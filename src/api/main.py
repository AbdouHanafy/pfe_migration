"""
API principale pour le système de migration
"""

import os
import shutil
from pathlib import Path
from uuid import uuid4

from fastapi import FastAPI, HTTPException, status, Depends, Header, Query, BackgroundTasks, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from typing import List, Dict, Optional
import logging
from datetime import datetime, timezone, timedelta
from pydantic import BaseModel, Field
import jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from src.discovery.kvm_discoverer import KVMDiscoverer
from src.discovery.vmware_workstation_discoverer import VMwareWorkstationDiscoverer
from src.config import config
from src.database.session import get_db, Base, engine
from src.database.models import User
from src.analysis import analyze_vm
from src.conversion import build_conversion_plan
from src.migration import choose_strategy, start_migration
from src.monitoring import job_store, build_report
from src.openshift import (
    check_tools,
    ensure_namespace,
    convert_disk_if_needed,
    upload_disk,
    build_vm_manifest,
    apply_manifest
)

class RegisterRequest(BaseModel):
    matricule: str = Field(..., min_length=3, max_length=64)
    password: str = Field(..., min_length=6, max_length=128)

class LoginRequest(BaseModel):
    matricule: str = Field(..., min_length=3, max_length=64)
    password: str = Field(..., min_length=6, max_length=128)

# Configuration du logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Création de l'application FastAPI
app = FastAPI(
    title="Migration Intelligente VMs → OpenShift",
    description="API pour la migration automatique de VMs vers OpenShift",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS middleware
_cors_allow_credentials = config.API_ALLOW_CREDENTIALS
if "*" in config.API_CORS_ORIGINS and _cors_allow_credentials:
    _cors_allow_credentials = False

app.add_middleware(
    CORSMiddleware,
    allow_origins=config.API_CORS_ORIGINS,
    allow_credentials=_cors_allow_credentials,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Instances globales
kvm_discoverer = KVMDiscoverer(connection_uri=config.KVM_CONNECTION_URI)
vmware_ws_discoverer = VMwareWorkstationDiscoverer(
    search_paths=config.VMWARE_WORKSTATION_PATHS
)
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def _ensure_kvm_connected() -> None:
    if kvm_discoverer.conn is None:
        if not kvm_discoverer.connect():
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Impossible de se connecter à KVM"
            )

def _get_vm_details(vm_name: str, source: str) -> Dict:
    src = (source or "kvm").lower()
    if src == "kvm":
        _ensure_kvm_connected()
        details = kvm_discoverer.get_vm_details(vm_name)
    elif src == "vmware-workstation":
        details = vmware_ws_discoverer.get_vm_details(vm_name)
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown discovery source: {source}"
        )
    if details is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"VM '{vm_name}' non trouvée"
        )
    return details

def _require_auth(
    authorization: str | None = Header(default=None, alias="Authorization"),
    x_api_key: str | None = Header(default=None, alias="X-API-Key")
):
    if config.AUTH_MODE == "none":
        return
    if config.AUTH_MODE == "api_key":
        if not config.API_KEY:
            return
        token = None
        if authorization:
            if authorization.lower().startswith("bearer "):
                token = authorization.split(" ", 1)[1].strip()
            else:
                token = authorization.strip()
        if not token and x_api_key:
            token = x_api_key.strip()
        if token != config.API_KEY:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid API key"
            )
        return
    if config.AUTH_MODE == "jwt":
        if not authorization or not authorization.lower().startswith("bearer "):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Missing Bearer token"
            )
        token = authorization.split(" ", 1)[1].strip()
        try:
            jwt.decode(token, config.JWT_SECRET, algorithms=[config.JWT_ALGORITHM])
        except Exception:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token"
            )
        return

def _hash_password(password: str) -> str:
    return pwd_context.hash(password)

def _verify_password(password: str, password_hash: str) -> bool:
    return pwd_context.verify(password, password_hash)

def _create_token(matricule: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=config.JWT_EXPIRE_MINUTES)
    payload = {"sub": matricule, "exp": expire}
    return jwt.encode(payload, config.JWT_SECRET, algorithm=config.JWT_ALGORITHM)

class OpenShiftMigrationRequest(BaseModel):
    source_disk_path: str = Field(..., description="Chemin vers le disque source (ex: VMDK)")
    source_disk_format: str = Field("vmdk", description="Format du disque source")
    target_vm_name: str = Field(..., description="Nom de la VM cible sur OpenShift")
    pvc_size: str = Field("20Gi", description="Taille du PVC")
    memory: str = Field("2Gi", description="Memoire demandee pour la VM")
    cpu_cores: int = Field(2, description="Nombre de coeurs CPU")
    firmware: str = Field("bios", description="bios ou uefi")
    namespace: Optional[str] = Field(None, description="Namespace OpenShift")


