"""
api/server.py — kirannn Production FastAPI Server v3
Streaming, auth, rate limiting, metrics, task queue, RAG, all agents
REPLACE your existing api/server.py with this file.
"""
from core.logger import logger
from core.agents.roles import security_agent
import os, sys, time, datetime
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from fastapi import FastAPI, HTTPException, Request, Depends, Header
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, StreamingResponse, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from pydantic import BaseModel, field_validator
from contextlib import asynccontextmanager
from typing import Optional, Any

from config.loader import cfg
from monitoring.metrics import record_request, record_agent_run, record_error, get_metrics_text, get_stats, Timer

BASE = Path(__file__).parent.parent

# ── Response cache ─────────────────────────────────────────────────────────────
_cache: dict = {}
_cache_ttl = cfg("cache", "ttl", default=3600)
_cache_max = cfg("cache", "max_size", default=500)

def _cache_get(key: str):
    if not cfg("cache", "enabled", default=True): return None
    entry = _cache.get(key)
    if entry and (time.time() - entry["ts"]) < _cache_ttl:
        return entry["val"]
    return None

def _cache_set(key: str, val):
    if len(_cache) >= _cache_max:
        oldest = min(_cache, key=lambda k: _cache[k]["ts"])
        del _cache[oldest]
    _cache[key] = {"val": val, "ts": time.time()}

# ── Rate limiter ───────────────────────────────────────────────────────────────
_rate_counts: dict = {}
_rate_limit = cfg("security", "rate_limit", default=60)

