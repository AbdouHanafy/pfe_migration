"""
OpenShift/KubeVirt helpers for real migration steps.
"""

from dataclasses import dataclass
from typing import Callable, Dict, Tuple
import os
import shutil
import subprocess
import json
import math
import re
from pathlib import Path
from urllib.parse import quote
from uuid import uuid4
import time

from src.config import config

SUPPORTED_BOOT_FIRMWARE = {"auto", "bios", "uefi", "efi"}
SUPPORTED_DISK_BUS = {"auto", "virtio", "scsi", "sata"}
PVC_FILESYSTEM_OVERHEAD_RATIO = 0.06
ProgressCallback = Callable[[str], None]


@dataclass
class UploadResult:
    pvc_name: str
    namespace: str
    image_path: str
    size: str
    uploadproxy_url: str


@dataclass
class DataVolumeResult:
    dv_name: str
    pvc_name: str
    namespace: str
    image_path: str
    size: str
    import_url: str


def _run(cmd: list[str]) -> Tuple[int, str, str]:
    result = subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=False
    )
    return result.returncode, result.stdout.strip(), result.stderr.strip()


def _diagnose_dv_blocker(namespace: str, dv_name: str, payload: Dict) -> str:
    claim_name = payload.get("status", {}).get("claimName") or dv_name
    code, out, err = _run(["oc", "describe", "pvc", claim_name, "-n", namespace])
    describe_output = out or err
    if code != 0 or not describe_output:
        return ""

    if "WaitForFirstConsumer" in describe_output and "Used By:     <none>" in describe_output:
        return (
            f"Cluster storage deadlock: PVC '{claim_name}' is waiting for first consumer, "
            "but no CDI importer pod is consuming it."
        )

    if "selected-node:" in describe_output and "master-1.ocp.pfe.lan" in describe_output:
        return (
            f"PVC '{claim_name}' was pinned to master-1.ocp.pfe.lan, which is not currently usable "
            "for this migration."
        )

    return ""


def _run_qemu_convert_with_progress(cmd: list[str], progress_callback: ProgressCallback | None = None) -> Tuple[int, str, str]:
    process = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )
    stderr_parts: list[str] = []
    progress_buffer = ""
    last_reported_percent = -1

    while True:
        chunk = process.stderr.read(1)
        if chunk == "" and process.poll() is not None:
            break
        if not chunk:
            continue
        stderr_parts.append(chunk)
        progress_buffer += chunk
        matches = re.findall(r"\(\s*([0-9]+(?:\.[0-9]+)?)\/100%\)", progress_buffer)
        if matches:
            try:
                percent = int(float(matches[-1]))
            except ValueError:
                percent = last_reported_percent
            if progress_callback and percent > last_reported_percent:
                progress_callback(f"Conversion progress: {percent}%")
                last_reported_percent = percent
            if len(progress_buffer) > 128:
                progress_buffer = progress_buffer[-128:]

    stdout = process.stdout.read() if process.stdout else ""
    stderr = "".join(stderr_parts)
    return process.wait(), stdout.strip(), stderr.strip()


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


def list_virtual_machines(namespace: str) -> list[Dict]:
    code, out, err = _run(["oc", "get", "vm", "-n", namespace, "-o", "json"])
    if code != 0:
        raise RuntimeError(f"Unable to list virtual machines in namespace '{namespace}': {err or out}")

    try:
        payload = json.loads(out or "{}")
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Invalid VM list output for namespace '{namespace}': {exc}") from exc

    items = payload.get("items", [])
    results: list[Dict] = []
    for item in items:
        metadata = item.get("metadata", {})
        spec = item.get("spec", {})
        status = item.get("status", {})
        printable_status = status.get("printableStatus") or "Unknown"
        cpu_cores = spec.get("template", {}).get("spec", {}).get("domain", {}).get("cpu", {}).get("cores") or 0
        memory = (
            spec.get("template", {})
            .get("spec", {})
            .get("domain", {})
            .get("resources", {})
            .get("requests", {})
            .get("memory", "")
        )
        volumes = spec.get("template", {}).get("spec", {}).get("volumes", []) or []
        results.append({
            "name": metadata.get("name", ""),
            "namespace": metadata.get("namespace", namespace),
            "created_at": metadata.get("creationTimestamp", ""),
            "status": printable_status,
            "ready": bool(status.get("ready")),
            "cpu_cores": cpu_cores,
            "memory": memory,
            "disks_count": len(volumes),
            "run_strategy": spec.get("runStrategy", ""),
            "console_url": build_vm_console_url(metadata.get("name", ""), metadata.get("namespace", namespace)),
        })
    return results


