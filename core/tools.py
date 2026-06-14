"""
core/tools.py — All agent tools: file, shell, web, memory, code execution
"""
from core.logger import logger
import os, subprocess, datetime, re, json
from pathlib import Path

from core.skills.browser import browser_open, browser_screenshot
from core.skills.gmail import gmail_read_inbox, calendar_upcoming

BASE = Path(__file__).parent.parent

# ── File Tools ────────────────────────────────────────────────────────────────
def file_read(path):
    try:
        p = Path(path).expanduser()
        return {"success": True, "result": p.read_text(encoding="utf-8", errors="replace")}
    except Exception as e:
        return {"success": False, "error": str(e)}

def file_write(path, content, mode="w"):
    try:
        p = Path(path).expanduser()
        p.parent.mkdir(parents=True, exist_ok=True)
        with open(p, mode, encoding="utf-8") as f:
            f.write(content)
        return {"success": True, "result": f"Written {len(content)} chars to {p}"}
    except Exception as e:
        return {"success": False, "error": str(e)}

def file_list(path="."):
    try:
        items = [{"name": i.name, "type": "dir" if i.is_dir() else "file",
                  "size": i.stat().st_size if i.is_file() else None}
                 for i in sorted(Path(path).expanduser().iterdir())]
        return {"success": True, "result": items}
    except Exception as e:
        return {"success": False, "error": str(e)}

def file_delete(path):
    try:
        Path(path).expanduser().unlink()
        return {"success": True, "result": f"Deleted {path}"}
    except Exception as e:
        return {"success": False, "error": str(e)}

# ── Shell Tool ────────────────────────────────────────────────────────────────
def shell_exec(command, cwd=None, timeout=30):
    try:
        r = subprocess.run(command, shell=True, capture_output=True,
                           text=True, timeout=timeout, cwd=cwd)
        return {"success": r.returncode == 0, "stdout": r.stdout,
                "stderr": r.stderr, "returncode": r.returncode}
    except subprocess.TimeoutExpired:
        return {"success": False, "error": f"Timed out after {timeout}s"}
    except Exception as e:
        return {"success": False, "error": str(e)}

# ── Code Execution Tool ───────────────────────────────────────────────────────
def code_exec(code, language="python"):
    """Write code to temp file and execute it."""
    import tempfile
    suffix = {"python": ".py", "js": ".js", "bash": ".sh"}.get(language, ".py")
    try:
        with tempfile.NamedTemporaryFile(mode='w', suffix=suffix, delete=False, encoding='utf-8') as f:
            f.write(code)
            tmp = f.name
        if language == "python":
            result = shell_exec(f"python {tmp}", timeout=60)
        elif language == "bash":
            result = shell_exec(f"bash {tmp}", timeout=60)
        else:
            result = shell_exec(f"node {tmp}", timeout=60)
        os.unlink(tmp)
        return result
    except Exception as e:
        return {"success": False, "error": str(e)}

# ── Memory Tools ──────────────────────────────────────────────────────────────
BASE = Path(__file__).parent.parent.resolve()
MEMORY_FILE = BASE / "memory" / "MEMORY.md"
SOUL_FILE   = BASE / "memory" / "SOUL.md"
AGENTS_FILE = BASE / "memory" / "AGENTS.md"

def memory_read():
    return file_read(str(MEMORY_FILE))

def soul_read():
    return file_read(str(SOUL_FILE))

def agents_log_read():
    return file_read(str(AGENTS_FILE))

def memory_append(entry, section="Recent Context"):
    ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    new_line = f"\n- [{ts}] {entry}"
    try:
        txt = MEMORY_FILE.read_text(encoding="utf-8")
        marker = f"## {section}"
        idx = txt.find(marker)
        if idx != -1:
            insert_at = txt.find("\n", idx) + 1
            txt = txt[:insert_at] + new_line + txt[insert_at:]
        else:
            txt += f"\n\n## {section}{new_line}"
        MEMORY_FILE.write_text(txt, encoding="utf-8")
        return {"success": True, "result": "Memory updated"}
    except Exception as e:
        return {"success": False, "error": str(e)}

def agents_log_append(entry):
    return memory_append(entry, section="Completed Tasks") if True else file_write(
        str(AGENTS_FILE), f"\n- {entry}", mode="a")

# ── Web Fetch Tool ────────────────────────────────────────────────────────────
def web_fetch(url):
    try:
        import urllib.request
        req = urllib.request.Request(url, headers={
            "User-Agent": "Mozilla/5.0 (kirannn-agent/1.0)"
        })
        with urllib.request.urlopen(req, timeout=12) as r:
            raw = r.read().decode("utf-8", errors="replace")
        text = re.sub(r"<script[^>]*>.*?</script>", " ", raw, flags=re.DOTALL)
        text = re.sub(r"<style[^>]*>.*?</style>", " ", text, flags=re.DOTALL)
        text = re.sub(r"<[^>]+>", " ", text)
        text = re.sub(r"\s+", " ", text).strip()
        return {"success": True, "result": text[:6000], "url": url}
    except Exception as e:
        return {"success": False, "error": str(e)}