def _check_rate(ip: str) -> bool:
    now = int(time.time() // 60)
    key = f"{ip}:{now}"
    _rate_counts[key] = _rate_counts.get(key, 0) + 1
    return _rate_counts[key] <= _rate_limit

# ── Lifespan ───────────────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("[*] kirannn v3 starting up...")
    # Database initialization and migration
    try:
        from database import init_db
        init_db()
    except Exception as e:
        logger.error(f"[ERROR] Database init/migration failed: {e}")
    # Heartbeat
    try:
        from core.heartbeat import start_heartbeat
        start_heartbeat(30)
    except Exception as e:
        logger.warning(f"[WARNING] Heartbeat: {e}")
    # Watchdog
    try:
        from core.watchdog import start_watchdog
        start_watchdog(60)
    except Exception as e:
        logger.warning(f"[WARNING] Watchdog: {e}")
    # Autonomous Mode
    try:
        from core.autonomous import start_autonomous_mode
        start_autonomous_mode()
    except Exception as e:
        logger.error(f"[ERROR] Autonomous mode start failed: {e}")
    yield
    logger.info("kirannn shutting down.")

app = FastAPI(title="kirannn", version="3.0.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
app.add_middleware(GZipMiddleware, minimum_size=1000)

if (BASE/"index.html").exists():
    app.mount("/static", StaticFiles(directory=str(BASE)), name="static")

# ── Request middleware ────────────────────────────────────────────────────────
@app.middleware("http")
async def middleware(request: Request, call_next):
    start = time.time()
    ip = request.client.host if request.client else "unknown"

    # Rate limiting
    if not _check_rate(ip):
        return Response("Rate limit exceeded", status_code=429)

    response = await call_next(request)
    duration = time.time() - start
    record_request(request.url.path, request.method, response.status_code, duration)
    return response

# ── Auth dependency ───────────────────────────────────────────────────────────
async def verify_api_key(x_api_key: Optional[str] = Header(None)):
    if not cfg("security", "api_key_enabled", default=False):
        return True
    expected = cfg("security", "api_key", default="")
    if not expected or x_api_key == expected:
        return True
    raise HTTPException(status_code=401, detail="Invalid API key")

# ── Pydantic models ───────────────────────────────────────────────────────────
class ChatReq(BaseModel):
    message: str
    session_id: str = "default"
    model: str = None
    stream: bool = False

    @field_validator("message")
    @classmethod
    def validate_message(cls, v):
        max_len = cfg("security", "max_input_length", default=8000)
        if len(v) > max_len:
            raise ValueError(f"Message too long: {len(v)} > {max_len}")
            
        from core.security import sanitize_input, contains_suspicious_patterns
        v = sanitize_input(v)
        if contains_suspicious_patterns(v):
            from core.logger import logger
            logger.warning(f"Suspicious pattern detected in input: {v[:100]}")
            # We don't necessarily block, but we could raise ValueError
        return v

class PlanReq(BaseModel):
    goal: str
    model: str = None
    execute: bool = False
    mode: str = "standard"

class MissionReq(BaseModel):
    goal: str
    mode: str = "standard"

class ProjectReq(BaseModel):
    name: str
    repos: list = []
    context: str = ""

class ToolReq(BaseModel):
    tool: str
    args: dict = {}

class FileReq(BaseModel):
    path: str
    content: str = ""
    mode: str = "w"

class MemReq(BaseModel):
    entry: str
    section: str = "Recent Context"

class ShellReq(BaseModel):
    command: str
    cwd: str = None

class CodeReq(BaseModel):
    code: str
    language: str = "python"

class RAGIngestReq(BaseModel):
    path: str = None
    url: str = None

class TaskReq(BaseModel):
    message: str
    session_id: str = "default"
    priority: int = 5

class DomainReq(BaseModel):
    task_type: str
    data: Optional[Any] = None

# ── Core routes ───────────────────────────────────────────────────────────────

@app.get("/")
def root():
    p = BASE / "index.html"
    if p.exists():
        return FileResponse(str(p))
    return {"status": "running", "version": "3.0.0"}

@app.get("/health")
def health():
    import requests as req
    status = {"api": "ok", "version": "3.0.0", "ollama": "unknown", "models": []}
    
    # 1. Ollama status
    try:
        r = req.get("http://localhost:11434/api/tags", timeout=3)
        status["ollama"] = "ok"
        status["models"] = [m["name"] for m in r.json().get("models", [])]
    except:
        status["ollama"] = "offline"
        
    # 2. Vector DB memory status
    try:
        from memory.vector_store import memory_stats
        status["memory"] = memory_stats()
    except:
        status["memory"] = "unavailable"
        
    # 3. SQLite Database check
    try:
        import database
        db_stats = database.get_stats()
        status["database"] = {"status": "ok", "stats": db_stats}
    except Exception as e:
        status["database"] = {"status": "error", "error": str(e)}
        
    # 4. Redis broker connection check
    try:
        import redis
        from workers.celery_worker import REDIS_URL
        r_client = redis.from_url(REDIS_URL, socket_timeout=2)
        r_client.ping()
        status["redis"] = "ok"
    except Exception as e:
        status["redis"] = f"offline ({str(e)})"
        
    # 5. System metrics checking
    try:
        import psutil
        import shutil
        total, used, free = shutil.disk_usage("/")
        status["system"] = {
            "cpu_percent": psutil.cpu_percent(),
            "ram_percent": psutil.virtual_memory().percent,
            "disk_free_gb": round(free / (1024**3), 2)
        }
    except Exception as e:
        status["system"] = {"error": str(e)}
        
    return status

@app.get("/metrics")
def metrics():
    """Prometheus metrics endpoint."""
    content = get_metrics_text()
    return Response(content=content, media_type="text/plain; charset=utf-8")

@app.get("/stats")
def stats(auth=Depends(verify_api_key)):
    return get_stats()

# ── Chat endpoints ────────────────────────────────────────────────────────────

@app.post("/chat/agent")
def chat_agent(req: ChatReq, auth=Depends(verify_api_key)):
    sec = security_agent(req.message, "general")
    if not sec["safe"] and sec["risk_level"] == "critical":
        raise HTTPException(status_code=400, detail=f"Security check failed: {sec['issues']}")

    if req.stream:
        return _stream_response(req.message, req.model)

    # Cache check
    cache_key = f"agent:{req.message[:100]}"
    cached = _cache_get(cache_key)
    if cached:
        return {**cached, "cached": True}

    with Timer("agent") as t:
        from core.agent import run_agent
        from config.loader import MODEL_FALLBACK
        # RAG-enhanced prompt
        from core.rag import build_rag_prompt
        enhanced = build_rag_prompt(req.message, req.message, req.session_id)
        result = run_agent(enhanced, model=req.model or MODEL_FALLBACK(), session_id=req.session_id)

    record_agent_run("master", True, t.elapsed)

    # Store in memory
    try:
        from memory.vector_store import store_conversation, add_episodic_memory
        store_conversation(req.session_id, "user", req.message)
        store_conversation(req.session_id, "assistant", result.get("response",""))
        add_episodic_memory("master", req.message, result.get("response",""))
    except: pass

    _cache_set(cache_key, result)
    return result

def _stream_response(message: str, model: str = None):
    """Stream tokens as Server-Sent Events."""
    from core.retry import ollama_stream
    from config.loader import MODEL_FALLBACK
    import json

    def generate():
        yield f"data: {json.dumps({'type':'start'})}\n\n"
        full_response = ""
        for token in ollama_stream(message, model=model or MODEL_FALLBACK()):
            full_response += token
            yield f"data: {json.dumps({'type':'token','text':token})}\n\n"
        yield f"data: {json.dumps({'type':'done','full':full_response})}\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")

@app.post("/chat/debate")
def chat_debate(req: ChatReq, auth=Depends(verify_api_key)):
    from core.agent import run_debate
    return run_debate(req.message)

@app.post("/chat/code")
def chat_code(req: ChatReq, auth=Depends(verify_api_key)):
    from core.agent import run_code_agent
    return run_code_agent(req.message)

@app.post("/chat/research")
def chat_research(req: ChatReq, auth=Depends(verify_api_key)):
    with Timer("research") as t:
        from core.agent import run_research_agent
        result = run_research_agent(req.message)
    record_agent_run("research", True, t.elapsed)
    
    try:
        from memory.vector_store import add_episodic_memory
        add_episodic_memory("research", req.message, result.get("response",""))
    except: pass
    
    return result

@app.post("/chat/pipeline")
def chat_pipeline(req: ChatReq, auth=Depends(verify_api_key)):
    with Timer("pipeline") as t:
        from core.agent import run_full_pipeline
        from config.loader import MODEL_PLAN
        result = run_full_pipeline(req.message, model=req.model or MODEL_PLAN())
    record_agent_run("pipeline", True, t.elapsed)
    
    try:
        from memory.vector_store import add_episodic_memory
        add_episodic_memory("pipeline", req.message, str(result))
    except: pass
    
    return result

@app.post("/chat")
def chat(req: ChatReq, auth=Depends(verify_api_key)):
    return chat_agent(req, auth)

# ── Planner + critic ──────────────────────────────────────────────────────────

@app.post("/plan")
def plan(req: PlanReq, auth=Depends(verify_api_key)):
    if req.mode == "react":
        from core.planner_react import react_plan, execute_plan
        plan_res = react_plan(req.goal, model=req.model)
        if plan_res.get("status") == "error":
            return {"success": False, "error": plan_res.get("error")}
        result = {"success": True, "plan": plan_res}
        if req.execute:
            exec_result = execute_plan(plan_res)
            return {"plan": result, "execution": exec_result.get("execution")}
        return result
    else:
        from core.agents.roles import planner_agent
        from config.loader import MODEL_PLAN
        result = planner_agent(req.goal)
        if req.execute and result.get("success"):
            from core.subagents import orchestrate
            orch = orchestrate(result)
            return {"plan": result, "execution": orch}
        return result

@app.post("/critique")
def critique(task: str, result: str, auth=Depends(verify_api_key)):
    from core.agents.roles import critic_agent
    return critic_agent(task, result)

# ── Task queue ────────────────────────────────────────────────────────────────

@app.post("/tasks/submit")
def submit_task(req: TaskReq, auth=Depends(verify_api_key)):
    from workers.celery_worker import submit_agent_task
    return submit_agent_task(req.message, req.session_id, req.priority)

@app.get("/tasks/{task_id}")
def get_task(task_id: str, auth=Depends(verify_api_key)):
    from workers.celery_worker import get_task_status
    return get_task_status(task_id)

# ── Episodic Memory endpoints ───────────────────────────────────────────────────

@app.get("/memory/episodic/stats")
def memory_episodic_stats(auth=Depends(verify_api_key)):
    from memory.episodic import get_memory_stats
    return get_memory_stats()

@app.post("/memory/episodic/summarize")
def memory_episodic_summarize(session_id: str = "discord_123", username: str = "guest", auth=Depends(verify_api_key)):
    from memory.episodic import summarize_session
    return summarize_session(session_id, username)

# ── RAG endpoints ─────────────────────────────────────────────────────────────

@app.post("/rag/ingest")
def rag_ingest(req: RAGIngestReq, auth=Depends(verify_api_key)):
    from core.rag import ingest_file, ingest_url
    if req.url:
        return ingest_url(req.url)
    if req.path:
        return ingest_file(req.path)
    raise HTTPException(400, "Provide path or url")

@app.get("/rag/search")
def rag_search(q: str, n: int = 5, auth=Depends(verify_api_key)):
    from memory.vector_store import retrieve_for_rag
    return retrieve_for_rag(q, n)

# ── Tool endpoints ────────────────────────────────────────────────────────────

@app.post("/tool")
def run_tool(req: ToolReq, auth=Depends(verify_api_key)):
    from core.agents.roles import security_agent
    sec = security_agent(str(req.args), "tool_args")
    if sec["risk_level"] == "critical":
        raise HTTPException(400, f"Blocked: {sec['issues']}")
    from core.tools import call_tool
    return call_tool(req.tool, **req.args)

@app.get("/files")
def list_files(path: str = ".", auth=Depends(verify_api_key)):
    from core.tools import file_list
    return file_list(path)

@app.get("/files/read")
def read_file(path: str, auth=Depends(verify_api_key)):
    from core.tools import file_read
    return file_read(path)

@app.post("/files/write")
def write_file(req: FileReq, auth=Depends(verify_api_key)):
    from core.tools import file_write
    return file_write(req.path, req.content, req.mode)

@app.post("/shell")
def run_shell(req: ShellReq, auth=Depends(verify_api_key)):
    from core.agents.roles import security_agent
    sec = security_agent(req.command, "shell_command")
    if sec["risk_level"] == "critical":
        raise HTTPException(400, f"Blocked command: {sec['issues']}")
    from core.tools import shell_exec
    return shell_exec(req.command, cwd=req.cwd)

@app.post("/code")
def run_code(req: CodeReq, auth=Depends(verify_api_key)):
    from core.tools import code_exec
    return code_exec(req.code, req.language)

@app.post("/search")
def search_web(q: str, auth=Depends(verify_api_key)):
    from core.tools import web_search
    return web_search(q)

# ── Memory endpoints ──────────────────────────────────────────────────────────

@app.get("/memory")
def get_memory(auth=Depends(verify_api_key)):
    from core.tools import memory_read
    return memory_read()

@app.post("/memory")
def add_memory(req: MemReq, auth=Depends(verify_api_key)):
    from core.tools import memory_append
    return memory_append(req.entry, req.section)

@app.get("/memory/search")
def search_mem(q: str, n: int = 5, auth=Depends(verify_api_key)):
    from memory.vector_store import search_memory
    return search_memory(q, n)

@app.get("/memory/stats")
def mem_stats(auth=Depends(verify_api_key)):
    from memory.vector_store import memory_stats
    return memory_stats()

# ── SQLite Database endpoints ──────────────────────────────────────────────────

@app.get("/db/stats")
def get_db_stats(auth=Depends(verify_api_key)):
    import database
    return database.get_stats()

@app.get("/db/conversations")
def get_db_conversations(limit: int = 100, agent: str = None, username: str = "guest", auth=Depends(verify_api_key)):
    import database
    return database.get_all_conversations(limit=limit, agent=agent, username=username)

@app.delete("/db/conversations/{conv_id}")
def delete_db_conversation(conv_id: int, auth=Depends(verify_api_key)):
    import database
    database.delete_conversation(conv_id)
    return {"status": "deleted"}

@app.get("/chat/history")
def get_chat_history(auth=Depends(verify_api_key)):
    import database
    return database.get_all_conversations(limit=50)

@app.get("/db/search")
def search_db_conversations(q: str, username: str = "guest", auth=Depends(verify_api_key)):
    import database
    return database.search_conversations(q, username)

# ── Reports ───────────────────────────────────────────────────────────────────

@app.get("/reports")
def get_reports():
    from core.tools import list_reports
    return list_reports()

@app.get("/reports/{name}")
def get_report(name: str):
    p = BASE / "reports" / name
    from core.tools import file_read
    return file_read(str(p))

# ── Self-coding + skills ──────────────────────────────────────────────────────

@app.post("/self-code")
def self_code(capability: str, auth=Depends(verify_api_key)):
    from core.subagents import self_coder_agent
    return self_coder_agent(capability)

@app.get("/skills")
def list_skills():
    skills_dir = BASE / "skills_hub"
    skills_dir.mkdir(exist_ok=True)
    skills = []
    for f in skills_dir.glob("*.py"):
        skills.append({"name": f.stem, "file": f.name, "size": f.stat().st_size,
                        "modified": datetime.datetime.fromtimestamp(f.stat().st_mtime).isoformat()})
    return {"skills": skills, "count": len(skills)}

@app.post("/skills/reload")
def reload_skills_endpoint(auth=Depends(verify_api_key)):
    """Hot-reload all skills from skills_hub/ without restarting."""
    from core.tools import reload_skills
    return reload_skills()

# ── Browser / Gmail ────────────────────────────────────────────────────────────

@app.post("/browser/open")
def browse(url: str, auth=Depends(verify_api_key)):
    from core.skills.browser import browser_open
    return browser_open(url)

@app.get("/gmail/inbox")
def inbox(max_results: int = 10, auth=Depends(verify_api_key)):
    from core.skills.gmail import gmail_read_inbox
    return gmail_read_inbox(max_results)

@app.get("/calendar")
def calendar(days: int = 7, auth=Depends(verify_api_key)):
    from core.skills.gmail import calendar_upcoming
    return calendar_upcoming(days)

# ── Domain Agent endpoints ───────────────────────────────────────────────────

@app.post("/chat/finance")
def chat_finance(req: DomainReq, auth=Depends(verify_api_key)):
    from agents.finance import run_finance_agent
    return run_finance_agent(req.task_type, req.data)

@app.post("/chat/health")
def chat_health(req: DomainReq, auth=Depends(verify_api_key)):
    from agents.health import run_health_agent
    return run_health_agent(req.task_type, req.data)

@app.post("/chat/twin")
def chat_twin(req: DomainReq, auth=Depends(verify_api_key)):
    from agents.digital_twin import run_digital_twin
    return run_digital_twin(req.task_type, req.data)

@app.get("/brief")
def brief(auth=Depends(verify_api_key)):
    from core.heartbeat import task_morning_brief
    import asyncio
    loop = asyncio.new_event_loop()
    loop.run_until_complete(task_morning_brief())
    return {"status": "brief generated"}

# ── Status endpoint (for React frontend) ──────────────────────────────────────

@app.get("/status")
def status():
    return {"status": "ok", "version": "5.0.0-jarvis"}

# ── Voice I/O endpoints ──────────────────────────────────────────────────────

@app.post("/voice/transcribe")
async def voice_transcribe(auth=Depends(verify_api_key)):
    """Transcribe uploaded audio to text using Whisper."""
    from fastapi import UploadFile, File
    # This endpoint needs to be called with multipart form data
    return {"info": "POST audio file to /voice/transcribe/upload"}

@app.post("/voice/transcribe/upload")
async def voice_transcribe_upload(file: bytes = None, auth=Depends(verify_api_key)):
    """Transcribe an uploaded audio file."""
    import tempfile
    from core.voice import get_voice_engine

    if not file:
        raise HTTPException(400, "No audio file provided")

    # Save temp file
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".ogg")
    tmp.write(file)
    tmp.close()

    try:
        engine = get_voice_engine()
        text = engine.transcribe(tmp.name)
        return {"status": "ok", "text": text}
    except Exception as e:
        raise HTTPException(500, f"Transcription failed: {str(e)}")
    finally:
        os.unlink(tmp.name)

