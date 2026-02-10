"""
Helper functions for job management.
"""
from typing import Optional, Dict, Any
from fastapi import HTTPException


def extract_task_id_from_job_id(job_id: str) -> str:
    """
    Extract task_id from job_id.

    Format: {task_id}_job_{counter}
    Example:
        "praat_abc123_job_1" → "praat_abc123"
        "praat_abc123_job_2" → "praat_abc123"

    Args:
        job_id: Job ID

    Returns:
        Task ID

    Raises:
        HTTPException: If job_id format is invalid
    """
    if "_job_" not in job_id:
        raise HTTPException(400, f"Invalid job_id format: {job_id}")

    parts = job_id.rsplit("_job_", 1)
    return parts[0]


def find_job_by_id(task: dict, job_id: str) -> Optional[dict]:
    """
    Find a job from task's data.jobs.

    Args:
        task: Task dictionary
        job_id: Job ID to find

    Returns:
        Job dict if found, None otherwise
    """
    for job in task.get('data', {}).get('jobs', []):
        if job['job_id'] == job_id:
            return job
    return None


def update_job_status(task_manager, task_id: str, job_id: str, **updates):
    """
    Update job status (helper function).

    Args:
        task_manager: TaskManager instance
        task_id: Task ID
        job_id: Job ID
        **updates: Fields to update (status, progress, stage, error, etc.)

    Example:
        update_job_status(
            task_manager,
            "praat_abc123",
            "praat_abc123_job_1",
            status="running",
            progress=0.5,
            stage="formant"
        )

    Raises:
        Exception: If task or job not found
    """
    from datetime import datetime

    task = task_manager.get_task(task_id)
    if not task:
        raise Exception(f"Task not found: {task_id}")

    # Find job and update
    job_found = False
    for job in task.get('data', {}).get('jobs', []):
        if job['job_id'] == job_id:
            for key, value in updates.items():
                job[key] = value
            job['updated_at'] = datetime.now().isoformat()
            job_found = True
            break

    if not job_found:
        raise Exception(f"Job not found: {job_id}")

    # Write back to file
    task_manager.update_task(task_id, data=task['data'])
