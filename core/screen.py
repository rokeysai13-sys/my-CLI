"""
core/screen.py — Screen awareness module.
Captures screenshots and performs OCR to understand what's on screen.
"""
import os
import tempfile
from datetime import datetime

try:
    from PIL import Image
    import mss
    SCREEN_CAPTURE_AVAILABLE = True
except ImportError:
    SCREEN_CAPTURE_AVAILABLE = False

try:
    import pytesseract
    OCR_AVAILABLE = True
except ImportError:
    OCR_AVAILABLE = False

from core.logger import logger


class ScreenAwareness:
    """Capture and understand what's on the user's screen."""

    def __init__(self):
        logger.info(f"ScreenAwareness init — capture: {SCREEN_CAPTURE_AVAILABLE}, OCR: {OCR_AVAILABLE}")

    def capture_screenshot(self, output_path: str = None, monitor: int = 1) -> str:
        """
        Take a screenshot of the specified monitor.
        
        Args:
            output_path: Where to save. Auto-generated if None.
            monitor: Monitor index (1 = primary).
            
        Returns:
            Path to the saved screenshot PNG.
        """
        if not SCREEN_CAPTURE_AVAILABLE:
            raise RuntimeError("mss and Pillow are required. Run: pip install mss Pillow")

        if output_path is None:
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_path = os.path.join(tempfile.gettempdir(), f"kirannn_screen_{ts}.png")

        with mss.mss() as sct:
            screenshot = sct.grab(sct.monitors[monitor])
            img = Image.frombytes("RGB", screenshot.size, screenshot.bgra, "raw", "BGRX")
            img.save(output_path, "PNG")

        logger.info(f"Screenshot saved: {output_path}")
        return output_path

    def read_screen(self, image_path: str = None) -> str:
        """
        OCR the screen contents. If no image path given, captures a fresh screenshot first.
        
        Returns:
            Extracted text from the screen.
        """
        if image_path is None:
            image_path = self.capture_screenshot()

        if not OCR_AVAILABLE:
            raise RuntimeError("pytesseract is required. Run: pip install pytesseract")

        img = Image.open(image_path)
        text = pytesseract.image_to_string(img)
        logger.info(f"OCR extracted {len(text)} chars from screen")
        return text.strip()

    def get_active_window_info(self) -> dict:
        """
        Get information about the currently active window (Windows only).
        
        Returns:
            Dict with 'title' and 'process' keys.
        """
        try:
            import ctypes
            from ctypes import wintypes

            user32 = ctypes.windll.user32
            h_wnd = user32.GetForegroundWindow()

            # Get window title
            length = user32.GetWindowTextLengthW(h_wnd) + 1
            title_buf = ctypes.create_unicode_buffer(length)
            user32.GetWindowTextW(h_wnd, title_buf, length)

            # Get process ID
            pid = wintypes.DWORD()
            user32.GetWindowThreadProcessId(h_wnd, ctypes.byref(pid))

            result = {
                "title": title_buf.value,
                "pid": pid.value,
            }

            # Try to get process name
            try:
                import subprocess
                proc = subprocess.run(
                    ["tasklist", "/FI", f"PID eq {pid.value}", "/FO", "CSV", "/NH"],
                    capture_output=True, text=True, timeout=5
                )
                if proc.stdout.strip():
                    result["process"] = proc.stdout.strip().split(",")[0].strip('"')
            except Exception:
                pass

            logger.info(f"Active window: {result.get('title', 'unknown')}")
            return result

        except Exception as e:
            logger.error(f"Failed to get active window info: {e}")
            return {"title": "unknown", "error": str(e)}


# ── Singleton ────────────────────────────────────────────────────────

_instance = None

def get_screen_awareness() -> ScreenAwareness:
    global _instance
    if _instance is None:
        _instance = ScreenAwareness()
    return _instance