@app.post("/voice/speak")
def voice_speak(text: str, auth=Depends(verify_api_key)):
    """Convert text to speech and return audio file path."""
    from core.voice import get_voice_engine
    engine = get_voice_engine()
    path = engine.speak_to_file(text)
    return {"status": "ok", "audio_path": path}

# ── Screen Awareness endpoints ────────────────────────────────────────────────

@app.get("/screen/capture")
def screen_capture(auth=Depends(verify_api_key)):
    """Take a screenshot and return the file path."""
    from core.screen import get_screen_awareness
    sa = get_screen_awareness()
    path = sa.capture_screenshot()
    return {"status": "ok", "screenshot_path": path}

@app.get("/screen/read")
def screen_read(auth=Depends(verify_api_key)):
    """Capture screen and OCR the content."""
    from core.screen import get_screen_awareness
    sa = get_screen_awareness()
    text = sa.read_screen()
    return {"status": "ok", "screen_text": text}

@app.get("/screen/active-window")
def screen_active_window(auth=Depends(verify_api_key)):
    """Get info about the currently active window."""
    from core.screen import get_screen_awareness
    sa = get_screen_awareness()
    return sa.get_active_window_info()

# ── OS Control endpoints ──────────────────────────────────────────────────────

@app.post("/os/open-app")
def os_open_app(app_name: str, auth=Depends(verify_api_key)):
    """Open an application by name."""
    from core.os_control import get_os_controller
    ctrl = get_os_controller()
    return ctrl.open_app(app_name)

