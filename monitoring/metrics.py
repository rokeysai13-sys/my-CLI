"""
monitoring/metrics.py — Prometheus metrics + structured logging
Install: pip install prometheus-client
Expose: GET /metrics
"""
import time, logging, datetime, os
from pathlib import Path
from config.loader import cfg

# ── Logging setup ─────────────────────────────────────────────────────────────
LOG_FILE = cfg("monitoring", "log_file", default=str(Path(__file__).parent.parent.resolve() / "logs" / "kirannn.log"))
LOG_DIR  = Path(LOG_FILE).parent
LOG_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=getattr(logging, cfg("system", "log_level", default="INFO")),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(LOG_FILE, encoding="utf-8")
    ]
)
logger = logging.getLogger("kirannn")


# ── Prometheus metrics ─────────────────────────────────────────────────────────
try:
    from prometheus_client import (Counter, Histogram, Gauge, 
                                    generate_latest, CONTENT_TYPE_LATEST,
                                    CollectorRegistry)
    PROM_OK = True
    registry = CollectorRegistry()

    # Counters
    requests_total = Counter(
        "kirannn_requests_total", "Total API requests",
        ["endpoint", "method", "status"], registry=registry
    )
    agent_runs_total = Counter(
        "kirannn_agent_runs_total", "Total agent runs",
        ["agent_type", "status"], registry=registry
    )
    tool_calls_total = Counter(
        "kirannn_tool_calls_total", "Total tool calls",
        ["tool_name", "success"], registry=registry
    )
    errors_total = Counter(
        "kirannn_errors_total", "Total errors",
        ["error_type"], registry=registry
    )

    # Histograms (latency)
    request_latency = Histogram(
        "kirannn_request_duration_seconds", "Request latency",
        ["endpoint"], registry=registry
    )
    agent_latency = Histogram(
        "kirannn_agent_duration_seconds", "Agent execution time",
        ["agent_type"], registry=registry
    )
    model_latency = Histogram(
        "kirannn_model_duration_seconds", "Model response time",
        ["model"], registry=registry
    )

    # Gauges (current state)
    active_tasks = Gauge(
        "kirannn_active_tasks", "Currently active tasks", registry=registry
    )
    memory_entries = Gauge(
        "kirannn_memory_entries", "Memory entries in vector store",
        ["collection"], registry=registry
    )
    cpu_usage = Gauge("kirannn_cpu_percent", "CPU usage %", registry=registry)
    ram_usage = Gauge("kirannn_ram_percent", "RAM usage %", registry=registry)

except ImportError:
    PROM_OK = False
    logger.warning("prometheus-client not installed — metrics disabled")


# ── Simple in-memory stats (always available) ─────────────────────────────────
_stats = {
    "requests": 0,
    "errors": 0,
    "agent_runs": {},
    "tool_calls": {},
    "start_time": datetime.datetime.now().isoformat(),
}


def record_request(endpoint: str, method: str = "GET", status: int = 200,
                   duration: float = 0):
    _stats["requests"] += 1
    if PROM_OK:
        requests_total.labels(endpoint=endpoint, method=method, status=str(status)).inc()
        request_latency.labels(endpoint=endpoint).observe(duration)


def record_agent_run(agent_type: str, success: bool, duration: float = 0):
    _stats["agent_runs"][agent_type] = _stats["agent_runs"].get(agent_type, 0) + 1
    if PROM_OK:
        agent_runs_total.labels(agent_type=agent_type, status="ok" if success else "fail").inc()
        agent_latency.labels(agent_type=agent_type).observe(duration)
    logger.info(f"Agent run: {agent_type} — {'ok' if success else 'fail'} ({duration:.2f}s)")


def record_tool_call(tool_name: str, success: bool):
    _stats["tool_calls"][tool_name] = _stats["tool_calls"].get(tool_name, 0) + 1
    if PROM_OK:
        tool_calls_total.labels(tool_name=tool_name, success=str(success)).inc()


def record_model_call(model: str, duration: float):
    if PROM_OK:
        model_latency.labels(model=model).observe(duration)


def record_error(error_type: str, message: str = ""):
    _stats["errors"] += 1
    if PROM_OK:
        errors_total.labels(error_type=error_type).inc()
    logger.error(f"Error [{error_type}]: {message}")


def update_system_metrics():
    """Update CPU/RAM gauges."""
    if not PROM_OK:
        return
    try:
        import psutil
        cpu_usage.set(psutil.cpu_percent())
        ram_usage.set(psutil.virtual_memory().percent)
    except ImportError:
        pass


def get_metrics_text() -> bytes:
    """Return Prometheus metrics as text."""
    if PROM_OK:
        update_system_metrics()
        return generate_latest(registry)
    return b"# prometheus-client not installed\n"


def get_stats() -> dict:
    """Return simple stats dict."""
    try:
        import psutil
        sys_stats = {
            "cpu_percent": psutil.cpu_percent(),
            "ram_percent": psutil.virtual_memory().percent,
            "ram_gb": round(psutil.virtual_memory().used / 1e9, 2)
        }
    except:
        sys_stats = {}
    return {**_stats, "system": sys_stats, "prometheus": PROM_OK}


# ── Timing context manager ────────────────────────────────────────────────────
class Timer:
    """Context manager for timing operations."""
    def __init__(self, name: str = "operation"):
        self.name = name
        self.elapsed = 0

    def __enter__(self):
        self._start = time.time()
        return self

    def __exit__(self, *args):
        self.elapsed = time.time() - self._start
        logger.debug(f"Timer [{self.name}]: {self.elapsed:.3f}s")