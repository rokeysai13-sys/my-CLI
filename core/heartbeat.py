"""
core/heartbeat.py — Proactive Scheduler
Wakes up every N minutes. Checks tasks, sends briefs, monitors health.
"""
from core.logger import logger
import asyncio, datetime, requests
from pathlib import Path

OLLAMA_URL = "http://localhost:11434/api/generate"
BASE = Path(__file__).parent.parent
_notify_fn = None  # injected by Telegram/Discord bot

def register_notifier(fn):
    global _notify_fn
    _notify_fn = fn

def _notify(msg: str):
    logger.info(f"[HEARTBEAT ⏰] {msg}")
    if _notify_fn:
        try: asyncio.create_task(_notify_fn(msg))
        except: pass

async def task_morning_brief():
    now = datetime.datetime.now()
    if now.hour != 8 or now.minute > 5: return
    mem = (BASE/"memory"/"MEMORY.md").read_text(encoding="utf-8")[:500] if (BASE/"memory"/"MEMORY.md").exists() else ""
    try:
        r = await asyncio.to_thread(
            requests.post,
            OLLAMA_URL,
            json={
                "model": "llama3",
                "prompt": f"Today is {now.strftime('%A %B %d')}. Memory: {mem}\nWrite a 100-word morning brief for Kiran: 1 tech tip, 1 AI trend, 1 focus suggestion.",
                "stream": False, "options": {"temperature": 0.7}
            },
            timeout=30
        )
        brief = r.json().get("response", "Good morning, Kiran!")
        _notify(f"☀️ Morning Brief:\n{brief}")
    except: _notify("☀️ Good morning, Kiran! Time to build something great.")

async def task_pending():
    mem = (BASE/"memory"/"MEMORY.md")
    if not mem.exists(): return
    txt = mem.read_text(encoding="utf-8")
    if "## Pending Tasks" not in txt: return
    start = txt.find("## Pending Tasks")
    end = txt.find("\n##", start+1)
    section = txt[start:end if end!=-1 else start+400]
    if "- " in section:
        _notify(f"📋 Pending tasks:\n{section[:300]}")

async def task_health():
    issues = []
    # 1. Ollama
    try:
        r = await asyncio.to_thread(requests.get, "http://localhost:11434/api/tags", timeout=4)
        models = [m["name"] for m in r.json().get("models",[])]
        if not models: issues.append("Ollama: no models loaded")
        else: logger.info(f"[HEARTBEAT] Ollama OK — {len(models)} models")
    except: issues.append("Ollama offline")
    # 2. API
    try: await asyncio.to_thread(requests.get, "http://localhost:8000/", timeout=3)
    except: issues.append("kirannn API offline")
    # 3. Redis
    try:
        import redis as _redis
        from workers.celery_worker import REDIS_URL
        r_client = _redis.from_url(REDIS_URL, socket_timeout=2)
        await asyncio.to_thread(r_client.ping)
        logger.info("[HEARTBEAT] Redis OK")
    except Exception as e:
        issues.append(f"Redis offline: {e}")
    # 4. Database
    try:
        from database import get_stats
        stats = await asyncio.to_thread(get_stats)
        logger.info(f"[HEARTBEAT] Database OK — {stats.get('total', 0)} conversations")
    except Exception as e:
        issues.append(f"Database error: {e}")
    # 5. Disk space
    try:
        import shutil
        total, used, free = shutil.disk_usage("/")
        free_gb = free / (1024**3)
        if free_gb < 1.0:
            issues.append(f"Disk critically low: {free_gb:.1f} GB free")
        else:
            logger.info(f"[HEARTBEAT] Disk OK — {free_gb:.1f} GB free")
    except: pass
    # 6. Memory system
    try:
        from memory.vector_store import memory_stats
        ms = memory_stats()
        logger.info(f"[HEARTBEAT] Memory OK — backend: {ms.get('backend', 'unknown')}")
    except Exception as e:
        issues.append(f"Memory system: {e}")

    if issues: _notify("⚠️ Health Alert:\n" + "\n".join(issues))
    else: logger.info("[HEARTBEAT] All systems healthy")

async def task_reports():
    """Notify if new reports were saved since last heartbeat."""
    reports_dir = BASE/"reports"
    if not reports_dir.exists(): return
    recent = sorted(reports_dir.glob("*.md"), key=lambda f: f.stat().st_mtime, reverse=True)
    if recent:
        latest = recent[0]
        import time
        if time.time() - latest.stat().st_mtime < 1800:  # last 30min
            _notify(f"📄 New report saved: {latest.name}")

async def heartbeat_loop(interval_minutes: int = 30):
    tick = 0
    logger.info(f"[HEARTBEAT] Started — every {interval_minutes} min")
    while True:
        await asyncio.sleep(interval_minutes * 60)
        tick += 1
        now = datetime.datetime.now().strftime("%H:%M")
        logger.info(f"[HEARTBEAT] Tick #{tick} @ {now}")
        try:
            await task_morning_brief()
            await task_pending()
            if tick % 2 == 0: await task_health()
            await task_reports()
        except Exception as e:
            logger.error(f"[HEARTBEAT] Error: {e}")

def start_heartbeat(interval_minutes: int = 30):
    loop = asyncio.get_event_loop()
    loop.create_task(heartbeat_loop(interval_minutes))