@app.post("/os/run")
def os_run_command(command: str, auth=Depends(verify_api_key)):
    """Execute a shell command safely."""
    from core.os_control import get_os_controller
    ctrl = get_os_controller()
    return ctrl.run_command(command)

@app.post("/os/file-move")
def os_file_move(src: str, dst: str, auth=Depends(verify_api_key)):
    """Move a file."""
    from core.os_control import get_os_controller
    return get_os_controller().file_move(src, dst)

@app.post("/os/file-copy")
def os_file_copy(src: str, dst: str, auth=Depends(verify_api_key)):
    """Copy a file."""
    from core.os_control import get_os_controller
    return get_os_controller().file_copy(src, dst)

@app.get("/os/system-info")
def os_system_info(auth=Depends(verify_api_key)):
    """Get system information (CPU, RAM, disk, battery)."""
    from core.os_control import get_os_controller
    return get_os_controller().system_info()

@app.get("/os/ls")
def os_list_dir(path: str = None, auth=Depends(verify_api_key)):
    """List directory contents."""
    from core.os_control import get_os_controller
    return get_os_controller().list_directory(path)

# ── Vision endpoints ──────────────────────────────────────────────────────────

@app.post("/vision/analyze")
def vision_analyze(image_path: str, prompt: str = "Describe this image in detail.", auth=Depends(verify_api_key)):
    """Analyze an image using multimodal LLM."""
    from core.vision import get_vision_engine
    result = get_vision_engine().analyze_image(image_path, prompt)
    return {"status": "ok", "analysis": result}

