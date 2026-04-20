"""
API principale pour le système de migration
"""

import os
import shutil
from pathlib import Path
import re
from uuid import uuid4

from fastapi import FastAPI, HTTPException, status, Depends, Header, Query, BackgroundTasks, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from typing import List, Dict, Optional
import logging
from datetime import datetime, timezone, timedelta
from pydantic import BaseModel, Field
import jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from src.discovery.kvm_discoverer import KVMDiscoverer
from src.discovery.vmware_esxi_discoverer import VMwareESXiDiscoverer
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
    build_vm_console_url,
    convert_disk_if_needed,
    normalize_disk_for_http_import,
    upload_disk,
    create_data_volume_http,
    wait_for_data_volume,
    build_import_url,
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
vmware_esxi_discoverer = VMwareESXiDiscoverer(
    host=config.VSPHERE_HOST,
    username=config.VSPHERE_USER,
    password=config.VSPHERE_PASSWORD,
    port=config.VSPHERE_PORT,
    datacenter=config.VSPHERE_DATACENTER,
    verify_ssl=config.VSPHERE_VERIFY_SSL,
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
    elif src == "vmware-esxi":
        try:
            details = vmware_esxi_discoverer.get_vm_details(vm_name)
        except RuntimeError as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=str(exc)
            )
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
    firmware: str = Field("auto", description="auto, bios ou uefi")
    disk_bus: str = Field("auto", description="auto, sata, scsi ou virtio")
    namespace: Optional[str] = Field(None, description="Namespace OpenShift")
    import_mode: str = Field("http", description="http ou upload")


def _sanitize_filename(filename: str) -> str:
    safe_name = Path(filename or "disk.img").name.strip()
    return safe_name or "disk.img"


def _persist_uploaded_bundle(uploads: List[UploadFile], target_vm_name: str) -> tuple[Path, List[str]]:
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

    return upload_dir, saved_names


def _extract_vmdk_extent_names(descriptor_path: Path) -> List[str]:
    try:
        descriptor = descriptor_path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return []

    extent_names: List[str] = []
    pattern = r'^\s*(?:RW|RDONLY|NOACCESS)\s+\d+\s+\S+\s+"([^"]+)"'
    for match in re.finditer(pattern, descriptor, re.MULTILINE):
        extent_names.append(Path(match.group(1)).name)
    return extent_names


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


def _build_uploaded_bundle_summary(upload_dir: Path, filenames: List[str], target_vm_name: str) -> Dict:
    primary_disk_path = _select_primary_disk_path(upload_dir, filenames)
    detected_format = primary_disk_path.suffix.lower().lstrip(".") or "raw"
    total_size_bytes = sum((upload_dir / name).stat().st_size for name in filenames if (upload_dir / name).exists())

    vmx_path: Path | None = None
    vm_name = target_vm_name
    try:
        vmx_path = _select_primary_vmx_path(upload_dir, filenames)
    except HTTPException:
        vmx_path = None

    if vmx_path is not None:
        vmx_data = vmware_ws_discoverer._parse_vmx(vmx_path)
        vm_name = vmx_data.get("displayName") or vmx_path.stem or target_vm_name

    split_extents: List[str] = []
    if detected_format == "vmdk":
        split_extents = _extract_vmdk_extent_names(primary_disk_path)
        missing_extents = [
            extent_name
            for extent_name in split_extents
            if not (upload_dir / extent_name).exists()
        ]
        if missing_extents:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Bundle VMware incomplet. Fichiers VMDK manquants: " + ", ".join(missing_extents)
            )

    return {
        "vm_name": vm_name,
        "upload_dir": str(upload_dir),
        "primary_disk_path": str(primary_disk_path),
        "detected_format": detected_format,
        "uploaded_files": filenames,
        "vmx_path": str(vmx_path) if vmx_path is not None else None,
        "split_extents": split_extents,
        "total_size_bytes": total_size_bytes,
    }


def _persist_uploaded_disks(uploads: List[UploadFile], target_vm_name: str) -> Dict:
    upload_dir, saved_names = _persist_uploaded_bundle(uploads, target_vm_name)
    return _build_uploaded_bundle_summary(upload_dir, saved_names, target_vm_name)


def _select_primary_vmx_path(upload_dir: Path, filenames: List[str]) -> Path:
    vmx_candidates = []
    for name in filenames:
        path = upload_dir / name
        if path.suffix.lower() == ".vmx":
            vmx_candidates.append(path)

    if not vmx_candidates:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Ajoutez le fichier .vmx avec les disques pour analyser une VM locale VMware."
        )

    vmx_candidates.sort(key=lambda item: len(item.name))
    return vmx_candidates[0]


