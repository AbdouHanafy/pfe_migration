"""
Reporting des migrations
"""

from typing import Dict
from datetime import datetime

from src.monitoring.job_store import MigrationJob

def build_report(job: MigrationJob) -> Dict:
    """Construit un rapport simple de migration."""
    return {
        "job_id": job.job_id,
        "vm_name": job.vm_name,
        "status": job.status,
        "created_at": job.created_at,
        "updated_at": job.updated_at,
        "error": job.error,
        "steps": job.steps,
        "analysis": job.plan.get("analysis", {}),
        "conversion_plan": job.plan.get("conversion_plan", {}),
        "strategy": job.plan.get("strategy", {})
    }
