"""
Orchestration de la migration
"""

from typing import Dict
import threading
import time

from src.monitoring.job_store import job_store

def start_migration(vm_details: Dict, analysis: Dict, conversion_plan: Dict, strategy: Dict) -> Dict:
    """Demarre une migration simulee et retourne le job."""
    plan = {
        "analysis": analysis,
        "conversion_plan": conversion_plan,
        "strategy": strategy
    }

    job = job_store.create_job(vm_details.get("name", "unknown"), plan)

    if strategy.get("strategy") == "alternative":
        job_store.update_status(job.job_id, "blocked", "Migration alternative requise.")
        return _job_to_dict(job)

    thread = threading.Thread(
        target=_simulate_job,
        args=(job.job_id, conversion_plan),
        daemon=True
    )
    thread.start()
    return _job_to_dict(job)

def _simulate_job(job_id: str, conversion_plan: Dict) -> None:
    steps = ["discovery", "analysis"]
    if conversion_plan.get("actions"):
        steps.append("conversion")
    steps.extend(["transfer", "verify"])

    job_store.update_status(job_id, "running")

    for step in steps:
        job_store.add_step(job_id, step, "running")
        time.sleep(0.2)
        job_store.finish_last_step(job_id, "completed")

    job_store.update_status(job_id, "completed")

def _job_to_dict(job) -> Dict:
    return {
        "job_id": job.job_id,
        "vm_name": job.vm_name,
        "status": job.status,
        "created_at": job.created_at,
        "updated_at": job.updated_at,
        "plan": job.plan,
        "steps": job.steps,
        "error": job.error
    }