def _build_uploaded_vmware_details(upload_dir: Path, filenames: List[str]) -> Dict:
    vmx_path = _select_primary_vmx_path(upload_dir, filenames)
    vmx_data = vmware_ws_discoverer._parse_vmx(vmx_path)
    vm_name = vmx_data.get("displayName") or vmx_path.stem

    return {
        "name": vm_name,
        "uuid": vmx_data.get("uuid.bios") or vmx_data.get("uuid.location") or "",
        "state": "uploaded",
        "hypervisor": "vmware-workstation",
        "specs": vmware_ws_discoverer._extract_specs(vmx_data),
        "disks": vmware_ws_discoverer._extract_disks(vmx_data, vmx_path.parent),
        "network": vmware_ws_discoverer._extract_network(vmx_data),
        "vmx_path": str(vmx_path),
        "uploaded_files": filenames,
    }


def _run_openshift_migration_job(job_id: str, req: OpenShiftMigrationRequest, namespace: str) -> None:
    """Execute la migration OpenShift hors du cycle de requete HTTP."""
    try:
        job_store.update_status(job_id, "running")
        job_store.add_log(job_id, f"Starting OpenShift migration in namespace '{namespace}' with import mode '{req.import_mode}'.")

        job_store.add_step(job_id, "namespace", "running")
        job_store.add_log(job_id, f"Ensuring namespace '{namespace}' exists.")
        ensure_namespace(namespace)
        job_store.finish_last_step(job_id, "completed")

        job_store.add_step(job_id, "conversion", "running")
        if (req.import_mode or "http").lower() == "upload":
            job_store.add_log(job_id, f"Preparing disk '{req.source_disk_path}' for upload mode.")
            image_path = convert_disk_if_needed(req.source_disk_path, req.source_disk_format)
        else:
            job_store.add_log(job_id, f"Normalizing disk '{req.source_disk_path}' for HTTP import mode.")
            image_path = normalize_disk_for_http_import(req.source_disk_path, req.source_disk_format)
        job_store.add_log(job_id, f"Disk ready at '{image_path}'.")
        job_store.finish_last_step(job_id, "completed")

        dv_name = f"{req.target_vm_name}-disk"
        import_mode = (req.import_mode or "http").lower()
        if import_mode == "upload":
            job_store.add_step(job_id, "upload", "running")
            job_store.add_log(job_id, f"Uploading image '{image_path}' into PVC '{dv_name}'.")
            upload_result = upload_disk(
                image_path=image_path,
                pvc_name=dv_name,
                size=req.pvc_size,
                namespace=namespace
            )
        else:
            job_store.add_step(job_id, "http-import", "running")
            job_store.add_log(job_id, f"Creating HTTP import DataVolume '{dv_name}' from '{image_path}'.")
            upload_result = create_data_volume_http(
                image_path=image_path,
                dv_name=dv_name,
                size=req.pvc_size,
                namespace=namespace
            )
            job_store.add_log(job_id, f"DataVolume '{dv_name}' created with import URL '{upload_result.import_url}'.")
        job_store.finish_last_step(job_id, "completed")

        if import_mode != "upload":
            job_store.add_step(job_id, "wait-for-import", "running")
            job_store.add_log(job_id, f"Waiting for DataVolume '{dv_name}' to reach 'Succeeded'.")
            wait_for_data_volume(namespace=namespace, dv_name=dv_name)
            job_store.add_log(job_id, f"DataVolume '{dv_name}' import succeeded.")
            job_store.finish_last_step(job_id, "completed")

        job_store.add_step(job_id, "apply-manifest", "running")
        job_store.add_log(job_id, f"Creating VirtualMachine '{req.target_vm_name}' using PVC '{upload_result.pvc_name}'.")
        manifest = build_vm_manifest(
            vm_name=req.target_vm_name,
            namespace=namespace,
            pvc_name=upload_result.pvc_name,
            memory=req.memory,
            cpu_cores=req.cpu_cores,
            firmware=req.firmware,
            disk_bus=req.disk_bus,
            source_path=req.source_disk_path,
            source_format=req.source_disk_format
        )
        apply_manifest(manifest)
        job_store.add_log(job_id, f"VirtualMachine '{req.target_vm_name}' manifest applied successfully.")
        job_store.finish_last_step(job_id, "completed")

        job_store.update_status(job_id, "completed")
    except Exception as exc:
        job_store.add_log(job_id, f"Migration failed: {exc}", level="error")
        job = job_store.get_job(job_id)
        if job and job.steps and job.steps[-1]["ended_at"] is None:
            job_store.finish_last_step(job_id, "failed")
        job_store.update_status(job_id, "failed", str(exc))


