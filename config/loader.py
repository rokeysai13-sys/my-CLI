"""config/loader.py — Load and access settings.yaml"""
import yaml
from pathlib import Path
from functools import lru_cache

CONFIG_PATH = Path(__file__).parent / "settings.yaml"

@lru_cache(maxsize=1)
def get_config() -> dict:
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        content = f.read()
    # Replace hardcoded folder path dynamically on load
    root = str(Path(__file__).parent.parent.resolve()).replace("\\", "/")
    content = content.replace("C:/my_ai_team", root)
    return yaml.safe_load(content)

def cfg(*keys, default=None):
    """Access nested config: cfg('models','planner')"""
    d = get_config()
    for k in keys:
        if isinstance(d, dict):
            d = d.get(k, default)
        else:
            return default
    return d

# Convenience shortcuts
OLLAMA_URL   = lambda: cfg("models", "ollama_url", default="http://localhost:11434")
MODEL_PLAN   = lambda: cfg("models", "planner",  default="qwen2.5:14b")
MODEL_CODE   = lambda: cfg("models", "code",     default="deepseek-coder:33b")
MODEL_JUDGE  = lambda: cfg("models", "judge",    default="qwen2.5:7b")
MODEL_FALLBACK = lambda: cfg("models", "fallback", default="llama3.1:8b")
MODEL_RESEARCH = lambda: cfg("models", "research", default="mistral-large")