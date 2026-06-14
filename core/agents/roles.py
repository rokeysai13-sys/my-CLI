"""
core/agents/roles.py — Named agent roles
Provides: planner_agent, critic_agent, security_agent
Called by: api/server.py  (/plan, /critique, /tool, /shell)
"""
import re
import requests
from config.loader import cfg

# ── Config helpers ────────────────────────────────────────────────────────────
def _ollama_url():
    return cfg("models", "ollama_url", default="http://localhost:11434") + "/api/generate"

def _model(key: str, fallback: str = "llama3") -> str:
    return cfg("models", key, default=fallback)


# ── Planner Agent ─────────────────────────────────────────────────────────────
def planner_agent(goal: str) -> dict:
    """
    Break a high-level goal into a structured JSON plan with sub-tasks.
    Returns the same dict shape as core/planner.py decompose().
    """
    from core.planner import decompose
    return decompose(goal, model=_model("planner", "llama3"))


# ── Critic Agent ──────────────────────────────────────────────────────────────
def critic_agent(task: str, result: str) -> dict:
    """
    Evaluate the quality of a task result.
    Returns a score (1-10) and a list of specific improvements.
    """
    try:
        r = requests.post(_ollama_url(), json={
            "model": _model("judge", "qwen2.5:7b"),
            "system": (
                "You are a strict quality evaluator for an AI agent system. "
                "Given a task and its result, you must:\n"
                "1. Score the result from 1-10 (10 = perfect)\n"
                "2. List exactly 3 specific improvements\n"
                "3. State whether the task was actually completed (yes/no)\n"
                "Be concise and direct. No filler text."
            ),
            "prompt": (
                f"Task: {task}\n\n"
                f"Result:\n{result[:2000]}\n\n"
                "Score (1-10), completed (yes/no), and 3 improvements:"
            ),
            "stream": False,
            "options": {"temperature": 0.2}
        }, timeout=60)
        raw = r.json().get("response", "")

        # Try to extract score
        score_match = re.search(r"\b([1-9]|10)\b", raw)
        score = int(score_match.group(1)) if score_match else 5

        # Try to detect completion
        completed = "yes" in raw.lower()[:200]

        return {
            "agent":     "critic",
            "task":      task,
            "score":     score,
            "completed": completed,
            "critique":  raw,
            "success":   True
        }
    except Exception as e:
        return {"agent": "critic", "task": task, "error": str(e), "success": False}


# ── Security Agent ────────────────────────────────────────────────────────────

# Commands / patterns that are always blocked
_BLOCKED_PATTERNS = [
    "rm -rf",
    "format c:",
    "del /f /s /q",
    "shutdown /",
    "DROP TABLE",
    "DROP DATABASE",
    "__import__('os').system",
    "subprocess.call",
    "subprocess.Popen",
    "os.system(",
    "eval(",
    "exec(",
    ":(){:|:&};:",      # fork bomb
    "dd if=/dev/zero",
    "mkfs.",
    "wget http",
    "curl http",
]

# Patterns flagged as high risk but not auto-blocked
_HIGH_RISK_PATTERNS = [
    "password",
    "api_key",
    "secret",
    "token",
    "private_key",
    "os.remove",
    "shutil.rmtree",
    "open(",
]

from pathlib import Path
_ROOT = Path(__file__).parent.parent.parent.resolve()
_ALLOWED_PATHS = [str(Path(ap).resolve()).replace("\\", "/") for ap in cfg("security", "allowed_paths", default=[str(_ROOT), str(Path.home())])]


def security_agent(content: str, context: str = "general") -> dict:
    """
    Scan input for dangerous patterns before executing tools or shell commands.

    Returns:
        {
            "safe":       bool,
            "risk_level": "low" | "medium" | "high" | "critical",
            "issues":     [list of matched patterns],
            "context":    str
        }
    """
    content_lower = content.lower()

    # 1. Check blocked patterns → always critical
    blocked_hits = [p for p in _BLOCKED_PATTERNS if p.lower() in content_lower]
    if blocked_hits:
        return {
            "safe":       False,
            "risk_level": "critical",
            "issues":     blocked_hits,
            "context":    context
        }

    # 2. Check high-risk patterns
    risk_hits = [p for p in _HIGH_RISK_PATTERNS if p.lower() in content_lower]

    # 3. Check path restrictions (for file/shell contexts)
    path_violation = False
    if context in ("shell_command", "file_path", "tool_args"):
        import re as _re
        import tempfile
        # Dynamically append temp directory to allowed paths
        allowed_paths_list = list(_ALLOWED_PATHS)
        try:
            temp_dir = str(Path(tempfile.gettempdir()).resolve()).replace("\\", "/")
            if temp_dir not in allowed_paths_list:
                allowed_paths_list.append(temp_dir)
        except:
            pass

        # Windows paths
        win_paths = _re.findall(r'[A-Za-z]:[/\\][^\s"\']+', content)
        # Unix paths: start with /, not followed by another /, not preceded by letters/colons, no http/https
        unix_paths = []
        for p in _re.findall(r'(?<![:\w])/[a-zA-Z0-9_\-\.]+/[^\s"\']+', content):
            if not p.startswith("//") and not any(scheme in p for scheme in ["http:", "https:"]):
                unix_paths.append(p)
        paths_in_content = win_paths + unix_paths

        for p in paths_in_content:
            try:
                normalized_p = str(Path(p).resolve()).replace("\\", "/")
            except:
                normalized_p = p.replace("\\", "/")
            if not any(normalized_p.startswith(ap) for ap in allowed_paths_list):
                path_violation = True
                risk_hits.append(f"path outside allowed zone: {p}")

    # 4. Determine overall risk level
    if path_violation and risk_hits:
        risk_level = "high"
    elif risk_hits:
        risk_level = "medium"
    else:
        risk_level = "low"

    return {
        "safe":       risk_level == "low",
        "risk_level": risk_level,
        "issues":     risk_hits,
        "context":    context
    }