def _sanitize_filename(filename: str) -> str:
    safe_name = Path(filename or "disk.img").name.strip()
    return safe_name or "disk.img"


def _select_primary_disk_path(upload_dir: Path, filenames: List[str]) -> Path:
    preferred = []
    split_pattern = "-s"

    for name in filenames:
        path = upload_dir / name
        suffix = path.suffix.lower()
        if suffix not in {".vmdk", ".qcow2", ".img", ".raw"}:
            continue
        if suffix == ".vmdk" and split_pattern not in path.stem.lower():
            preferred.append(path)

    if preferred:
        preferred.sort(key=lambda item: len(item.name))
        return preferred[0]

    candidates = [upload_dir / name for name in filenames]
    candidates = [path for path in candidates if path.suffix.lower() in {".vmdk", ".qcow2", ".img", ".raw"}]
    if not candidates:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Aucun disque exploitable trouve dans les fichiers uploades."
        )
    candidates.sort(key=lambda item: len(item.name))
    return candidates[0]


def _persist_uploaded_disks(uploads: List[UploadFile], target_vm_name: str) -> tuple[str, str, List[str]]:
    os.makedirs(config.DATA_DIR, exist_ok=True)
    upload_dir = Path(config.DATA_DIR) / "uploads" / f"{target_vm_name}-{uuid4().hex[:8]}"
    upload_dir.mkdir(parents=True, exist_ok=True)

    saved_names: List[str] = []
    for upload in uploads:
        safe_name = _sanitize_filename(upload.filename or f"{target_vm_name}.img")
        disk_path = upload_dir / safe_name
        try:
            with disk_path.open("wb") as buffer:
                shutil.copyfileobj(upload.file, buffer, length=1024 * 1024)
        finally:
            upload.file.close()
        saved_names.append(safe_name)

    primary_disk_path = _select_primary_disk_path(upload_dir, saved_names)
    detected_format = primary_disk_path.suffix.lower().lstrip(".") or "raw"
    return str(primary_disk_path), detected_format, saved_names


def _run_openshift_migration_job(job_id: str, req: OpenShiftMigrationRequest, namespace: str) -> None:
    """Execute la migration OpenShift hors du cycle de requete HTTP."""
    try:
        job_store.update_status(job_id, "running")

        job_store.add_step(job_id, "namespace", "running")
        ensure_namespace(namespace)
        job_store.finish_last_step(job_id, "completed")

        job_store.add_step(job_id, "conversion", "running")
        image_path = convert_disk_if_needed(req.source_disk_path, req.source_disk_format)
        job_store.finish_last_step(job_id, "completed")

        job_store.add_step(job_id, "upload", "running")
        upload_result = upload_disk(
            image_path=image_path,
            pvc_name=f"{req.target_vm_name}-disk",
            size=req.pvc_size,
            namespace=namespace
        )
        job_store.finish_last_step(job_id, "completed")

        job_store.add_step(job_id, "apply-manifest", "running")
        manifest = build_vm_manifest(
            vm_name=req.target_vm_name,
            namespace=namespace,
            pvc_name=upload_result.pvc_name,
            memory=req.memory,
            cpu_cores=req.cpu_cores,
            firmware=req.firmware
        )
        apply_manifest(manifest)
        job_store.finish_last_step(job_id, "completed")

        job_store.update_status(job_id, "completed")
    except Exception as exc:
        job = job_store.get_job(job_id)
        if job and job.steps and job.steps[-1]["ended_at"] is None:
            job_store.finish_last_step(job_id, "failed")
        job_store.update_status(job_id, "failed", str(exc))

@app.on_event("startup")
async def startup_event():
    """Initialisation au démarrage"""
    logger.info("Démarrage de l'API Migration...")
    Base.metadata.create_all(bind=engine)
    # Connexion à KVM
    if kvm_discoverer.connect():
        logger.info("Connecté à KVM")
    else:
        logger.warning("Impossible de se connecter à KVM")

@app.on_event("shutdown")
async def shutdown_event():
    """Nettoyage à l'arrêt"""
    logger.info("Arrêt de l'API Migration...")
    kvm_discoverer.disconnect()

@app.get("/")
async def root(_: None = Depends(_require_auth)):
    """Endpoint racine"""
    return {
        "service": "Migration Intelligente VMs → OpenShift",
        "version": "1.0.0",
        "status": "running",
        "endpoints": {
            "health": "/health",
            "docs": "/docs",
            "discovery": "/api/v1/discovery/kvm",
            "discovery_vmware_workstation": "/api/v1/discovery/vmware-workstation",
            "migration_analyze": "/api/v1/migration/analyze/{vm_name}",
            "migration_plan": "/api/v1/migration/plan/{vm_name}",
            "migration_start": "/api/v1/migration/start/{vm_name}",
            "migration_status": "/api/v1/migration/status/{job_id}",
            "migration_jobs": "/api/v1/migration/jobs",
            "migration_report": "/api/v1/migration/report/{job_id}",
            "migration_openshift": "/api/v1/migration/openshift/{vm_name}",
            "migration_openshift_upload": "/api/v1/migration/openshift-upload/{vm_name}"
        }
    }

