from core.logger import logger
import requests
import json
import os
import hashlib
from config.loader import cfg

# Simple in-memory cache for LLM outputs
_llm_cache = {}

class LlmResponse(str):
    def get(self, key, default=None):
        if key == "response":
            return str(self)
        return default

def _get_cache_key(model: str, system: str, prompt: str, options: dict) -> str:
    key_src = f"{model}:{system}:{prompt}:{json.dumps(options or {}, sort_keys=True)}"
    return hashlib.sha256(key_src.encode("utf-8")).hexdigest()

def get_available_ollama_models():
    """Fetch the list of locally pulled Ollama models."""
    try:
        ollama_url = cfg("models", "ollama_url", default="http://localhost:11434")
        r = requests.get(f"{ollama_url}/api/tags", timeout=3)
        if r.status_code == 200:
            return [m["name"] for m in r.json().get("models", [])]
    except Exception as e:
        logger.warning(f"[LLM] Failed to check available Ollama models: {e}")
    return []

def llm_generate(prompt: str, model: str = None, system: str = "", stream: bool = False, options: dict = None, timeout: int = 90):
    """
    Unified LLM generation function.
    Routes to Ollama (local) or falls back to cloud providers (OpenAI/Gemini) if configured or if model prefix matches.
    Automatically handles offline models by routing to available local options.
    """
    if model is None:
        model = cfg("models", "fallback", default="llama3")

    options = options or {}
    
    # Check if we should use a cloud model based on prefix
    is_openai = model.startswith("gpt-")
    is_gemini = model.startswith("gemini-")
    
    # Check cache first
    cache_enabled = cfg("cache", "enabled", default=True)
    cache_key = _get_cache_key(model, system, prompt, options)
    
    if cache_enabled and cache_key in _llm_cache:
        logger.info(f"[LLM CACHE] Hit for model '{model}'")
        cached_val = _llm_cache[cache_key]
        return LlmResponse(cached_val.get("response", ""))
        
    if is_openai:
        result = _call_openai(model, system, prompt, options, timeout)
        if cache_enabled and "response" in result:
            _llm_cache[cache_key] = result
        return LlmResponse(result.get("response", ""))
    elif is_gemini:
        result = _call_gemini(model, system, prompt, options, timeout)
        if cache_enabled and "response" in result:
            _llm_cache[cache_key] = result
        return LlmResponse(result.get("response", ""))
        
    # Default to Ollama (Local)
    ollama_url = cfg("models", "ollama_url", default="http://localhost:11434") + "/api/generate"
    
    # Dynamic Model Routing: Ensure the requested model exists locally
    available = get_available_ollama_models()
    if available:
        if model not in available:
            # Try to match the base model name (e.g. "llama3" from "llama3:latest")
            base_model = model.split(":")[0]
            matched = next((m for m in available if m.startswith(base_model) or base_model in m), None)
            
            if matched:
                logger.info(f"[LLM] Model '{model}' not found. Routing to matched local model: '{matched}'")
                model = matched
            else:
                # Bypassing embedding models to find a text generation model
                non_embed = [m for m in available if "embed" not in m]
                fallback = non_embed[0] if non_embed else available[0]
                logger.info(f"[LLM] Model '{model}' not found. Routing to fallback local model: '{fallback}'")
                model = fallback

    try:
        r = requests.post(ollama_url, json={
            "model": model,
            "system": system,
            "prompt": prompt,
            "stream": stream,
            "options": options
        }, timeout=timeout)
        r.raise_for_status()
        result = r.json()
        
        # Save cache
        if cache_enabled and "response" in result:
            _llm_cache[cache_key] = result
            
        return LlmResponse(result.get("response", ""))
    except requests.exceptions.RequestException as e:
        # Fallback to cloud if Ollama fails and fallback is enabled
        fallback_model = cfg("models", "cloud_fallback_model", default="")
        if fallback_model:
            logger.error(f"[LLM] Ollama failed ({e}), falling back to {fallback_model}")
            if fallback_model.startswith("gpt-"):
                res_val = _call_openai(fallback_model, system, prompt, options, timeout)
                return LlmResponse(res_val.get("response", ""))
            elif fallback_model.startswith("gemini-"):
                res_val = _call_gemini(fallback_model, system, prompt, options, timeout)
                return LlmResponse(res_val.get("response", ""))
        raise Exception(f"Ollama request failed and no fallback available: {e}")

def _call_openai(model: str, system: str, prompt: str, options: dict, timeout: int) -> dict:
    api_key = cfg("api_keys", "openai", default=os.getenv("OPENAI_API_KEY"))
    if not api_key:
        raise ValueError("OpenAI API key missing. Please set it in config or OPENAI_API_KEY env.")
    
    url = "https://api.openai.com/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    temperature = options.get("temperature", 0.7)
    
    data = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": prompt}
        ],
        "temperature": temperature
    }
    
    if "stop" in options:
        data["stop"] = options["stop"]
        
    r = requests.post(url, headers=headers, json=data, timeout=timeout)
    r.raise_for_status()
    resp = r.json()
    
    content = resp["choices"][0]["message"]["content"]
    return {"response": content}

def _call_gemini(model: str, system: str, prompt: str, options: dict, timeout: int) -> dict:
    api_key = cfg("api_keys", "gemini", default=os.getenv("GEMINI_API_KEY"))
    if not api_key:
        raise ValueError("Gemini API key missing. Please set it in config or GEMINI_API_KEY env.")
    
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
    
    temperature = options.get("temperature", 0.7)
    
    data = {
        "contents": [
            {
                "role": "user",
                "parts": [{"text": prompt}]
            }
        ],
        "systemInstruction": {
            "parts": [{"text": system}]
        },
        "generationConfig": {
            "temperature": temperature
        }
    }
    
    if "stop" in options:
        data["generationConfig"]["stopSequences"] = options["stop"]
        
    r = requests.post(url, headers={"Content-Type": "application/json"}, json=data, timeout=timeout)
    r.raise_for_status()
    resp = r.json()
    
    try:
        content = resp["candidates"][0]["content"]["parts"][0]["text"]
        return {"response": content}
    except (KeyError, IndexError):
        return {"response": ""}
