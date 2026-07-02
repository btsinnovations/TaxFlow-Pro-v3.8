"""Lightweight in-process report queue for TaxFlow Pro v3.11.6.

Provides asynchronous report generation with bounded concurrency and
backpressure. Reports run in a background thread pool; callers receive a
job ID and poll for completion.

This is intentionally lightweight (no Celery/RQ dependency) so the packaged
app remains self-contained. For high-volume multi-server deployments, swap
this module for a broker-backed worker pool.
"""
from __future__ import annotations

import threading
import uuid
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Dict, Optional


class JobStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class ReportJob:
    id: str
    report_type: str
    status: JobStatus = JobStatus.PENDING
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    result: Any = None
    error: Optional[str] = None


class ReportQueue:
    """Bounded in-process report queue.

    ``max_workers`` controls concurrency. ``max_queue`` controls the number
    of *pending* jobs accepted beyond ``max_workers``; additional submits
    raise ``QueueFull`` immediately (backpressure).
    """

    class QueueFull(Exception):
        """Raised when the pending queue is at capacity."""

    def __init__(self, max_workers: int = 4, max_pending: int = 20) -> None:
        self.max_workers = max_workers
        self.max_pending = max_pending
        self._jobs: Dict[str, ReportJob] = {}
        self._lock = threading.Lock()
        self._executor = ThreadPoolExecutor(
            max_workers=max_workers,
            thread_name_prefix="taxflow-report-",
        )
        self._semaphore = threading.Semaphore(max_pending + max_workers)

    def submit(
        self,
        report_type: str,
        func: Callable[..., Any],
        *args: Any,
        **kwargs: Any,
    ) -> str:
        """Submit a report job. Returns the job ID.

        Raises ``QueueFull`` if the queue has reached its configured capacity.
        """
        if not self._semaphore.acquire(blocking=False):
            raise self.QueueFull(
                f"Report queue is at capacity ({self.max_workers} running + "
                f"{self.max_pending} pending). Try again later."
            )

        job_id = str(uuid.uuid4())
        job = ReportJob(id=job_id, report_type=report_type)
        with self._lock:
            self._jobs[job_id] = job

        def _run() -> Any:
            job.started_at = datetime.now(timezone.utc)
            job.status = JobStatus.RUNNING
            try:
                result = func(*args, **kwargs)
                job.result = result
                job.status = JobStatus.COMPLETED
            except Exception as exc:  # noqa: BLE001
                job.error = str(exc)
                job.status = JobStatus.FAILED
            finally:
                job.completed_at = datetime.now(timezone.utc)
                self._semaphore.release()
            return job

        # Submit through the executor so *running* jobs are bounded by
        # max_workers. The semaphore guards total in-flight + pending.
        self._executor.submit(_run)
        return job_id

    def get(self, job_id: str) -> Optional[ReportJob]:
        """Return a copy of the job record, or None if not found."""
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                return None
            # Return a shallow copy to avoid external mutation.
            return ReportJob(
                id=job.id,
                report_type=job.report_type,
                status=job.status,
                created_at=job.created_at,
                started_at=job.started_at,
                completed_at=job.completed_at,
                result=job.result,
                error=job.error,
            )

    def list_jobs(
        self,
        limit: int = 100,
        status: Optional[JobStatus] = None,
    ) -> list[ReportJob]:
        """Return recent jobs, optionally filtered by status."""
        with self._lock:
            jobs = list(self._jobs.values())
        jobs.sort(key=lambda j: j.created_at, reverse=True)
        if status is not None:
            jobs = [j for j in jobs if j.status == status]
        return jobs[:limit]

    def shutdown(self, wait: bool = True) -> None:
        """Shutdown the executor. Called automatically on process exit."""
        self._executor.shutdown(wait=wait)


# Module-level singleton queue used by the reports router.
DEFAULT_QUEUE = ReportQueue(max_workers=4, max_pending=20)
