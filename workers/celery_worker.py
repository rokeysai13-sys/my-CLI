"""
workers/celery_worker.py — Async task queue
Install: pip install celery redis
Start Redis: docker run -d -p 6379:6379 redis
Start worker: celery -A workers.celery_worker worker --loglevel=info
"""
from core.logger import logger
import os, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from celery import Celery
    from celery.utils.log import get_task_logger
    CELERY_OK = True
except ImportError:
    CELERY_OK = False
    logger.info("[QUEUE] celery not installed — pip install celery redis")

from config.loader import cfg

REDIS_URL = os.getenv("REDIS_URL", cfg("queue", "redis_url", default="redis://localhost:6379/0"))

if CELERY_OK:
    app = Celery("kirannn", broker=REDIS_URL, backend=REDIS_URL)
    app.conf.update(
        task_serializer="json",
        result_serializer="json",
        accept_content=["json"],
        task_track_started=True,
        task_acks_late=True,
        worker_prefetch_multiplier=1,
        task_soft_time_limit=cfg("queue", "task_timeout", default=300),
        task_time_limit=cfg("queue", "task_timeout", default=300) + 30,
        task_max_retries=cfg("queue", "max_retries", default=3),
        task_default_retry_delay=cfg("queue", "retry_delay", default=5),
    )
    logger = get_task_logger(__name__)

    # ── Task definitions ──────────────────────────────────────────────────────

    @app.task(bind=True, name="run_agent_task", max_retries=3)
    def run_agent_task(self, message: str, model: str = None, session_id: str = None):
        """Run master agent as background task."""
        try:
            from core.agent import run_agent
            from config.loader import MODEL_FALLBACK
            result = run_agent(message, model=model or MODEL_FALLBACK(), session_id=session_id)
            return {"status": "complete", "result": result}
        except Exception as e:
            logger.error(f"Agent task failed: {e}")
            raise self.retry(exc=e, countdown=cfg("queue","retry_delay",default=5))

    @app.task(bind=True, name="run_pipeline_task", max_retries=2)
    def run_pipeline_task(self, goal: str, model: str = None):
        """Run full planning pipeline as background task."""
        try:
            from core.agent import run_full_pipeline
            from config.loader import MODEL_PLAN
            result = run_full_pipeline(goal, model=model or MODEL_PLAN())
            return {"status": "complete", "result": result}
        except Exception as e:
            logger.error(f"Pipeline task failed: {e}")
            raise self.retry(exc=e)

    @app.task(bind=True, name="run_research_task", max_retries=2)
    def run_research_task(self, query: str):
        """Run research agent as background task."""
        try:
            from core.agent import run_research_agent
            result = run_research_agent(query)
            return {"status": "complete", "result": result}
        except Exception as e:
            raise self.retry(exc=e)

    @app.task(name="ingest_document_task")
    def ingest_document_task(path_or_url: str):
        """Ingest a document into RAG system."""
        try:
            from core.rag import ingest_file, ingest_url
            if path_or_url.startswith("http"):
                return ingest_url(path_or_url)
            return ingest_file(path_or_url)
        except Exception as e:
            return {"success": False, "error": str(e)}

    @app.task(name="memory_cleanup_task")
    def memory_cleanup_task():
        """Periodic memory cleanup and summarization."""
        try:
            from memory.vector_store import memory_stats
            stats = memory_stats()
            return {"status": "complete", "stats": stats}
        except Exception as e:
            return {"status": "error", "error": str(e)}

    @app.task(name="health_check_task")
    def health_check_task():
        """Background health check."""
        import requests as req
        results = {}
        for name, url in [
            ("ollama", "http://localhost:11434/api/tags"),
            ("api", "http://localhost:8000/health")
        ]:
            try:
                r = req.get(url, timeout=5)
                results[name] = "ok"
            except:
                results[name] = "offline"
        return results


# ── Task submission helpers (used by FastAPI) ─────────────────────────────────

def submit_agent_task(message: str, session_id: str = None, priority: int = 5) -> dict:
    """Submit agent task to queue. Returns task ID."""
    if not CELERY_OK:
        return {"queue": False, "error": "celery not installed"}
    try:
        task = run_agent_task.apply_async(
            args=[message],
            kwargs={"session_id": session_id},
            priority=priority
        )
        return {"queued": True, "task_id": task.id, "status": "pending"}
    except Exception as e:
        return {"queued": False, "error": str(e)}


def get_task_status(task_id: str) -> dict:
    """Check status of a queued task."""
    if not CELERY_OK:
        return {"error": "celery not installed"}
    try:
        from celery.result import AsyncResult
        result = AsyncResult(task_id, app=app)
        return {
            "task_id": task_id,
            "status": result.status,
            "result": result.result if result.ready() else None,
            "ready": result.ready()
        }
    except Exception as e:
        return {"error": str(e)}


if __name__ == "__main__":
    if CELERY_OK:
        app.start()
    else:
        logger.info("Install celery and redis first:")
        logger.info("  pip install celery redis")
        logger.info("  docker run -d -p 6379:6379 redis")