@app.post("/vision/read-handwriting")
def vision_handwriting(image_path: str, auth=Depends(verify_api_key)):
    """Read handwritten notes from an image."""
    from core.vision import get_vision_engine
    return {"status": "ok", "text": get_vision_engine().read_handwriting(image_path)}

@app.post("/vision/whiteboard")
def vision_whiteboard(image_path: str, auth=Depends(verify_api_key)):
    """Analyze a whiteboard photo."""
    from core.vision import get_vision_engine
    return {"status": "ok", "analysis": get_vision_engine().analyze_whiteboard(image_path)}

@app.post("/vision/describe-error")
def vision_error(image_path: str, auth=Depends(verify_api_key)):
    """Analyze an error screenshot."""
    from core.vision import get_vision_engine
    return {"status": "ok", "analysis": get_vision_engine().describe_error(image_path)}

# ── IoT / Sensor endpoints ───────────────────────────────────────────────────

@app.post("/sensors/push")
def sensors_push(sensor_name: str, value: float, unit: str = "", auth=Depends(verify_api_key)):
    """Push a sensor reading (for Raspberry Pi, phone, etc.)."""
    from core.sensors import get_sensor_hub
    return get_sensor_hub().push_reading(sensor_name, value, unit)

@app.get("/sensors/latest")
def sensors_latest(sensor_name: str = None, auth=Depends(verify_api_key)):
    """Get latest sensor readings."""
    from core.sensors import get_sensor_hub
    hub = get_sensor_hub()
    if sensor_name:
        return hub.get_latest(sensor_name)
    return hub.get_all_latest()