def set_virtual_machine_run_strategy(namespace: str, vm_name: str, run_strategy: str) -> None:
    payload = json.dumps({"spec": {"runStrategy": run_strategy}})
    code, out, err = _run([
        "oc",
        "patch",
        "vm",
        vm_name,
        "-n",
        namespace,
        "--type",
        "merge",
        "-p",
        payload,
    ])
    if code != 0:
        raise RuntimeError(
            f"Unable to set VM '{vm_name}' runStrategy to '{run_strategy}' in namespace '{namespace}': {err or out}"
        )


def build_vm_console_url(vm_name: str, namespace: str) -> str:
    base_url = (config.OPENSHIFT_CONSOLE_URL or "").strip().rstrip("/")
    if not base_url:
        return ""
    encoded_namespace = quote(namespace, safe="")
    encoded_vm_name = quote(vm_name, safe="")
    return f"{base_url}/k8s/ns/{encoded_namespace}/kubevirt.io~v1~VirtualMachine/{encoded_vm_name}"


def get_import_base_url() -> str:
    base_url = (config.OPENSHIFT_IMPORT_BASE_URL or "").strip().rstrip("/")
    if not base_url:
        raise RuntimeError("OPENSHIFT_IMPORT_BASE_URL is required for HTTP import mode.")
    return base_url


def _build_converted_target_path(source_path: str, output_format: str) -> str:
    os.makedirs(config.DATA_DIR, exist_ok=True)
    source = Path(source_path)
    suffix = ".raw" if output_format == "raw" else f".{output_format}"
    stem = source.stem or "disk"
    unique_suffix = uuid4().hex[:8]
    return str(Path(config.DATA_DIR) / f"{stem}-converted-{unique_suffix}{suffix}")


def _build_import_target_path(source_path: str) -> str:
    os.makedirs(config.DATA_DIR, exist_ok=True)
    imports_dir = Path(config.DATA_DIR) / "imports"
    imports_dir.mkdir(parents=True, exist_ok=True)
    source = Path(source_path)
    unique_suffix = uuid4().hex[:8]
    return str(imports_dir / f"{source.stem or 'disk'}-{unique_suffix}.qcow2")


def _qemu_img_info(image_path: str) -> Dict:
    code, out, err = _run(["qemu-img", "info", "--output", "json", image_path])
    if code != 0:
        raise RuntimeError(f"Unable to inspect image '{image_path}': {err or out}")
    try:
        return json.loads(out)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Invalid qemu-img info output for '{image_path}': {exc}") from exc


def _parse_size_to_bytes(size: str) -> int:
    raw = (size or "").strip()
    if not raw:
        raise ValueError("PVC size cannot be empty.")

    normalized = raw.lower()
    units = {
        "ki": 1024,
        "mi": 1024 ** 2,
        "gi": 1024 ** 3,
        "ti": 1024 ** 4,
    }
    for suffix, factor in units.items():
        if normalized.endswith(suffix):
            return int(float(normalized[:-len(suffix)].strip()) * factor)
    return int(normalized)


def _bytes_to_gib_ceil(size_bytes: int) -> str:
    gib = max(1, math.ceil(size_bytes / (1024 ** 3)))
    return f"{gib}Gi"


def resolve_upload_size(image_path: str, requested_size: str) -> str:
    info = _qemu_img_info(image_path)
    virtual_size = int(info.get("virtual-size") or 0)
    actual_size = int(info.get("actual-size") or 0)
    base_size = max(virtual_size, actual_size)
    if base_size <= 0:
        raise RuntimeError(f"Unable to determine image size for '{image_path}'.")

    # CDI uploads to filesystem PVCs need headroom beyond the virtual disk size.
    required_bytes = math.ceil(base_size / (1 - PVC_FILESYSTEM_OVERHEAD_RATIO))
    requested_bytes = _parse_size_to_bytes(requested_size)

    # Honor the user's request when it is larger than the minimum safe size.
    # This keeps the UI/backend contract predictable while still preventing
    # undersized PVCs that would fail CDI imports.
    return _bytes_to_gib_ceil(max(required_bytes, requested_bytes))


