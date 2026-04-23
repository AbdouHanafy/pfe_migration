"""
Configuration du projet PFE Migration
"""

import os
from pathlib import Path
from dotenv import load_dotenv
from typing import Dict, Any, List

load_dotenv()


PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _resolve_project_path(raw_path: str, default_relative: str) -> str:
    candidate = Path((raw_path or "").strip() or default_relative).expanduser()
    if not candidate.is_absolute():
        candidate = PROJECT_ROOT / candidate
    return str(candidate.resolve())

class Config:
    """Configuration de l'application"""
    
    # Application
    APP_NAME = "Migration Intelligente VMs → OpenShift"
    APP_VERSION = "1.0.0"
    APP_DESCRIPTION = "Système de migration automatisée avec IA"
    
    # API
    API_HOST = os.getenv("API_HOST", "0.0.0.0")
    API_PORT = int(os.getenv("API_PORT", "8000"))
    API_DEBUG = os.getenv("API_DEBUG", "True").lower() == "true"
    API_ALLOW_CREDENTIALS = os.getenv("API_ALLOW_CREDENTIALS", "false").lower() == "true"

    @staticmethod
    def _parse_csv_env(name: str, default: List[str]) -> List[str]:
        raw = os.getenv(name, "")
        if not raw:
            return default
        if raw.strip() == "*":
            return ["*"]
        return [item.strip() for item in raw.split(",") if item.strip()]

    API_CORS_ORIGINS = _parse_csv_env.__func__(
        "API_CORS_ORIGINS",
        ["http://localhost:8000", "http://localhost:3000", "http://localhost:5173"]
    )
    
    # KVM
    KVM_CONNECTION_URI = os.getenv("KVM_URI", "qemu:///system")

    # Local agent
    LOCAL_AGENT_HOST = os.getenv("LOCAL_AGENT_HOST", "127.0.0.1")
    LOCAL_AGENT_PORT = int(os.getenv("LOCAL_AGENT_PORT", "8010"))
    LOCAL_AGENT_TOKEN = os.getenv("LOCAL_AGENT_TOKEN", "")
    LOCAL_AGENT_CORS_ORIGINS = _parse_csv_env.__func__(
        "LOCAL_AGENT_CORS_ORIGINS",
        ["http://localhost:5173", "http://127.0.0.1:5173"]
    )

    # VMware Workstation discovery (comma-separated paths)
    VMWARE_WORKSTATION_PATHS = _parse_csv_env.__func__(
        "VMWARE_WORKSTATION_PATHS",
        [str(os.path.expanduser("~/vmware"))]
    )

    # VMware ESXi / vSphere discovery
    VSPHERE_HOST = os.getenv("VSPHERE_HOST", "")
    VSPHERE_PORT = int(os.getenv("VSPHERE_PORT", "443"))
    VSPHERE_USER = os.getenv("VSPHERE_USER", "")
    VSPHERE_PASSWORD = os.getenv("VSPHERE_PASSWORD", "")
    VSPHERE_DATACENTER = os.getenv("VSPHERE_DATACENTER", "")
    VSPHERE_VERIFY_SSL = os.getenv("VSPHERE_VERIFY_SSL", "false").lower() == "true"
    
    # Base de données (pour plus tard)
    DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./migration.db")
    
    # Paths
    LOG_DIR = _resolve_project_path(os.getenv("LOG_DIR", ""), "logs")
    DATA_DIR = _resolve_project_path(os.getenv("DATA_DIR", ""), "data")
    
    # Migration
    DEFAULT_MIGRATION_STRATEGY = "auto"  # auto, direct, conversion
    MAX_CONCURRENT_MIGRATIONS = int(os.getenv("MAX_CONCURRENT_MIGRATIONS", "3"))

    # OpenShift / KubeVirt
    OPENSHIFT_NAMESPACE = os.getenv("OPENSHIFT_NAMESPACE", "vm-migration")
    OPENSHIFT_CONSOLE_URL = os.getenv("OPENSHIFT_CONSOLE_URL", "")
    OPENSHIFT_IMPORT_BASE_URL = os.getenv("OPENSHIFT_IMPORT_BASE_URL", "")
    OPENSHIFT_UPLOADPROXY_URL = os.getenv("OPENSHIFT_UPLOADPROXY_URL", "")
    OPENSHIFT_INSECURE_UPLOAD = os.getenv("OPENSHIFT_INSECURE_UPLOAD", "true").lower() == "true"
    ENABLE_REAL_MIGRATION = os.getenv("ENABLE_REAL_MIGRATION", "false").lower() == "true"

    # API Security
    API_KEY = os.getenv("API_KEY", "")
    API_KEY_HEADER = os.getenv("API_KEY_HEADER", "Authorization")

    # Auth mode: none | api_key | jwt
    AUTH_MODE = os.getenv("AUTH_MODE", "api_key").lower()
    JWT_SECRET = os.getenv("JWT_SECRET", "change-me")
    JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
    JWT_EXPIRE_MINUTES = int(os.getenv("JWT_EXPIRE_MINUTES", "120"))
    
    @classmethod
    def to_dict(cls) -> Dict[str, Any]:
        """Retourne la configuration sous forme de dictionnaire"""
        return {
            key: value
            for key, value in cls.__dict__.items()
            if not key.startswith('_') and not callable(value)
        }
    
    @classmethod
    def display(cls):
        """Affiche la configuration"""
        print("=" * 50)
        print(f"{cls.APP_NAME} - Configuration")
        print("=" * 50)
        
        for key, value in cls.to_dict().items():
            print(f"{key:30}: {value}")
        
        print("=" * 50)

# Instance globale
config = Config()

if __name__ == "__main__":
    config.display()