@app.get("/sensors/list")
def sensors_list(auth=Depends(verify_api_key)):
    """List all registered sensors."""
    from core.sensors import get_sensor_hub
    return {"sensors": get_sensor_hub().list_sensors()}

# ── Autonomous Mission Control endpoints ─────────────────────────────────────

@app.post("/missions")
def create_mission_endpoint(req: MissionReq, auth=Depends(verify_api_key)):
    """Create a new stateful autonomous mission and generate its subtasks."""
    from core.mission import MissionManager
    manager = MissionManager()
    mission = manager.create_mission(req.goal, req.mode)
    return {"status": "ok", "mission": mission.to_dict()}

@app.get("/missions")
def list_missions_endpoint(auth=Depends(verify_api_key)):
    """List all stateful autonomous missions."""
    from core.mission import MissionManager
    manager = MissionManager()
    return {"status": "ok", "missions": [m.to_dict() for m in manager.missions.values()]}

@app.get("/missions/{mission_id}")
def get_mission_endpoint(mission_id: str, auth=Depends(verify_api_key)):
    """Get status of a specific mission."""
    from core.mission import MissionManager
    manager = MissionManager()
    mission = manager.missions.get(mission_id)
    if not mission:
        return {"status": "error", "message": "Mission not found"}
    return {"status": "ok", "mission": mission.to_dict()}