def ensure_upload_pvc(namespace: str, pvc_name: str, size: str) -> None:
    code, out, err = _run([
        "oc", "get", "pvc", pvc_name,
        "-n", namespace,
        "-o", "json"
    ])
    if code == 0:
        try:
            pvc = json.loads(out)
        except json.JSONDecodeError:
            pvc = {}
        phase = pvc.get("status", {}).get("phase")
        if phase == "Bound":
            return
    else:
        manifest = {
            "apiVersion": "v1",
            "kind": "PersistentVolumeClaim",
            "metadata": {
                "name": pvc_name,
                "namespace": namespace,
            },
            "spec": {
                "accessModes": ["ReadWriteOnce"],
                "resources": {"requests": {"storage": size}},
                "storageClassName": config.OPENSHIFT_STORAGE_CLASS,
                "volumeMode": "Filesystem",
            },
        }
        data = json.dumps(manifest)
        process = subprocess.Popen(
            ["oc", "apply", "-f", "-"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        apply_out, apply_err = process.communicate(input=data)
        if process.returncode != 0:
            raise RuntimeError(f"Unable to create PVC '{pvc_name}': {apply_err or apply_out}")

    code, out, err = _run([
        "oc", "wait",
        f"--for=jsonpath={{.status.phase}}=Bound",
        f"pvc/{pvc_name}",
        "-n", namespace,
        "--timeout=180s",
    ])
    if code != 0:
        raise RuntimeError(f"PVC '{pvc_name}' was not bound in time: {err or out}")


def convert_disk_if_needed(source_path: str, source_format: str, progress_callback: ProgressCallback | None = None) -> str:
    source_format = (source_format or "").lower()
    if source_format in ("qcow2", "raw"):
        return source_path

    # Keep qcow2 as the normalized intermediate format for uploads.
    target_path = _build_converted_target_path(source_path, "qcow2")

    cmd = [
        "qemu-img", "convert",
        "-p",
        "-O", "qcow2",
        source_path,
        target_path
    ]
    code, out, err = _run_qemu_convert_with_progress(cmd, progress_callback=progress_callback)
    if code != 0:
        raise RuntimeError(f"Disk conversion failed: {err or out}")
    return target_path


def normalize_disk_for_http_import(source_path: str, source_format: str, progress_callback: ProgressCallback | None = None) -> str:
    normalized_format = (source_format or "").lower()
    if normalized_format == "qcow2":
        source = Path(source_path)
        data_dir = Path(config.DATA_DIR).resolve()
        try:
            if source.resolve().is_relative_to(data_dir):
                return str(source.resolve())
        except Exception:
            pass

    target_path = _build_import_target_path(source_path)
    cmd = [
        "qemu-img", "convert",
        "-p",
        "-O", "qcow2",
        source_path,
        target_path
    ]
    code, out, err = _run_qemu_convert_with_progress(cmd, progress_callback=progress_callback)
    if code != 0:
        raise RuntimeError(f"Disk normalization failed: {err or out}")
    return target_path


def upload_disk(image_path: str, pvc_name: str, size: str, namespace: str) -> UploadResult:
    uploadproxy_url = get_uploadproxy_url()
    effective_size = resolve_upload_size(image_path, size)
    ensure_upload_pvc(namespace, pvc_name, effective_size)
    cmd = [
        "virtctl", "image-upload",
        "pvc", pvc_name,
        "--no-create",
        "--namespace", namespace,
        "--image-path", image_path,
        "--size", effective_size,
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
        size=effective_size,
        uploadproxy_url=uploadproxy_url
    )


def build_import_url(image_path: str) -> str:
    base_url = get_import_base_url()
    filename = quote(Path(image_path).name, safe="")
    return f"{base_url}/api/v1/openshift/imports/{filename}"


def delete_datasource_if_exists(namespace: str, dv_name: str) -> None:
    _run(["oc", "delete", "dv", dv_name, "-n", namespace, "--ignore-not-found=true"])
    _run(["oc", "delete", "vm", dv_name, "-n", namespace, "--ignore-not-found=true"])


def create_data_volume_http(image_path: str, dv_name: str, size: str, namespace: str) -> DataVolumeResult:
    effective_size = resolve_upload_size(image_path, size)
    import_url = build_import_url(image_path)
    manifest = {
        "apiVersion": "cdi.kubevirt.io/v1beta1",
        "kind": "DataVolume",
        "metadata": {
            "name": dv_name,
            "namespace": namespace,
        },
        "spec": {
            "source": {
                "http": {
                    "url": import_url
                }
            },
            "storage": {
                "accessModes": ["ReadWriteOnce"],
                "resources": {
                    "requests": {
                        "storage": effective_size
                    }
                },
                "storageClassName": config.OPENSHIFT_STORAGE_CLASS,
                "volumeMode": "Filesystem",
            }
        }
    }
    data = json.dumps(manifest)
    process = subprocess.Popen(
        ["oc", "apply", "-f", "-"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )
    out, err = process.communicate(input=data)
    if process.returncode != 0:
        raise RuntimeError(f"DataVolume apply failed: {err or out}")
    return DataVolumeResult(
        dv_name=dv_name,
        pvc_name=dv_name,
        namespace=namespace,
        image_path=image_path,
        size=effective_size,
        import_url=import_url
    )


def wait_for_data_volume(
    namespace: str,
    dv_name: str,
    timeout_seconds: int = 900,
    progress_callback: ProgressCallback | None = None
) -> Dict:
    deadline = time.time() + timeout_seconds
    pending_deadline = time.time() + min(timeout_seconds, 120)
    last_phase = ""
    last_progress = ""
    while time.time() < deadline:
        code, out, err = _run(["oc", "get", "dv", dv_name, "-n", namespace, "-o", "json"])
        if code != 0:
            time.sleep(2)
            continue
        try:
            payload = json.loads(out)
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"Invalid DataVolume status output: {exc}") from exc
        status = payload.get("status", {})
        phase = status.get("phase", "")
        progress = status.get("progress", "")
        if progress_callback:
            if phase and phase != last_phase:
                progress_callback(f"Import phase: {phase}")
            if progress and progress != last_progress:
                progress_callback(f"Import progress: {progress}")
        if phase == "Succeeded":
            return payload
        if phase in {"Failed", "Unknown"}:
            raise RuntimeError(f"DataVolume '{dv_name}' failed with phase '{phase}' and progress '{progress or 'N/A'}'.")
        if phase in {"Pending", "PendingPopulation", "ImportScheduled"} and time.time() >= pending_deadline:
            blocker = _diagnose_dv_blocker(namespace, dv_name, payload)
            if blocker:
                raise RuntimeError(
                    f"DataVolume '{dv_name}' is blocked in phase '{phase}': {blocker}"
                )
        last_phase = phase or last_phase
        last_progress = progress or last_progress
        time.sleep(2)
    raise RuntimeError(
        f"Timed out waiting for DataVolume '{dv_name}' to succeed. Last phase: '{last_phase or 'unknown'}', progress: '{last_progress or 'N/A'}'."
    )


def _resolve_firmware(firmware: str, source_path: str = "") -> str:
    requested = (firmware or "auto").lower()
    if requested not in SUPPORTED_BOOT_FIRMWARE:
        raise ValueError(f"Unsupported firmware '{firmware}'. Use auto, bios or uefi.")

    if requested in {"uefi", "efi"}:
        return "efi"
    if requested == "bios":
        return "bios"

    # auto: use a conservative default, but honor clear hints in filenames.
    source_hint = Path(source_path or "").name.lower()
    if "uefi" in source_hint or "efi" in source_hint:
        return "efi"
    return "bios"


def _resolve_disk_bus(disk_bus: str, source_format: str = "") -> str:
    requested = (disk_bus or "auto").lower()
    if requested not in SUPPORTED_DISK_BUS:
        raise ValueError(f"Unsupported disk bus '{disk_bus}'. Use auto, sata, scsi or virtio.")

    if requested != "auto":
        return requested

    # Compatibility-first default for first boot after import.
    source_fmt = (source_format or "").lower()
    if source_fmt in {"vmdk", "vhd", "vhdx"}:
        return "sata"
    return "sata"


def _build_disk_device(name: str, disk_bus: str) -> Dict:
    return {
        "name": name,
        "bootOrder": 1,
        "disk": {"bus": disk_bus}
    }


def build_vm_manifest(
    vm_name: str,
    namespace: str,
    pvc_name: str,
    memory: str,
    cpu_cores: int,
    firmware: str = "auto",
    disk_bus: str = "auto",
    source_path: str = "",
    source_format: str = ""
) -> Dict:
    resolved_firmware = _resolve_firmware(firmware, source_path)
    resolved_disk_bus = _resolve_disk_bus(disk_bus, source_format)
    bootloader = {"bios": {}} if resolved_firmware == "bios" else {"efi": {"secureBoot": False}}

    return {
        "apiVersion": "kubevirt.io/v1",
        "kind": "VirtualMachine",
        "metadata": {
            "name": vm_name,
            "namespace": namespace
        },
        "spec": {
            "runStrategy": "Always",
            "template": {
                "metadata": {"labels": {"kubevirt.io/domain": vm_name}},
                "spec": {
                    "terminationGracePeriodSeconds": 0,
                    "domain": {
                        "machine": {"type": "q35"},
                        "cpu": {"cores": cpu_cores},
                        "resources": {"requests": {"memory": memory}},
                        "devices": {
                            "autoattachSerialConsole": True,
                            "rng": {},
                            "disks": [
                                _build_disk_device("rootdisk", resolved_disk_bus)
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
