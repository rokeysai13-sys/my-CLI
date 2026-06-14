"""
core/skills/browser.py — Playwright browser automation skill
Requires: playwright>=1.40.0   (pip install playwright && playwright install chromium)

Usage via API:
  POST /browser/open   {"url": "https://example.com"}

Usage via agent tool:
  {"tool": "browser_open", "args": {"url": "https://example.com"}}
"""
import re


def browser_open(url: str, headless: bool = True) -> dict:
    """
    Open a URL in a headless browser, extract visible text + title.
    Much better than web_fetch for JS-heavy sites.
    """
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return {
            "success": False,
            "error": "Playwright not installed. Run: pip install playwright && playwright install chromium"
        }

    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=headless)
            ctx     = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) kirannn-agent/1.0"
            )
            page = ctx.new_page()
            page.goto(url, timeout=20_000, wait_until="domcontentloaded")

            title   = page.title()
            html    = page.content()
            browser.close()

        # Strip scripts, styles, tags → plain text
        text = re.sub(r"<script[^>]*>.*?</script>", " ", html, flags=re.DOTALL)
        text = re.sub(r"<style[^>]*>.*?</style>",  " ", text, flags=re.DOTALL)
        text = re.sub(r"<[^>]+>", " ", text)
        text = re.sub(r"\s+", " ", text).strip()

        return {
            "success": True,
            "url":     url,
            "title":   title,
            "text":    text[:6000],
            "length":  len(text)
        }
    except Exception as e:
        return {"success": False, "url": url, "error": str(e)}


def browser_screenshot(url: str, save_path: str = None) -> dict:
    """Take a screenshot of a webpage and save it."""
    try:
        from playwright.sync_api import sync_playwright
        from pathlib import Path
        import datetime

        BASE = Path(__file__).parent.parent.parent.resolve()
        save_path = save_path or f"{BASE}/reports/screenshot_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.png"

        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True)
            page    = browser.new_page(viewport={"width": 1280, "height": 800})
            page.goto(url, timeout=20_000)
            page.screenshot(path=save_path, full_page=True)
            browser.close()

        return {"success": True, "url": url, "saved_to": save_path}
    except Exception as e:
        return {"success": False, "error": str(e)}