@app.post("/missions/{mission_id}/step")
async def execute_mission_step_endpoint(mission_id: str, auth=Depends(verify_api_key)):
    """Execute the next step in the mission's plan."""
    from core.mission import MissionManager
    manager = MissionManager()
    result = await manager.execute_mission_step(mission_id)
    return result

@app.get("/decisions")
def get_decision_log(auth=Depends(verify_api_key)):
    """Retrieve the log of all autonomous decision records."""
    import json
    from core.mission import DECISION_LOG_FILE
    if DECISION_LOG_FILE.exists():
        try:
            return json.loads(DECISION_LOG_FILE.read_text(encoding="utf-8"))
        except:
            return []
    return []

# ── Project Memory endpoints ──────────────────────────────────────────────────

@app.post("/projects")
def create_project_endpoint(req: ProjectReq, auth=Depends(verify_api_key)):
    """Create a new project context in project memory."""
    from core.project import ProjectManager
    manager = ProjectManager()
    project = manager.create_project(req.name, req.repos, req.context)
    return {"status": "ok", "project": project.to_dict()}

@app.get("/projects")
def list_projects_endpoint(auth=Depends(verify_api_key)):
    """List all projects in project memory."""
    from core.project import ProjectManager
    manager = ProjectManager()
    return {"status": "ok", "projects": [p.to_dict() for p in manager.projects.values()]}

@app.get("/projects/{name}")
def get_project_endpoint(name: str, auth=Depends(verify_api_key)):
    """Get context of a specific project."""
    from core.project import ProjectManager
    manager = ProjectManager()
    project = manager.projects.get(name)
    if not project:
        return {"status": "error", "message": "Project not found"}
    return {"status": "ok", "project": project.to_dict()}

@app.post("/projects/{name}/decision")
def add_project_decision_endpoint(name: str, decision: str, auth=Depends(verify_api_key)):
    """Log an architectural or technical decision to a project."""
    from core.project import ProjectManager
    manager = ProjectManager()
    result = manager.add_decision(name, decision)
    return result

@app.post("/projects/{name}/github/sync")
def sync_project_github_endpoint(name: str, repo_path: str, auth=Depends(verify_api_key)):
    """Sync repository details into project memory using local git info or GitHub API."""
    from core.github_memory import sync_github_repo
    res = sync_github_repo(name, repo_path)
    if res.get("status") == "success":
        return res
    raise HTTPException(status_code=500, detail=res.get("error", "Sync failed"))