def _build_openshift_job_response(job, vm_name: str, target_vm_name: str, namespace: str, **extra_fields) -> Dict:
    vm_console_url = build_vm_console_url(target_vm_name, namespace)
    response = {
        "job_id": job.job_id,
        "vm_name": vm_name,
        "target_vm_name": target_vm_name,
        "namespace": namespace,
        "status": job.status,
        "vm_console_url": vm_console_url,
        "vm_resource_path": f"/k8s/ns/{namespace}/kubevirt.io~v1~VirtualMachine/{target_vm_name}"
    }
    response.update(extra_fields)
    return response


def _resolve_import_mode(import_mode: str | None) -> str:
    normalized = (import_mode or "http").strip().lower()
    if normalized not in {"http", "upload"}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="import_mode must be 'http' or 'upload'."
        )
    return normalized


@app.get("/api/v1/openshift/imports/{filename}")
async def serve_openshift_import_file(filename: str):
    imports_dir = Path(config.DATA_DIR) / "imports"
    file_path = (imports_dir / Path(filename).name).resolve()
    try:
        if not file_path.is_relative_to(imports_dir.resolve()):
            raise ValueError("outside imports dir")
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Import file not found"
        )
    if not file_path.exists() or not file_path.is_file():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Import file not found"
        )
    return FileResponse(file_path, media_type="application/octet-stream", filename=file_path.name)

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
            "discovery_vmware_esxi": "/api/v1/discovery/vmware-esxi",
            "discovery_vmware_workstation": "/api/v1/discovery/vmware-workstation",
            "migration_analyze": "/api/v1/migration/analyze/{vm_name}",
            "migration_analyze_upload": "/api/v1/migration/analyze-upload",
            "migration_plan": "/api/v1/migration/plan/{vm_name}",
            "migration_plan_upload": "/api/v1/migration/plan-upload",
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
            "vmware_esxi_configured": vmware_esxi_discoverer.is_configured,
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

@app.get("/api/v1/discovery/vmware-esxi", response_model=List[Dict])
async def discover_vmware_esxi_vms(_: None = Depends(_require_auth)):
    """Découvre toutes les VMs VMware ESXi / vSphere"""
    try:
        return vmware_esxi_discoverer.list_vms()
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc)
        )
    except Exception as e:
        logger.error(f"Erreur découverte VMware ESXi: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors de la découverte VMware ESXi: {str(e)}"
        )

@app.get("/api/v1/discovery/vmware-esxi/{vm_name}")
async def get_vmware_esxi_vm_details(vm_name: str, _: None = Depends(_require_auth)):
    """Récupère les détails d'une VM VMware ESXi / vSphere spécifique"""
    try:
        details = vmware_esxi_discoverer.get_vm_details(vm_name)
        if details is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"VM '{vm_name}' non trouvée"
            )
        return details
    except HTTPException:
        raise
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc)
        )
    except Exception as e:
        logger.error(f"Erreur détails VMware ESXi {vm_name}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors de la récupération des détails VMware ESXi: {str(e)}"
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


@app.post("/api/v1/migration/analyze-upload")
async def analyze_uploaded_vm_for_migration(
    vm_name: str = Form(...),
    bundle_files: List[UploadFile] = File(...),
    _: None = Depends(_require_auth)
):
    """Analyse une VM VMware locale envoyee depuis le frontend."""
    valid_files = [upload for upload in bundle_files if upload and upload.filename]
    if not valid_files:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Aucun fichier fourni pour l'analyse."
        )

    upload_dir, saved_names = _persist_uploaded_bundle(valid_files, vm_name)
    details = _build_uploaded_vmware_details(upload_dir, saved_names)
    analysis = analyze_vm(details)
    return {
        "vm_name": details.get("name", vm_name),
        "source": "uploaded-vmware-workstation",
        "bundle": _build_uploaded_bundle_summary(upload_dir, saved_names, vm_name),
        "details": details,
        "analysis": analysis
    }