def web_search(query, num=5):
    """Search DuckDuckGo and return result snippets."""
    try:
        import urllib.parse, urllib.request
        q = urllib.parse.quote(query)
        url = f"https://html.duckduckgo.com/html/?q={q}"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=12) as r:
            html = r.read().decode("utf-8", errors="replace")
        # Extract result links + snippets
        links = re.findall(r'href="(https?://[^"]+)"', html)
        snippets = re.findall(r'class="result__snippet"[^>]*>(.*?)</a>', html, re.DOTALL)
        snippets = [re.sub(r"<[^>]+>", "", s).strip() for s in snippets[:num]]
        links = [l for l in links if "duckduckgo" not in l][:num]
        return {"success": True, "results": list(zip(links, snippets)), "query": query}
    except Exception as e:
        return {"success": False, "error": str(e)}

# ── Report Tool ───────────────────────────────────────────────────────────────
def save_report(title, content):
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M")
    # Sanitize title to remove invalid filename characters (including newlines)
    safe_title = re.sub(r'[\x00-\x1f\\/*?:"<>|\n\r]', '', title)
    safe_title = safe_title[:30].strip().replace(' ', '_')
    if not safe_title:
        safe_title = "report"
    fname = BASE / "reports" / f"{ts}_{safe_title}.md"
    fname.parent.mkdir(parents=True, exist_ok=True)
    fname.write_text(content, encoding="utf-8")
    return {"success": True, "result": str(fname), "path": str(fname)}

def list_reports():
    d = BASE / "reports"
    d.mkdir(exist_ok=True)
    return {"success": True, "result": [f.name for f in sorted(d.iterdir()) if f.suffix == ".md"]}

def deep_research_tool(query: str, depth: int = 3):
    from core.deep_research import deep_research
    try:
        return deep_research(query, depth)
    except Exception as e:
        return {"success": False, "error": str(e)}

# ── Screen & OS wrappers ──────────────────────────────────────────────────────
def screen_capture():
    """Capture a screenshot of the user's primary monitor."""
    try:
        from core.screen import get_screen_awareness
        path = get_screen_awareness().capture_screenshot()
        return {"success": True, "result": f"Screenshot saved to {path}", "path": path}
    except Exception as e:
        return {"success": False, "error": str(e)}

def screen_ocr():
    """OCR the content currently displayed on the user's screen."""
    try:
        from core.screen import get_screen_awareness
        text = get_screen_awareness().read_screen()
        return {"success": True, "result": text}
    except Exception as e:
        return {"success": False, "error": str(e)}

def active_window():
    """Get information about the currently focused/active window on the screen."""
    try:
        from core.screen import get_screen_awareness
        info = get_screen_awareness().get_active_window_info()
        return {"success": True, "result": info}
    except Exception as e:
        return {"success": False, "error": str(e)}

def os_open_app(app_name: str):
    """Open a local application by name (e.g., notepad, calculator, chrome, paint, SnippingTool)."""
    try:
        from core.os_control import get_os_controller
        res = get_os_controller().open_app(app_name)
        return {"success": res.get("status") == "ok", "result": res.get("message")}
    except Exception as e:
        return {"success": False, "error": str(e)}

def os_system_info():
    """Get system hardware diagnostics (CPU, RAM, disk, battery status)."""
    try:
        from core.os_control import get_os_controller
        info = get_os_controller().system_info()
        return {"success": True, "result": info}
    except Exception as e:
        return {"success": False, "error": str(e)}

def os_open_file(file_path: str):
    """Open a local file with its default system application."""
    try:
        from core.os_control import get_os_controller
        res = get_os_controller().open_file(file_path)
        return {"success": res.get("status") == "ok", "result": res.get("message")}
    except Exception as e:
        return {"success": False, "error": str(e)}

def ollama_status():
    """Get the list of pulled/downloaded Ollama models on the system."""
    try:
        from config.loader import cfg
        import requests
        ollama_url = cfg("models", "ollama_url", default="http://localhost:11434")
        r = requests.get(f"{ollama_url}/api/tags", timeout=5)
        if r.status_code == 200:
            models = [m["name"] for m in r.json().get("models", [])]
            return {"success": True, "result": models}
        return {"success": False, "error": f"Ollama HTTP {r.status_code}"}
    except Exception as e:
        return {"success": False, "error": str(e)}

