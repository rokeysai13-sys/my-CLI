"""
core/os_control.py — Local OS control module.
Gives agents the ability to open apps, run scripts, move files, and control the laptop.
"""
import os
import shutil
import subprocess
import platform
from pathlib import Path

from core.logger import logger


# ── Safety: Only allow certain operations ────────────────────────────

BLOCKED_COMMANDS = [
    "format", "del /s", "rm -rf /", "shutdown", "restart",
    "reg delete", "taskkill /f /im explorer", "net user",
]

ALLOWED_EXTENSIONS_TO_OPEN = [
    ".txt", ".py", ".js", ".html", ".css", ".md", ".json",
    ".pdf", ".docx", ".xlsx", ".pptx", ".png", ".jpg", ".mp4",
]


def _is_safe_command(cmd: str) -> bool:
    """Check if a command is safe to execute."""
    cmd_lower = cmd.lower().strip()
    for blocked in BLOCKED_COMMANDS:
        if blocked in cmd_lower:
            logger.warning(f"BLOCKED dangerous command: {cmd}")
            return False
    return True


class OSController:
    """Control the local operating system safely."""

    def __init__(self):
        self.system = platform.system()  # 'Windows', 'Linux', 'Darwin'
        logger.info(f"OSController initialized for {self.system}")

    # ── App Launching ────────────────────────────────────────────────

    def open_app(self, app_name: str) -> dict:
        """
        Open an application by name.
        
        Args:
            app_name: Name like 'notepad', 'chrome', 'vscode', 'explorer'
            
        Returns:
            dict with 'status' and 'message'
        """
        import platform
        is_windows = platform.system() == "Windows"
        is_mac = platform.system() == "Darwin"

        app_map = {
            "notepad": "notepad.exe" if is_windows else ("open -e" if is_mac else "nano"),
            "calculator": "calc.exe" if is_windows else ("open -a Calculator" if is_mac else "bc"),
            "explorer": "explorer.exe" if is_windows else ("open" if is_mac else "xdg-open ."),
            "chrome": r"C:\Program Files\Google\Chrome\Application\chrome.exe" if is_windows else ("open -a 'Google Chrome'" if is_mac else "google-chrome"),
            "vscode": "code",
            "cmd": "cmd.exe" if is_windows else "bash",
            "powershell": "powershell.exe" if is_windows else "pwsh",
            "task_manager": "taskmgr.exe" if is_windows else ("open -a 'Activity Monitor'" if is_mac else "top"),
            "paint": "mspaint.exe" if is_windows else ("open -a Photos" if is_mac else "gimp"),
            "snipping": "SnippingTool.exe" if is_windows else ("open -a Screencapture" if is_mac else "gnome-screenshot"),
        }

        exe = app_map.get(app_name.lower(), app_name)
        
        try:
            subprocess.Popen(exe, shell=True)
            logger.info(f"Opened app: {app_name} ({exe})")
            return {"status": "ok", "message": f"Opened {app_name}"}
        except Exception as e:
            logger.error(f"Failed to open app {app_name}: {e}")
            return {"status": "error", "message": str(e)}

    # ── Script / Command Execution ───────────────────────────────────

    def run_command(self, command: str, timeout: int = 30) -> dict:
        """
        Execute a shell command safely.
        
        Args:
            command: The command string to run
            timeout: Max seconds before killing the process
            
        Returns:
            dict with 'status', 'stdout', 'stderr', 'returncode'
        """
        if not _is_safe_command(command):
            return {"status": "blocked", "message": "Command blocked for safety reasons."}

        try:
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=os.path.expanduser("~")
            )
            logger.info(f"Command executed: {command[:60]}... → rc={result.returncode}")
            return {
                "status": "ok",
                "stdout": result.stdout[:2000],  # Cap output
                "stderr": result.stderr[:500],
                "returncode": result.returncode
            }
        except subprocess.TimeoutExpired:
            return {"status": "timeout", "message": f"Command timed out after {timeout}s"}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    # ── File Operations ──────────────────────────────────────────────

    def file_move(self, src: str, dst: str) -> dict:
        """Move a file or directory."""
        try:
            shutil.move(src, dst)
            logger.info(f"Moved: {src} → {dst}")
            return {"status": "ok", "message": f"Moved {src} to {dst}"}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def file_copy(self, src: str, dst: str) -> dict:
        """Copy a file or directory."""
        try:
            if os.path.isdir(src):
                shutil.copytree(src, dst)
            else:
                shutil.copy2(src, dst)
            logger.info(f"Copied: {src} → {dst}")
            return {"status": "ok", "message": f"Copied {src} to {dst}"}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def file_delete(self, path: str) -> dict:
        """Delete a file (NOT directories for safety)."""
        try:
            if os.path.isdir(path):
                return {"status": "blocked", "message": "Directory deletion blocked for safety. Use specific commands."}
            os.remove(path)
            logger.info(f"Deleted: {path}")
            return {"status": "ok", "message": f"Deleted {path}"}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def open_file(self, file_path: str) -> dict:
        """Open a file with its default application."""
        try:
            os.startfile(file_path)
            logger.info(f"Opened file: {file_path}")
            return {"status": "ok", "message": f"Opened {file_path}"}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def list_directory(self, path: str = None) -> dict:
        """List contents of a directory."""
        if path is None:
            path = os.path.expanduser("~\\Desktop")
        try:
            items = []
            for item in Path(path).iterdir():
                items.append({
                    "name": item.name,
                    "type": "dir" if item.is_dir() else "file",
                    "size": item.stat().st_size if item.is_file() else None
                })
            return {"status": "ok", "path": path, "items": items[:50]}  # Cap at 50
        except Exception as e:
            return {"status": "error", "message": str(e)}

    # ── System Info ──────────────────────────────────────────────────

    def system_info(self) -> dict:
        """Get basic system information."""
        info = {
            "os": platform.system(),
            "version": platform.version(),
            "machine": platform.machine(),
            "hostname": platform.node(),
            "user": os.getlogin(),
        }
        try:
            import psutil
            info["cpu_percent"] = psutil.cpu_percent(interval=1)
            info["ram_percent"] = psutil.virtual_memory().percent
            info["disk_percent"] = psutil.disk_usage("/").percent
            info["battery"] = None
            batt = psutil.sensors_battery()
            if batt:
                info["battery"] = {"percent": batt.percent, "plugged": batt.power_plugged}
        except ImportError:
            pass
        return info


# ── Singleton ────────────────────────────────────────────────────────

_instance = None

def get_os_controller() -> OSController:
    global _instance
    if _instance is None:
        _instance = OSController()
    return _instance
