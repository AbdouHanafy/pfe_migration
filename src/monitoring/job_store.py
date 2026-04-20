"""
Stockage en memoire des jobs de migration
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional
import threading
import uuid

def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

@dataclass
class MigrationJob:
    job_id: str
    vm_name: str
    status: str
    created_at: str
    updated_at: str
    plan: Dict = field(default_factory=dict)
    steps: List[Dict] = field(default_factory=list)
    logs: List[Dict] = field(default_factory=list)
    error: Optional[str] = None

class JobStore:
    """Stocke les jobs de migration en memoire."""
    def __init__(self) -> None:
        self._jobs: Dict[str, MigrationJob] = {}
        self._lock = threading.Lock()

    def create_job(self, vm_name: str, plan: Dict) -> MigrationJob:
        job_id = str(uuid.uuid4())
        now = _now_iso()
        job = MigrationJob(
            job_id=job_id,
            vm_name=vm_name,
            status="queued",
            created_at=now,
            updated_at=now,
            plan=plan,
            steps=[],
            logs=[]
        )
        with self._lock:
            self._jobs[job_id] = job
            job.logs.append({
                "timestamp": now,
                "level": "info",
                "message": f"Job queued for VM '{vm_name}'."
            })
        return job

    def get_job(self, job_id: str) -> Optional[MigrationJob]:
        with self._lock:
            return self._jobs.get(job_id)

    def list_jobs(self) -> List[MigrationJob]:
        with self._lock:
            return list(self._jobs.values())

    def update_status(self, job_id: str, status: str, error: Optional[str] = None) -> None:
        with self._lock:
            job = self._jobs.get(job_id)
            if not job:
                return
            job.status = status
            now = _now_iso()
            job.updated_at = now
            job.logs.append({
                "timestamp": now,
                "level": "error" if error else "info",
                "message": f"Job status changed to '{status}'." + (f" Error: {error}" if error else "")
            })
            if error:
                job.error = error

    def add_step(self, job_id: str, name: str, status: str) -> None:
        with self._lock:
            job = self._jobs.get(job_id)
            if not job:
                return
            now = _now_iso()
            job.steps.append({
                "name": name,
                "status": status,
                "started_at": now,
                "ended_at": None,
                "logs": []
            })
            job.updated_at = now
            job.logs.append({
                "timestamp": now,
                "level": "info",
                "message": f"Step '{name}' started."
            })

    def finish_last_step(self, job_id: str, status: str) -> None:
        with self._lock:
            job = self._jobs.get(job_id)
            if not job or not job.steps:
                return
            now = _now_iso()
            job.steps[-1]["status"] = status
            job.steps[-1]["ended_at"] = now
            job.updated_at = now
            job.logs.append({
                "timestamp": now,
                "level": "info" if status == "completed" else "error",
                "message": f"Step '{job.steps[-1]['name']}' finished with status '{status}'."
            })

    def add_log(self, job_id: str, message: str, level: str = "info") -> None:
        with self._lock:
            job = self._jobs.get(job_id)
            if not job:
                return
            now = _now_iso()
            entry = {
                "timestamp": now,
                "level": level,
                "message": message
            }
            job.logs.append(entry)
            if job.steps:
                job.steps[-1].setdefault("logs", []).append(entry)
            job.updated_at = now

job_store = JobStore()
