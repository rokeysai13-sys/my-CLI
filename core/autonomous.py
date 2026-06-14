"""
core/autonomous.py — Scheduled autonomous task runner.
Agent runs tasks on its own schedule without user prompting.
"""
from core.logger import logger
from apscheduler.schedulers.asyncio import AsyncIOScheduler
import asyncio

scheduler = AsyncIOScheduler()

def start_autonomous_mode():
    """Start the background scheduler."""
    if not scheduler.running:
        # Morning brief at 8am
        scheduler.add_job(morning_brief_task, 'cron', hour=8, minute=0)
        # Hourly health check
        scheduler.add_job(health_check_task, 'interval', hours=1)
        # Daily memory cleanup at midnight
        scheduler.add_job(memory_cleanup_task, 'cron', hour=0, minute=0)
        # Custom user-defined tasks from MEMORY.md "## Scheduled Tasks" section
        scheduler.add_job(run_pending_scheduled_tasks, 'interval', minutes=15)
        
        scheduler.start()
        logger.info("[AUTONOMOUS] Scheduler started")

async def morning_brief_task():
    """Generate a morning briefing based on latest news/events and user memory."""
    logger.info("[AUTONOMOUS] Running morning brief...")
    from core.agent import run_full_pipeline
    # E.g. Send to a default channel or save as report
    try:
        run_full_pipeline("Generate a concise morning briefing of top tech news and my outstanding tasks.")
    except Exception as e:
        logger.error(f"[AUTONOMOUS] Morning brief failed: {e}")

async def health_check_task():
    """Check system health periodically."""
    logger.info("[AUTONOMOUS] Running health check...")
    from core.heartbeat import task_health
    try:
        await task_health()
    except Exception as e:
        logger.error(f"[AUTONOMOUS] Health check failed: {e}")

async def memory_cleanup_task():
    """Consolidate or trim memory files at night."""
    logger.info("[AUTONOMOUS] Running memory cleanup...")
    from memory.episodic import _trim_memory_md
    _trim_memory_md()

async def run_pending_scheduled_tasks():
    """Read scheduled tasks from MEMORY.md and execute them."""
    logger.info("[AUTONOMOUS] Checking for pending tasks...")
    from pathlib import Path
    
    BASE = Path(__file__).parent.parent.resolve()
    MEMORY_FILE = BASE / "memory" / "MEMORY.md"
    
    if not MEMORY_FILE.exists():
        return

    try:
        mem = MEMORY_FILE.read_text(encoding="utf-8")
    except Exception as e:
        logger.error(f"[AUTONOMOUS] Failed to read MEMORY.md: {e}")
        return

    if "## Scheduled Tasks" in mem:
        import re
        parts = mem.split("## Scheduled Tasks")
        pre = parts[0]
        post = parts[1]
        
        # Isolate the Scheduled Tasks section from any subsequent ## sections
        subparts = post.split("\n## ")
        scheduled_section = subparts[0]
        remainder = "\n## " + "\n## ".join(subparts[1:]) if len(subparts) > 1 else ""
        
        lines = scheduled_section.split("\n")
        from core.agent import run_agent
        
        modified = False
        new_lines = []
        for line in lines:
            if line.strip().startswith("- [ ]"):
                task_text = re.sub(r'^-\s*\[\s*\]\s*', '', line.strip())
                logger.info(f"[AUTONOMOUS] Executing task: {task_text}")
                try:
                    # Execute task asynchronously so we do not block the scheduler thread
                    await asyncio.to_thread(run_agent, task_text)
                    line = line.replace("- [ ]", "- [x]")
                    modified = True
                except Exception as ex:
                    logger.error(f"[AUTONOMOUS] Task execution failed: {ex}")
            new_lines.append(line)
            
        if modified:
            new_scheduled_section = "\n".join(new_lines)
            new_mem = pre + "## Scheduled Tasks" + new_scheduled_section + remainder
            try:
                MEMORY_FILE.write_text(new_mem, encoding="utf-8")
                logger.info("[AUTONOMOUS] Marked completed tasks in MEMORY.md")
            except Exception as e:
                logger.error(f"[AUTONOMOUS] Failed to write MEMORY.md: {e}")