@app.post("/api/v1/migration/plan-upload")
async def plan_uploaded_vm_migration(
    vm_name: str = Form(...),
    bundle_files: List[UploadFile] = File(...),
    _: None = Depends(_require_auth)
):
    """Prepare un plan de migration pour une VM VMware locale envoyee depuis le frontend."""
    valid_files = [upload for upload in bundle_files if upload and upload.filename]
    if not valid_files:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Aucun fichier fourni pour la planification."
        )

    upload_dir, saved_names = _persist_uploaded_bundle(valid_files, vm_name)
    details = _build_uploaded_vmware_details(upload_dir, saved_names)
    analysis = analyze_vm(details)
    conversion_plan = build_conversion_plan(details, analysis)
    strategy = choose_strategy(details, analysis, conversion_plan)
    return {
        "vm_name": details.get("name", vm_name),
        "source": "uploaded-vmware-workstation",
        "bundle": _build_uploaded_bundle_summary(upload_dir, saved_names, vm_name),
        "details": details,
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
        "logs": job.logs,
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
            "logs": job.logs,
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
    import_mode = _resolve_import_mode(req.import_mode)
    normalized_path = req.source_disk_path
    import_url = ""
    if import_mode == "http":
        normalized_path = normalize_disk_for_http_import(req.source_disk_path, req.source_disk_format)
        import_url = build_import_url(normalized_path)
    plan = {
        "strategy": {"strategy": f"openshift-{import_mode}"},
        "target_vm_name": req.target_vm_name,
        "namespace": namespace,
        "source_disk_path": normalized_path,
        "source_disk_format": req.source_disk_format,
        "import_mode": import_mode,
        "import_url": import_url,
        "vm_console_url": build_vm_console_url(req.target_vm_name, namespace)
    }
    job = job_store.create_job(vm_name, plan)
    queued_req = OpenShiftMigrationRequest(
        source_disk_path=normalized_path,
        source_disk_format=req.source_disk_format,
        target_vm_name=req.target_vm_name,
        pvc_size=req.pvc_size,
        memory=req.memory,
        cpu_cores=req.cpu_cores,
        firmware=req.firmware,
        disk_bus=req.disk_bus,
        namespace=namespace,
        import_mode=import_mode
    )
    background_tasks.add_task(_run_openshift_migration_job, job.job_id, queued_req, namespace)

    return _build_openshift_job_response(
        job,
        vm_name,
        req.target_vm_name,
        namespace,
        source_disk_path=normalized_path,
        import_mode=import_mode,
        import_url=import_url
    )


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
    firmware: str = Form("auto"),
    disk_bus: str = Form("auto"),
    namespace: str = Form(""),
    import_mode: str = Form("http"),
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

    bundle = _persist_uploaded_disks(valid_files, target_vm_name)
    stored_path = bundle["primary_disk_path"]
    detected_format = bundle["detected_format"]
    requested_format = (source_disk_format or "").strip().lower()
    effective_format = detected_format if requested_format in {"", "auto"} else requested_format
    effective_namespace = namespace or config.OPENSHIFT_NAMESPACE
    effective_import_mode = _resolve_import_mode(import_mode)

    req = OpenShiftMigrationRequest(
        source_disk_path=stored_path,
        source_disk_format=effective_format,
        target_vm_name=target_vm_name,
        pvc_size=pvc_size,
        memory=memory,
        cpu_cores=cpu_cores,
        firmware=firmware,
        disk_bus=disk_bus,
        namespace=effective_namespace,
        import_mode=effective_import_mode
    )

    import_url = ""
    if effective_import_mode == "http":
        req.source_disk_path = normalize_disk_for_http_import(stored_path, effective_format)
        import_url = build_import_url(req.source_disk_path)

    plan = {
        "strategy": {"strategy": f"openshift-{effective_import_mode}"},
        "target_vm_name": target_vm_name,
        "namespace": effective_namespace,
        "source_disk_path": req.source_disk_path,
        "source_disk_format": effective_format,
        "import_mode": effective_import_mode,
        "import_url": import_url,
        "uploaded_files": bundle["uploaded_files"],
        "bundle": bundle,
        "vm_console_url": build_vm_console_url(target_vm_name, effective_namespace)
    }
    job = job_store.create_job(vm_name, plan)
    background_tasks.add_task(_run_openshift_migration_job, job.job_id, req, effective_namespace)

    return _build_openshift_job_response(
        job,
        vm_name,
        target_vm_name,
        effective_namespace,
        source_disk_path=req.source_disk_path,
        source_disk_format=effective_format,
        import_mode=effective_import_mode,
        import_url=import_url,
        uploaded_files=bundle["uploaded_files"],
        bundle=bundle
    )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