@app.get("/health")
async def health_check(_: None = Depends(_require_auth)):
    """Vérification de la santé du service"""
    return {
        "status": "healthy",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "services": {
            "kvm_connection": kvm_discoverer.conn is not None,
            "tools": check_tools()
        }
    }

@app.post("/api/v1/auth/register")
async def register_user(req: RegisterRequest, db: Session = Depends(get_db)):
    if config.AUTH_MODE != "jwt":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Auth mode is not jwt"
        )
    existing = db.query(User).filter(User.matricule == req.matricule).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Matricule already exists"
        )
    user = User(matricule=req.matricule, password_hash=_hash_password(req.password))
    db.add(user)
    db.commit()
    return {"status": "created", "matricule": req.matricule}

@app.post("/api/v1/auth/login")
async def login_user(req: LoginRequest, db: Session = Depends(get_db)):
    if config.AUTH_MODE != "jwt":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Auth mode is not jwt"
        )
    user = db.query(User).filter(User.matricule == req.matricule).first()
    if not user or not _verify_password(req.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials"
        )
    token = _create_token(user.matricule)
    return {"access_token": token, "token_type": "bearer"}

@app.get("/api/v1/discovery/kvm", response_model=List[Dict])
async def discover_kvm_vms(_: None = Depends(_require_auth)):
    """Découvre toutes les VMs KVM"""
    try:
        _ensure_kvm_connected()
        vms = kvm_discoverer.list_vms()
        return vms
    except Exception as e:
        logger.error(f"Erreur découverte KVM: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors de la découverte: {str(e)}"
        )

@app.get("/api/v1/discovery/kvm/{vm_name}")
async def get_kvm_vm_details(vm_name: str, _: None = Depends(_require_auth)):
    """Récupère les détails d'une VM KVM spécifique"""
    try:
        _ensure_kvm_connected()
        details = kvm_discoverer.get_vm_details(vm_name)
        if details is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"VM '{vm_name}' non trouvée"
            )
        return details
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erreur détails VM {vm_name}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors de la récupération des détails: {str(e)}"
        )

@app.get("/api/v1/discovery/vmware-workstation", response_model=List[Dict])
async def discover_vmware_ws_vms(_: None = Depends(_require_auth)):
    """Découvre toutes les VMs VMware Workstation"""
    try:
        return vmware_ws_discoverer.list_vms()
    except Exception as e:
        logger.error(f"Erreur découverte VMware Workstation: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors de la découverte VMware Workstation: {str(e)}"
        )

@app.get("/api/v1/discovery/vmware-workstation/{vm_name}")
async def get_vmware_ws_vm_details(vm_name: str, _: None = Depends(_require_auth)):
    """Récupère les détails d'une VM VMware Workstation spécifique"""
    try:
        details = vmware_ws_discoverer.get_vm_details(vm_name)
        if details is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"VM '{vm_name}' non trouvée"
            )
        return details
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erreur détails VMware Workstation {vm_name}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors de la récupération des détails: {str(e)}"
        )

@app.post("/api/v1/migration/analyze/{vm_name}")
async def analyze_vm_for_migration(
    vm_name: str,
    source: str = Query(default="kvm"),
    _: None = Depends(_require_auth)
):
    """Analyse une VM pour la migration"""
    details = _get_vm_details(vm_name, source)
    analysis = analyze_vm(details)
    return {
        "vm_name": vm_name,
        "analysis": analysis
    }

@app.post("/api/v1/migration/plan/{vm_name}")
async def plan_migration(
    vm_name: str,
    source: str = Query(default="kvm"),
    _: None = Depends(_require_auth)
):
    """Prepare un plan de migration"""
    details = _get_vm_details(vm_name, source)
    analysis = analyze_vm(details)
    conversion_plan = build_conversion_plan(details, analysis)
    strategy = choose_strategy(details, analysis, conversion_plan)
    return {
        "vm_name": vm_name,
        "analysis": analysis,
        "conversion_plan": conversion_plan,
        "strategy": strategy
    }

@app.post("/api/v1/migration/start/{vm_name}")
async def start_migration_job(
    vm_name: str,
    source: str = Query(default="kvm"),
    _: None = Depends(_require_auth)
):
    """Demarre une migration (simulee)"""
    details = _get_vm_details(vm_name, source)
    analysis = analyze_vm(details)
    conversion_plan = build_conversion_plan(details, analysis)
    strategy = choose_strategy(details, analysis, conversion_plan)
    job = start_migration(details, analysis, conversion_plan, strategy)
    return job

