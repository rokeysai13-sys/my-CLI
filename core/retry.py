"""
core/retry.py — Auto-retry with exponential backoff
Wraps model calls, tool calls, and API calls.
"""
from core.logger import logger
import time, functools, requests
from config.loader import cfg

MAX_RETRIES  = lambda: cfg("models", "retry_count", default=3)
RETRY_DELAY  = lambda: cfg("models", "retry_delay", default=2.0)
OLLAMA_URL   = lambda: cfg("models", "ollama_url", default="http://localhost:11434")
MODEL_FALLBACK = lambda: cfg("models", "fallback", default="llama3.1:8b")


def with_retry(fn, *args, max_retries=None, delay=None, fallback=None, **kwargs):
    """
    Call fn(*args, **kwargs) with automatic retry on failure.
    Returns result or fallback value.
    """
    retries = max_retries or MAX_RETRIES()
    wait    = delay or RETRY_DELAY()

    last_error = None
    for attempt in range(1, retries + 1):
        try:
            result = fn(*args, **kwargs)
            return result
        except Exception as e:
            last_error = e
            if attempt < retries:
                sleep_time = wait * (2 ** (attempt - 1))  # exponential backoff
                logger.error(f"[RETRY] Attempt {attempt}/{retries} failed: {e}. Retrying in {sleep_time:.1f}s...")
                time.sleep(sleep_time)
            else:
                logger.error(f"[RETRY] All {retries} attempts failed. Last error: {e}")

    if fallback is not None:
        return fallback
    raise last_error


def ollama_call(prompt: str, model: str, system: str = None,
                temperature: float = 0.3, timeout: int = None) -> str:
    """
    Make an LLM API call with automatic retry + cloud model fallback.
    """
    t = timeout or cfg("models", "timeout", default=120)
    from core.llm import llm_generate

    def _call(m):
        res = llm_generate(
            model=m,
            system=system or "",
            prompt=prompt,
            stream=False,
            options={"temperature": temperature},
            timeout=t
        )
        return res.get("response", "").strip()

    # Try primary model with retries
    try:
        return with_retry(_call, model, max_retries=2)
    except Exception as primary_err:
        logger.error(f"[RETRY] Primary model {model} failed: {primary_err}. Trying fallback...")
        # Fallback to configured model
        fallback_model = MODEL_FALLBACK()
        if fallback_model != model:
            try:
                return _call(fallback_model)
            except Exception as fb_err:
                return f"[All models failed. Primary: {primary_err}. Fallback: {fb_err}]"
        return f"[Model {model} failed: {primary_err}]"


def ollama_stream(prompt: str, model: str, system: str = None,
                  temperature: float = 0.3):
    """
    Stream tokens from Ollama. Yields text chunks.
    Falls back to non-streaming on error.
    """
    import json
    try:
        payload = {
            "model": model,
            "prompt": prompt,
            "stream": True,
            "options": {"temperature": temperature}
        }
        if system:
            payload["system"] = system

        with requests.post(
            OLLAMA_URL() + "/api/generate",
            json=payload,
            stream=True,
            timeout=cfg("models", "timeout", default=120)
        ) as r:
            for line in r.iter_lines():
                if line:
                    try:
                        chunk = json.loads(line)
                        token = chunk.get("response", "")
                        if token:
                            yield token
                        if chunk.get("done"):
                            break
                    except json.JSONDecodeError:
                        continue
    except Exception as e:
        yield f"[Stream error: {e}]"


def retry_decorator(max_retries=3, delay=1.0, exceptions=(Exception,)):
    """Decorator for adding retry to any function."""
    def decorator(fn):
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            return with_retry(fn, *args, max_retries=max_retries, delay=delay, **kwargs)
        return wrapper
    return decorator