# ── Tool Registry ─────────────────────────────────────────────────────────────
TOOLS = {
    "file_read":      (file_read,      ["path"],            "Read a file"),
    "file_write":     (file_write,     ["path","content"],  "Write content to a file"),
    "file_list":      (file_list,      ["path"],            "List directory contents"),
    "file_delete":    (file_delete,    ["path"],            "Delete a file"),
    "shell_exec":     (shell_exec,     ["command"],         "Run a shell/terminal command"),
    "code_exec":      (code_exec,      ["code"],            "Execute Python/bash code"),
    "memory_read":    (memory_read,    [],                  "Read agent long-term memory"),
    "memory_append":  (memory_append,  ["entry"],           "Save something to memory"),
    "soul_read":      (soul_read,      [],                  "Read agent identity & user prefs"),
    "web_fetch":      (web_fetch,      ["url"],             "Fetch a webpage as text"),
    "web_search":     (web_search,     ["query"],           "Search DuckDuckGo for a query"),
    "deep_research":  (deep_research_tool, ["query", "depth"], "Perform deep multi-source research"),
    "save_report":    (save_report,    ["title","content"], "Save a report to disk"),
    "list_reports":   (list_reports,   [],                  "List saved reports"),
    "screen_capture":  (screen_capture,  [],                  "Capture a screenshot of the user's monitor"),
    "screen_ocr":      (screen_ocr,      [],                  "OCR the contents displayed on the screen"),
    "active_window":   (active_window,   [],                  "Get info about the active window"),
    "os_open_app":     (os_open_app,     ["app_name"],        "Open a local application by name"),
    "os_system_info":  (os_system_info,  [],                  "Get local system diagnostics"),
    "os_open_file":    (os_open_file,    ["file_path"],       "Open a local file with default app"),
    "ollama_status":   (ollama_status,   [],                  "Get the list of pulled Ollama models on the system"),
    "browser_open":    (browser_open,    ["url"],             "Open a URL in headless Playwright browser to extract text"),
    "browser_screenshot": (browser_screenshot, ["url", "save_path"], "Take a screenshot of a webpage and save it"),
    "gmail_read":      (gmail_read_inbox, ["max_results"],     "Read the most recent emails from Gmail inbox"),
    "calendar_events": (calendar_upcoming, ["days"],           "Get upcoming calendar events for the next N days"),
}

# ── Skills Hub Auto-Loader ────────────────────────────────────────────────────

def load_skills_hub() -> list:
    """
    Dynamically load every .py skill from skills_hub/ into the TOOLS registry.
    Called once at import time, and again via reload_skills() for hot-reload.
    Returns list of newly registered tool names.
    """
    import importlib.util, inspect
    skills_dir = BASE / "skills_hub"
    skills_dir.mkdir(exist_ok=True)

    loaded = []
    for skill_file in sorted(skills_dir.glob("*.py")):
        try:
            spec = importlib.util.spec_from_file_location(skill_file.stem, skill_file)
            mod  = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)

            # Register every public callable as a tool
            for fn_name, fn in vars(mod).items():
                if callable(fn) and not fn_name.startswith("_") and fn_name not in TOOLS:
                    # Try to introspect args from signature
                    try:
                        sig  = inspect.signature(fn)
                        args = [p for p in sig.parameters if p != "kwargs"]
                    except Exception:
                        args = []
                    doc  = (fn.__doc__ or f"Skill: {fn_name}").split("\n")[0].strip()
                    TOOLS[fn_name] = (fn, args, f"[Skill] {doc}")
                    loaded.append(fn_name)

        except Exception as e:
            logger.error(f"[SKILLS] Failed to load {skill_file.name}: {e}")

    if loaded:
        logger.info(f"[SKILLS] Loaded {len(loaded)} skills: {', '.join(loaded)}")
    return loaded


def reload_skills() -> dict:
    """Hot-reload all skills from skills_hub/ without restarting the server."""
    before = set(TOOLS.keys())
    # Remove previously loaded skills so we can re-register
    skill_names = [k for k, v in list(TOOLS.items()) if "[Skill]" in v[2]]
    for k in skill_names:
        del TOOLS[k]
    newly_loaded = load_skills_hub()
    return {"removed": skill_names, "loaded": newly_loaded}


# Load skills at import time
load_skills_hub()


# ── Tool Dispatcher ───────────────────────────────────────────────────────────

def call_tool(name, **kwargs):
    if name not in TOOLS:
        return {"success": False, "error": f"Unknown tool: {name}. Available: {list(TOOLS.keys())}"}
    try:
        return TOOLS[name][0](**kwargs)
    except Exception as e:
        return {"success": False, "error": str(e)}

def tools_manifest():
    lines = ["TOOLS (call by responding with JSON: {\"tool\":\"name\",\"args\":{...}}):"]
    for name, (_, args, desc) in TOOLS.items():
        lines.append(f"  {name}({', '.join(args)}) — {desc}")
    return "\n".join(lines)