@app.get("/api/v1/migration/status/{job_id}")
async def get_migration_status(job_id: str, _: None = Depends(_require_auth)):
    """Retourne le statut d'un job"""
    job = job_store.get_job(job_id)
    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job '{job_id}' non trouvé"
        )
    return {
        "job_id": job.job_id,
        "vm_name": job.vm_name,
        "status": job.status,
        "created_at": job.created_at,
        "updated_at": job.updated_at,
        "steps": job.steps,
        "error": job.error
    }

@app.get("/api/v1/migration/jobs")
async def list_migration_jobs(_: None = Depends(_require_auth)):
    """Liste les jobs"""
    jobs = job_store.list_jobs()
    return [
        {
            "job_id": job.job_id,
            "vm_name": job.vm_name,
            "status": job.status,
            "created_at": job.created_at,
            "updated_at": job.updated_at,
            "error": job.error
        }
        for job in jobs
    ]

@app.get("/api/v1/migration/report/{job_id}")
async def get_migration_report(job_id: str, _: None = Depends(_require_auth)):
    """Retourne un rapport de migration"""
    job = job_store.get_job(job_id)
    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job '{job_id}' non trouvé"
        )
    return build_report(job)

@app.post("/api/v1/migration/openshift/{vm_name}")
async def migrate_to_openshift(
    vm_name: str,
    req: OpenShiftMigrationRequest,
    background_tasks: BackgroundTasks,
    _: None = Depends(_require_auth)
):
    """
    Migration reelle vers OpenShift (necessite oc + virtctl configures).
    """
    if not config.ENABLE_REAL_MIGRATION:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="ENABLE_REAL_MIGRATION=false. Activez la migration reelle via la config."
        )

    namespace = req.namespace or config.OPENSHIFT_NAMESPACE
    plan = {
        "strategy": {"strategy": "openshift-background"},
        "target_vm_name": req.target_vm_name,
        "namespace": namespace,
        "source_disk_path": req.source_disk_path,
        "source_disk_format": req.source_disk_format
    }
    job = job_store.create_job(vm_name, plan)
    background_tasks.add_task(_run_openshift_migration_job, job.job_id, req, namespace)

    return {
        "job_id": job.job_id,
        "vm_name": vm_name,
        "target_vm_name": req.target_vm_name,
        "namespace": namespace,
        "status": "queued"
    }


@app.post("/api/v1/migration/openshift-upload/{vm_name}")
async def migrate_uploaded_disk_to_openshift(
    vm_name: str,
    background_tasks: BackgroundTasks,
    disk_files: List[UploadFile] = File(...),
    source_disk_format: str = Form(""),
    target_vm_name: str = Form(...),
    pvc_size: str = Form("20Gi"),
    memory: str = Form("2Gi"),
    cpu_cores: int = Form(2),
    firmware: str = Form("bios"),
    namespace: str = Form(""),
    _: None = Depends(_require_auth)
):
    """
    Migration reelle vers OpenShift avec upload du disque depuis le frontend.
    """
    if not config.ENABLE_REAL_MIGRATION:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="ENABLE_REAL_MIGRATION=false. Activez la migration reelle via la config."
        )

    valid_files = [upload for upload in disk_files if upload and upload.filename]
    if not valid_files:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Aucun fichier disque fourni."
        )

    stored_path, detected_format, uploaded_files = _persist_uploaded_disks(valid_files, target_vm_name)
    effective_format = (source_disk_format or detected_format).lower()
    effective_namespace = namespace or config.OPENSHIFT_NAMESPACE

    req = OpenShiftMigrationRequest(
        source_disk_path=stored_path,
        source_disk_format=effective_format,
        target_vm_name=target_vm_name,
        pvc_size=pvc_size,
        memory=memory,
        cpu_cores=cpu_cores,
        firmware=firmware,
        namespace=effective_namespace
    )

    plan = {
        "strategy": {"strategy": "openshift-upload"},
        "target_vm_name": target_vm_name,
        "namespace": effective_namespace,
        "source_disk_path": stored_path,
        "source_disk_format": effective_format,
        "uploaded_files": uploaded_files
    }
    job = job_store.create_job(vm_name, plan)
    background_tasks.add_task(_run_openshift_migration_job, job.job_id, req, effective_namespace)

    return {
        "job_id": job.job_id,
        "vm_name": vm_name,
        "target_vm_name": target_vm_name,
        "namespace": effective_namespace,
        "source_disk_path": stored_path,
        "source_disk_format": effective_format,
        "uploaded_files": uploaded_files,
        "status": "queued"
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
