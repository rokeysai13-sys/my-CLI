from core.logger import logger
import ollama

MODELS = {
    "coder":    "deepseek-coder:6.7b",
    "general":  "llama3",
    "reason":   "mistral",
    "analysis": "qwen2.5:7b"
}

OPTIONS = {
    "num_ctx": 2048,
    "num_gpu": 99,
    "num_thread": 8,
    "temperature": 0.7,
}

SYSTEM_PROMPTS = {
    "coder":    "You are a coding assistant. Give clean, working code. Be direct.",
    "general":  "You are a knowledgeable AI. Give accurate, well-structured answers. No filler phrases.",
    "reason":   "You are a sharp reasoning engine. Give accurate, well-reasoned answers.",
    "analysis": "You are an analytical AI. Give thorough, accurate analysis.",
}

DEBATE_PROMPTS = {
    "research": "You are in an AI debate. Give a thorough, well-structured answer covering all important aspects. Be accurate and detailed.",
    "critique": "You are reviewing other AI answers in a debate. Find specific factual errors, missing info, and weak reasoning. Be specific, harsh, and use bullet points.",
    "rewrite":  "You are rewriting your answer after criticism. Fix mistakes, keep what was correct, make it the most accurate and complete answer possible.",
    "vote":     "You are voting for the best debate answer. Analyze carefully and pick the most accurate one.",
}

def ask(model, prompt, history=None, model_key="general", debate_phase=None):
    from core.llm import llm_generate
    system = DEBATE_PROMPTS.get(debate_phase) if debate_phase else SYSTEM_PROMPTS.get(model_key, SYSTEM_PROMPTS["general"])
    
    full_prompt = ""
    if history:
        for msg in history[-10:]:
            role = msg.get("role", "user") if isinstance(msg, dict) else (msg[0] if isinstance(msg, tuple) else "user")
            content = msg.get("content", "") if isinstance(msg, dict) else (msg[1] if isinstance(msg, tuple) else str(msg))
            full_prompt += f"{str(role).capitalize()}: {content}\n\n"
    full_prompt += f"User: {prompt}"
    
    res = llm_generate(full_prompt, model=model, system=system)
    if isinstance(res, dict):
        return res.get("response", "").strip()
    return str(res).strip()

def ask_stream(model, prompt, history=None, model_key="general", debate_phase=None):
    from core.retry import ollama_stream
    system = DEBATE_PROMPTS.get(debate_phase) if debate_phase else SYSTEM_PROMPTS.get(model_key, SYSTEM_PROMPTS["general"])
    
    full_prompt = ""
    if history:
        for msg in history[-10:]:
            role = msg.get("role", "user") if isinstance(msg, dict) else (msg[0] if isinstance(msg, tuple) else "user")
            content = msg.get("content", "") if isinstance(msg, dict) else (msg[1] if isinstance(msg, tuple) else str(msg))
            full_prompt += f"{str(role).capitalize()}: {content}\n\n"
    full_prompt += f"User: {prompt}"
    
    try:
        for chunk in ollama_stream(full_prompt, model=model, system=system):
            yield chunk
    except Exception as e:
        yield f"[Error: {e}]"

def warmup():
    logger.info("Warming up models...")
    for name, model in MODELS.items():
        try:
            ollama.chat(model=model, messages=[{"role": "user", "content": "hi"}], options=OPTIONS)
            logger.info(f"  OK {model} ready")
        except Exception as e:
            logger.error(f"  FAIL {model}: {e}")