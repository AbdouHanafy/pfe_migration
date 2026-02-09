from .client import (
    ensure_namespace,
    convert_disk_if_needed,
    upload_disk,
    build_vm_manifest,
    apply_manifest
)

__all__ = [
    "ensure_namespace",
    "convert_disk_if_needed",
    "upload_disk",
    "build_vm_manifest",
    "apply_manifest"
]
