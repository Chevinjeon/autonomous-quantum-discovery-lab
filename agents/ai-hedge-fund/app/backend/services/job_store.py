"""In-memory job store for async hedge fund analysis jobs."""

import asyncio
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from enum import Enum


class JobStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETE = "complete"
    ERROR = "error"
    CANCELLED = "cancelled"


@dataclass
class ProgressEvent:
    index: int
    type: str  # "start", "progress", "complete", "error"
    data: Dict[str, Any]
    timestamp: float = field(default_factory=time.time)


@dataclass
class Job:
    job_id: str
    status: JobStatus = JobStatus.PENDING
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    events: List[ProgressEvent] = field(default_factory=list)
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    task: Optional[asyncio.Task] = None

    def add_event(self, event_type: str, data: Dict[str, Any]) -> int:
        idx = len(self.events)
        self.events.append(ProgressEvent(index=idx, type=event_type, data=data))
        self.updated_at = time.time()
        return idx


class JobStore:
    def __init__(self, ttl_seconds: int = 3600):
        self._jobs: Dict[str, Job] = {}
        self.ttl_seconds = ttl_seconds

    def create_job(self) -> Job:
        self.cleanup_old_jobs()
        job_id = uuid.uuid4().hex[:12]
        job = Job(job_id=job_id)
        self._jobs[job_id] = job
        return job

    def get_job(self, job_id: str) -> Optional[Job]:
        return self._jobs.get(job_id)

    def get_events_after(self, job_id: str, after: int = -1) -> Optional[List[ProgressEvent]]:
        job = self._jobs.get(job_id)
        if job is None:
            return None
        return [e for e in job.events if e.index > after]

    def cancel_job(self, job_id: str) -> bool:
        job = self._jobs.get(job_id)
        if job is None:
            return False
        if job.task and not job.task.done():
            job.task.cancel()
        job.status = JobStatus.CANCELLED
        job.updated_at = time.time()
        return True

    def cleanup_old_jobs(self):
        now = time.time()
        to_remove = [
            jid for jid, j in self._jobs.items()
            if j.status in (JobStatus.COMPLETE, JobStatus.ERROR, JobStatus.CANCELLED)
            and (now - j.updated_at) > self.ttl_seconds
        ]
        for jid in to_remove:
            del self._jobs[jid]


job_store = JobStore()
