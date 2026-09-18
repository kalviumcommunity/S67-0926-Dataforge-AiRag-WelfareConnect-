"""
Background job dispatcher and task queue abstractions.
Supports asynchronous document indexing and task status tracking.
"""

from typing import Any, Callable, Dict, Optional
import uuid
from backend.app.workers.document_processor import DocumentProcessor


class TaskQueue:
    """In-process and Redis-compatible task queue interface."""

    def __init__(self):
        self.tasks: Dict[str, Dict[str, Any]] = {}

    def enqueue(
        self,
        task_name: str,
        func: Callable,
        *args,
        **kwargs
    ) -> str:
        """Enqueue a background execution job."""
        job_id = f"job-{uuid.uuid4()}"
        self.tasks[job_id] = {
            "id": job_id,
            "name": task_name,
            "status": "QUEUED",
            "result": None,
            "error": None,
        }
        # In background workers / dev mode, execution can be synchronous or async
        try:
            self.tasks[job_id]["status"] = "RUNNING"
            res = func(*args, **kwargs)
            self.tasks[job_id]["status"] = "COMPLETED"
            self.tasks[job_id]["result"] = res
        except Exception as e:
            self.tasks[job_id]["status"] = "FAILED"
            self.tasks[job_id]["error"] = str(e)

        return job_id

    def get_status(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Get status of an enqueued job."""
        return self.tasks.get(job_id)


task_queue = TaskQueue()
