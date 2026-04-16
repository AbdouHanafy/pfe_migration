"""
OpenShift/KubeVirt helpers for real migration steps.
"""

from dataclasses import dataclass
from typing import Dict, Optional, Tuple
import os
import shutil
import subprocess
import json

from src.config import config

@dataclass
class UploadResult:
    pvc_name: str
    namespace: str
    image_path: str
    size: str
    uploadproxy_url: str

def _run(cmd: list[str]) -> Tuple[int, str, str]:
    result = subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=False
    )
    return result.returncode, result.stdout.strip(), result.stderr.strip()


def check_tools() -> Dict[str, bool]:
    """Retourne la disponibilite des binaires externes requis."""
    return {
        "oc": shutil.which("oc") is not None,
        "virtctl": shutil.which("virtctl") is not None,
        "qemu-img": shutil.which("qemu-img") is not None
    }

def get_uploadproxy_url() -> str:
    if config.OPENSHIFT_UPLOADPROXY_URL:
        return config.OPENSHIFT_UPLOADPROXY_URL
    cmd = [
        "oc", "get", "route",
        "-n", "openshift-cnv",
        "cdi-uploadproxy",
        "-o", "jsonpath={.spec.host}"
    ]
    code, out, err = _run(cmd)
    if code != 0 or not out:
        raise RuntimeError(f"Unable to get uploadproxy route: {err or out}")
    return f"https://{out}"

def ensure_namespace(namespace: str) -> None:
    code, _, _ = _run(["oc", "get", "namespace", namespace])
    if code == 0:
        return
    code, out, err = _run(["oc", "new-project", namespace])
    if code != 0:
        raise RuntimeError(f"Unable to create namespace: {err or out}")

def convert_disk_if_needed(source_path: str, source_format: str) -> str:
    source_format = (source_format or "").lower()
    if source_format in ("qcow2", "raw"):
        return source_path

    os.makedirs(config.DATA_DIR, exist_ok=True)
    target_path = os.path.join(config.DATA_DIR, "converted.qcow2")

    cmd = [
        "qemu-img", "convert",
        "-O", "qcow2",
        source_path,
        target_path
    ]
    code, out, err = _run(cmd)
    if code != 0:
        raise RuntimeError(f"Disk conversion failed: {err or out}")
    return target_path

def upload_disk(image_path: str, pvc_name: str, size: str, namespace: str) -> UploadResult:
    uploadproxy_url = get_uploadproxy_url()
    cmd = [
        "virtctl", "image-upload",
        "pvc", pvc_name,
        "--namespace", namespace,
        "--image-path", image_path,
        "--size", size,
        "--uploadproxy-url", uploadproxy_url
    ]
    if config.OPENSHIFT_INSECURE_UPLOAD:
        cmd.append("--insecure")

    code, out, err = _run(cmd)
    if code != 0:
        raise RuntimeError(f"Image upload failed: {err or out}")
    return UploadResult(
        pvc_name=pvc_name,
        namespace=namespace,
        image_path=image_path,
        size=size,
        uploadproxy_url=uploadproxy_url
    )

def build_vm_manifest(
    vm_name: str,
    namespace: str,
    pvc_name: str,
    memory: str,
    cpu_cores: int,
    firmware: str = "bios"
) -> Dict:
    firmware = (firmware or "bios").lower()
    bootloader = {"bios": {}} if firmware == "bios" else {"uefi": {}}

    return {
        "apiVersion": "kubevirt.io/v1",
        "kind": "VirtualMachine",
        "metadata": {"name": vm_name, "namespace": namespace},
        "spec": {
            "running": True,
            "template": {
                "metadata": {"labels": {"kubevirt.io/domain": vm_name}},
                "spec": {
                    "domain": {
                        "cpu": {"cores": cpu_cores},
                        "resources": {"requests": {"memory": memory}},
                        "devices": {
                            "disks": [
                                {"name": "rootdisk", "disk": {"bus": "virtio"}}
                            ],
                            "interfaces": [
                                {"name": "default", "masquerade": {}}
                            ]
                        },
                        "firmware": {"bootloader": bootloader}
                    },
                    "networks": [{"name": "default", "pod": {}}],
                    "volumes": [
                        {"name": "rootdisk", "persistentVolumeClaim": {"claimName": pvc_name}}
                    ]
                }
            }
        }
    }

def apply_manifest(manifest: Dict) -> None:
    data = json.dumps(manifest)
    cmd = ["oc", "apply", "-f", "-"]
    process = subprocess.Popen(
        cmd,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )
    out, err = process.communicate(input=data)
    if process.returncode != 0:
        raise RuntimeError(f"Apply manifest failed: {err or out}")
