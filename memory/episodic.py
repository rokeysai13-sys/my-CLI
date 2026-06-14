"""
memory/episodic.py — Episodic memory manager with auto-summarization.

How it works:
  - Every session accumulates messages in DB (via api/server.py)
  - When message count hits threshold (default: 50), this module:
      1. Reads the last N messages
      2. Sends them to llama3 for compression into a summary
      3. Stores the summary in ChromaDB vector store
      4. Clears old raw messages from DB
      5. Appends the summary to MEMORY.md under "## Summaries"

This keeps memory lean without losing important context.
"""

from core.logger import logger
import datetime
from pathlib import Path

BASE        = Path(__file__).parent.parent.resolve()
MEMORY_FILE = BASE / "memory" / "MEMORY.md"
MAX_MEMORY_LINES = 200   # trim MEMORY.md if it exceeds this


# ── Check & trigger summarization ────────────────────────────────────────────

def maybe_summarize(session_id: str, username: str = "guest") -> dict:
    """
    Call this after every message save.
    If message count >= threshold, summarize and compress.
    Returns {"summarized": bool, "summary": str or None}
    """
    from config.loader import cfg
    threshold = cfg("memory", "summarize_after", default=50)

    try:
        from database import count_messages
        count = count_messages(session_id)
    except Exception:
        return {"summarized": False, "reason": "count_messages not available"}

    if count < threshold:
        return {"summarized": False, "count": count, "threshold": threshold}

    return summarize_session(session_id, username)


def summarize_session(session_id: str, username: str = "guest") -> dict:
    """
    Summarize a session's messages, store to vector memory, clear old messages.
    """
    try:
        from database import load_persistent_memory, clear_persistent_memory
        msgs = load_persistent_memory(username, limit=100)
    except Exception as e:
        return {"summarized": False, "error": f"DB load failed: {e}"}

    if not msgs:
        return {"summarized": False, "reason": "no messages to summarize"}

    # Build conversation text
    lines = [
        f"{m.get('role', '?')}: {m.get('content', '')[:300]}"
        for m in msgs[-60:]   # last 60 messages max
    ]
    conversation_text = "\n".join(lines)

    # Ask LLM to summarize
    summary = _llm_summarize(conversation_text, session_id)
    if not summary:
        return {"summarized": False, "reason": "LLM summarization failed"}

    # Store in ChromaDB vector memory
    try:
        from memory.vector_store import store_document
        store_document(
            text=summary,
            source=f"session_summary:{session_id}:{datetime.datetime.now().isoformat()}",
            doc_type="summary"
        )
    except Exception as e:
        logger.error(f"[EPISODIC] Vector store failed: {e}")

    # Append to MEMORY.md
    _append_to_memory_md(session_id, summary)

    # Trim MEMORY.md if too long
    _trim_memory_md()

    # Clear raw messages from DB to free space
    try:
        from database import clear_persistent_memory
        clear_persistent_memory(username)
    except Exception as e:
        logger.error(f"[EPISODIC] DB clear failed: {e}")

    logger.info(f"[EPISODIC] Session {session_id} summarized: {len(msgs)} msgs -> 1 summary")
    return {
        "summarized": True,
        "session_id": session_id,
        "messages_compressed": len(msgs),
        "summary_preview": summary[:200]
    }


# ── LLM summarizer ────────────────────────────────────────────────────────────

def _llm_summarize(conversation_text: str, session_id: str) -> str:
    """Use llama3 to compress a conversation into key facts."""
    try:
        from core.retry import ollama_call
        summary = ollama_call(
            prompt=(
                f"Summarize this conversation into concise bullet points.\n"
                f"Focus on: decisions made, facts learned, tasks completed, user preferences.\n"
                f"Be specific. Max 10 bullets.\n\n"
                f"Conversation:\n{conversation_text[:4000]}"
            ),
            model="llama3",
            system="You are a memory compressor for an AI agent. Extract only the most important facts.",
            temperature=0.2
        )
        return summary.strip()
    except Exception as e:
        logger.error(f"[EPISODIC] LLM summarize error: {e}")
        # Fallback: extract first line of each message
        lines = [l for l in conversation_text.split("\n") if l.strip()]
        return "Summary (auto):\n" + "\n".join(f"- {l[:100]}" for l in lines[:10])


# ── MEMORY.md helpers ─────────────────────────────────────────────────────────

def _append_to_memory_md(session_id: str, summary: str):
    """Append a summary entry to MEMORY.md."""
    ts  = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    entry = f"\n- [{ts}] Session {session_id[:8]}:\n{_indent(summary)}"
    try:
        txt = MEMORY_FILE.read_text(encoding="utf-8") if MEMORY_FILE.exists() else ""
        marker = "## Summaries"
        if marker in txt:
            idx = txt.find("\n", txt.find(marker)) + 1
            txt = txt[:idx] + entry + txt[idx:]
        else:
            txt += f"\n\n{marker}{entry}"
        MEMORY_FILE.write_text(txt, encoding="utf-8")
    except Exception as e:
        logger.error(f"[EPISODIC] Memory.md append error: {e}")


def _trim_memory_md():
    """
    If MEMORY.md exceeds MAX_MEMORY_LINES, remove the oldest entries
    (keeping headers and the most recent content intact).
    """
    try:
        if not MEMORY_FILE.exists():
            return
        lines = MEMORY_FILE.read_text(encoding="utf-8").splitlines()
        if len(lines) <= MAX_MEMORY_LINES:
            return

        # Find section headers (## lines)
        headers = [i for i, l in enumerate(lines) if l.startswith("## ")]
        if not headers:
            # No sections — just keep last MAX_MEMORY_LINES lines
            MEMORY_FILE.write_text("\n".join(lines[-MAX_MEMORY_LINES:]), encoding="utf-8")
            return

        # Keep header block (everything before first ##) + last MAX_MEMORY_LINES of content
        preamble    = lines[:headers[0]]
        content     = lines[headers[0]:]
        trimmed     = content[-MAX_MEMORY_LINES:]
        MEMORY_FILE.write_text("\n".join(preamble + trimmed), encoding="utf-8")
        logger.info(f"[EPISODIC] MEMORY.md trimmed: {len(lines)} -> {len(preamble)+len(trimmed)} lines")
    except Exception as e:
        logger.error(f"[EPISODIC] Trim error: {e}")


def _indent(text: str, prefix: str = "  ") -> str:
    return "\n".join(prefix + l for l in text.splitlines())


# ── Manual trigger ────────────────────────────────────────────────────────────

def get_memory_stats() -> dict:
    """Return stats about current memory usage."""
    stats = {}
    try:
        if MEMORY_FILE.exists():
            txt = MEMORY_FILE.read_text(encoding="utf-8")
            stats["memory_md_lines"] = len(txt.splitlines())
            stats["memory_md_bytes"] = len(txt.encode())
    except Exception:
        pass
    try:
        from memory.vector_store import memory_stats
        stats["vector_store"] = memory_stats()
    except Exception:
        stats["vector_store"] = "unavailable"
    return stats
