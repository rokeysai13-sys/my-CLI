"""
main.py — kirannn single launcher
Starts: FastAPI + Telegram bot + Discord bot
"""
from core.logger import logger
import os, sys, threading
from pathlib import Path
try: from dotenv import load_dotenv; load_dotenv(Path(__file__).parent/".env")
except: pass

BANNER = """
 ██╗  ██╗██╗██████╗  █████╗ ███╗   ██╗███╗   ██╗███╗   ██╗
 ██║ ██╔╝██║██╔══██╗██╔══██╗████╗  ██║████╗  ██║████╗  ██║
 █████╔╝ ██║██████╔╝███████║██╔██╗ ██║██╔██╗ ██║██╔██╗ ██║
 ██╔═██╗ ██║██╔══██╗██╔══██║██║╚██╗██║██║╚██╗██║██║╚██╗██║
 ██║  ██╗██║██║  ██║██║  ██║██║ ╚████║██║ ╚████║██║ ╚████║
 ╚═╝  ╚═╝╚═╝╚═╝  ╚═╝╚═╝  ╚═╝╚═╝  ╚═══╝╚═╝  ╚═══╝╚═╝  ╚═══╝
  Autonomous Agent System v7.0 — by Kirannn
  Capabilities: Planning · Sub-Agents · Memory · Self-Coding · Heartbeat
"""

def validate_environment() -> bool:
    """Check all critical dependencies before starting services."""
    import requests as req
    logger.info("\n[CHECK] Validating environment...")
    ok = True

    # 1. Check Ollama
    try:
        r = req.get("http://localhost:11434/api/tags", timeout=4)
        models = [m["name"] for m in r.json().get("models", [])]
        if models:
            logger.info(f"  [OK] Ollama: {len(models)} model(s) loaded -> {', '.join(models[:3])}")
        else:
            logger.warning("  [WARN] Ollama: running but NO models loaded")
            logger.info("         Run: ollama pull llama3")
            ok = False
    except Exception:
        logger.error("  [FAIL] Ollama: OFFLINE - run 'ollama serve' first")
        ok = False

    # 2. Check optional bot tokens
    tg = os.getenv("TELEGRAM_TOKEN")
    dc = os.getenv("DISCORD_TOKEN")
    logger.warning(f"  {'[OK]' if tg else '[WARN]'} Telegram bot: {'configured' if tg else 'TELEGRAM_TOKEN not set (bot will be skipped)'}")
    logger.warning(f"  {'[OK]' if dc else '[WARN]'} Discord bot:  {'configured' if dc else 'DISCORD_TOKEN not set  (bot will be skipped)'}")

    # 3. Check memory files
    from pathlib import Path
    base = Path(__file__).parent
    for fname in ["memory/MEMORY.md", "memory/SOUL.md", "memory/AGENTS.md"]:
        p = base / fname
        status = "[OK]  " if p.exists() else "[WARN]"
        note   = "exists" if p.exists() else "missing (will be created on first use)"
        logger.info(f"  {status} {fname}: {note}")

    logger.warning(f"\n{'[OK] Environment OK - starting services.' if ok else '[WARN] Starting with warnings above.'}\n")
    return ok

def start_fastapi():
    import uvicorn
    uvicorn.run("api.server:app", host="0.0.0.0", port=8000, reload=False, log_level="info")

def start_telegram():
    if not os.getenv("TELEGRAM_TOKEN"): print("[MAIN] TELEGRAM_TOKEN not set — skipping"); return
    try: from bots.telegram_bot import run_telegram_bot; run_telegram_bot()
    except Exception as e: print(f"[TELEGRAM] {e}")

def start_discord():
    if not os.getenv("DISCORD_TOKEN"): print("[MAIN] DISCORD_TOKEN not set — skipping"); return
    try: from bots.discord_bot import run_discord_bot; run_discord_bot()
    except Exception as e: print(f"[DISCORD] {e}")

if __name__ == "__main__":
    logger.info(BANNER)
    validate_environment()

    for name, fn in [("Telegram", start_telegram), ("Discord", start_discord)]:
        t = threading.Thread(target=fn, name=name, daemon=True)
        t.start()
    logger.info("[MAIN] API starting on http://localhost:8000")
    start_fastapi()