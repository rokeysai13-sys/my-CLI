"""
core/watchdog.py — Self-healing watchdog service
Monitors components, auto-restarts failures, recovers tasks.
"""
from core.logger import logger
import asyncio, datetime, subprocess, sys, time
from pathlib import Path

BASE = Path(__file__).parent.parent


class Watchdog:
    """Monitors and auto-restarts failed components."""

    def __init__(self):
        self.checks = {}
        self.failures = {}
        self.restart_counts = {}
        self.max_restarts = 5
        self._running = False
        self._notify_fn = None

    def register_notifier(self, fn):
        self._notify_fn = fn

    async def _notify(self, msg: str):
        logger.info(f"[WATCHDOG] {msg}")
        if self._notify_fn:
            try:
                await self._notify_fn(msg)
            except:
                pass

    # ── Health checks ─────────────────────────────────────────────────────────

    async def check_ollama(self) -> bool:
        import requests
        try:
            r = await asyncio.to_thread(requests.get, "http://localhost:11434/api/tags", timeout=15)
            return r.status_code == 200
        except:
            return False

    async def check_api(self) -> bool:
        import requests
        try:
            r = await asyncio.to_thread(requests.get, "http://localhost:8000/health", timeout=15)
            return r.status_code == 200
        except:
            return False

    async def check_memory(self) -> bool:
        try:
            from memory.vector_store import memory_stats
            stats = memory_stats()
            return stats.get("backend") in ["chromadb", "markdown_fallback"]
        except:
            return False

    async def check_disk_space(self) -> bool:
        try:
            import shutil
            total, used, free = shutil.disk_usage("/")
            free_gb = free / (1024**3)
            return free_gb > 1.0  # warn if less than 1GB free
        except:
            return True

    # ── Recovery actions ──────────────────────────────────────────────────────

    async def restart_api(self):
        """Restart the FastAPI server."""
        count = self.restart_counts.get("api", 0)
        if count >= self.max_restarts:
            await self._notify(f"[!] API failed {count} times — NOT restarting (max reached)")
            return
        self.restart_counts["api"] = count + 1
        await self._notify(f"[*] Restarting API server (attempt {count+1})...")
        try:
            venv_python = str(BASE / ".venv" / "Scripts" / "python.exe")
            if not Path(venv_python).exists():
                venv_python = sys.executable
            subprocess.Popen(
                [venv_python, str(BASE / "main.py")],
                cwd=str(BASE),
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if sys.platform == "win32" else 0
            )
            await asyncio.sleep(5)
            if await self.check_api():
                await self._notify("[OK] API restarted successfully!")
            else:
                await self._notify("[!] API restart attempted but still offline")
        except Exception as e:
            await self._notify(f"[X] API restart failed: {e}")

    async def reload_ollama_models(self):
        """Ping Ollama to wake up models."""
        import requests
        from config.loader import MODEL_FALLBACK, OLLAMA_URL
        try:
            await asyncio.to_thread(
                requests.post,
                OLLAMA_URL() + "/api/generate",
                json={
                    "model": MODEL_FALLBACK(),
                    "prompt": "hi",
                    "stream": False
                },
                timeout=30
            )
            await self._notify("[OK] Ollama model warmed up")
        except Exception as e:
            await self._notify(f"[X] Ollama reload failed: {e}")

    async def recover_memory(self):
        """Attempt to recover memory system."""
        try:
            from memory.vector_store import memory_stats
            stats = memory_stats()
            await self._notify(f"[*] Memory stats: {stats}")
        except Exception as e:
            await self._notify(f"[X] Memory recovery failed: {e}")

    # ── Main watchdog loop ────────────────────────────────────────────────────

    async def run(self, interval: int = 60):
        """Main watchdog loop. Checks health every N seconds."""
        self._running = True
        logger.info(f"[WATCHDOG] Started — checking every {interval}s")

        component_checks = {
            "ollama":     (self.check_ollama,    self.reload_ollama_models),
            "api":        (self.check_api,        self.restart_api),
            "memory":     (self.check_memory,     self.recover_memory),
            "disk":       (self.check_disk_space, None),
        }

        while self._running:
            await asyncio.sleep(interval)
            timestamp = datetime.datetime.now().strftime("%H:%M:%S")
            issues = []

            for name, (check_fn, recovery_fn) in component_checks.items():
                try:
                    healthy = await check_fn()
                    if not healthy:
                        issues.append(name)
                        self.failures[name] = self.failures.get(name, 0) + 1
                        logger.error(f"[WATCHDOG !] {name} is DOWN (failure #{self.failures[name]})")
                        if recovery_fn and self.failures[name] <= 3:
                            await recovery_fn()
                    else:
                        if name in self.failures and self.failures[name] > 0:
                            logger.info(f"[WATCHDOG OK] {name} recovered")
                        self.failures[name] = 0
                except Exception as e:
                    logger.error(f"[WATCHDOG] Check error for {name}: {e}")

            if issues:
                await self._notify(f"[!] Watchdog alert @ {timestamp}: {', '.join(issues)} down")
            else:
                logger.info(f"[WATCHDOG OK] All systems healthy @ {timestamp}")

    def stop(self):
        self._running = False


# ── Global instance ───────────────────────────────────────────────────────────
_watchdog = Watchdog()

def get_watchdog() -> Watchdog:
    return _watchdog

def start_watchdog(interval: int = 60):
    """Launch watchdog as background asyncio task."""
    loop = asyncio.get_event_loop()
    loop.create_task(_watchdog.run(interval))
    logger.info(f"[WATCHDOG] Scheduled every {interval}s")