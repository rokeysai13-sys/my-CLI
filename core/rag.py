"""
core/rag.py — Retrieval-Augmented Generation pipeline
Injects relevant docs/memory into prompts before LLM call.
"""
import re
from pathlib import Path

def build_rag_prompt(query: str, base_prompt: str, session_id: str = None) -> str:
    """
    Build an enriched prompt by retrieving relevant context.
    Returns enhanced prompt with injected context.
    """
    context_blocks = []

    # 1. Search vector memory for relevant docs
    try:
        from memory.vector_store import retrieve_for_rag, search_memory, get_user_preferences
        
        # Relevant documents
        docs = retrieve_for_rag(query, n=3)
        if docs.get("results"):
            doc_texts = "\n".join(
                f"[Doc] {r['text'][:300]}"
                for r in docs["results"]
                if r.get("distance", 1) < 0.7
            )
            if doc_texts:
                context_blocks.append(f"## Relevant Knowledge\n{doc_texts}")

        # Relevant past memories
        mems = search_memory(query, n_results=3, collection="memories")
        if mems.get("results"):
            mem_texts = "\n".join(
                f"- {r['text'][:200]}"
                for r in mems["results"]
                if r.get("distance", 1) < 0.6
            )
            if mem_texts:
                context_blocks.append(f"## Relevant Memory\n{mem_texts}")

        # User preferences
        prefs = get_user_preferences(query)
        if prefs:
            context_blocks.append(f"## User Preferences\n" + "\n".join(f"- {p}" for p in prefs[:3]))

        # Session conversation context
        if session_id:
            from memory.vector_store import recall_conversation
            history = recall_conversation(session_id, query=query, n=5)
            if history.get("results"):
                hist_text = "\n".join(
                    f"{r['meta'].get('role','?')}: {r['text'][:150]}"
                    for r in history["results"]
                )
                context_blocks.append(f"## Recent Conversation\n{hist_text}")

    except Exception as e:
        context_blocks.append(f"## Note\nMemory retrieval unavailable: {e}")

    # 2. Build enriched prompt
    if not context_blocks:
        return base_prompt

    context_str = "\n\n".join(context_blocks)
    return f"""{context_str}

---

{base_prompt}

(Use the context above to inform your response if relevant.)"""


def ingest_file(path: str) -> dict:
    """Load a file and store it in vector memory for RAG."""
    p = Path(path)
    if not p.exists():
        return {"success": False, "error": f"File not found: {path}"}

    try:
        # Read content based on type
        suffix = p.suffix.lower()
        if suffix == ".pdf":
            text = _read_pdf(path)
        elif suffix in [".md", ".txt", ".py", ".js", ".html", ".csv"]:
            text = p.read_text(encoding="utf-8", errors="replace")
        else:
            text = p.read_text(encoding="utf-8", errors="replace")

        from memory.vector_store import store_document
        result = store_document(text, source=str(path), doc_type=suffix.lstrip("."))
        return {**result, "file": str(path), "size": len(text)}
    except Exception as e:
        return {"success": False, "error": str(e)}


def ingest_url(url: str) -> dict:
    """Fetch a URL and store its content for RAG."""
    try:
        import urllib.request, re
        req = urllib.request.Request(url, headers={"User-Agent": "kirannn-rag/1.0"})
        with urllib.request.urlopen(req, timeout=15) as r:
            html = r.read().decode("utf-8", errors="replace")
        text = re.sub(r"<[^>]+>", " ", html)
        text = re.sub(r"\s+", " ", text).strip()

        from memory.vector_store import store_document
        result = store_document(text[:10000], source=url, doc_type="webpage")
        return {**result, "url": url}
    except Exception as e:
        return {"success": False, "error": str(e)}


def ingest_directory(dir_path: str, extensions: list = None) -> dict:
    """Ingest all files in a directory."""
    exts = extensions or [".txt", ".md", ".py", ".pdf"]
    d = Path(dir_path)
    if not d.exists():
        return {"success": False, "error": "Directory not found"}

    results = {"total": 0, "success": 0, "failed": 0, "files": []}
    for f in d.rglob("*"):
        if f.suffix.lower() in exts and f.is_file():
            r = ingest_file(str(f))
            results["total"] += 1
            if r.get("success"):
                results["success"] += 1
            else:
                results["failed"] += 1
            results["files"].append({"file": f.name, **r})

    return {**results, "success": True}


# ── Text chunking ─────────────────────────────────────────────────────────────
def _semantic_chunk_text(text: str, max_chunk_size: int = 1500) -> list:
    """
    Intelligently splits text on semantic boundaries (markdown headers, paragraphs, then sentences).
    This ensures we don't cut sentences or code blocks in half.
    """
    import re
    
    # 1. Try splitting by major markdown headers
    sections = re.split(r'\n(?=#{1,3}\s)', text)
    
    chunks = []
    current_chunk = ""
    
    for section in sections:
        # If the section is small enough, add it or merge it
        if len(current_chunk) + len(section) < max_chunk_size:
            current_chunk += "\n" + section
        else:
            # If current_chunk is full, save it
            if current_chunk.strip():
                chunks.append(current_chunk.strip())
            
            # If the single section is STILL too big, we must split by paragraphs
            if len(section) > max_chunk_size:
                paragraphs = re.split(r'\n\s*\n', section)
                sub_chunk = ""
                for para in paragraphs:
                    if len(sub_chunk) + len(para) < max_chunk_size:
                        sub_chunk += "\n\n" + para
                    else:
                        if sub_chunk.strip():
                            chunks.append(sub_chunk.strip())
                        # If a single paragraph is too big, split by sentences
                        if len(para) > max_chunk_size:
                            sentences = re.split(r'(?<=[.!?])\s+', para)
                            tiny_chunk = ""
                            for sent in sentences:
                                if len(tiny_chunk) + len(sent) < max_chunk_size:
                                    tiny_chunk += " " + sent
                                else:
                                    if tiny_chunk.strip():
                                        chunks.append(tiny_chunk.strip())
                                    tiny_chunk = sent
                            if tiny_chunk.strip():
                                sub_chunk = tiny_chunk.strip()
                        else:
                            sub_chunk = para
                if sub_chunk.strip():
                    current_chunk = sub_chunk.strip()
            else:
                current_chunk = section
                
    if current_chunk.strip():
        chunks.append(current_chunk.strip())
        
    return chunks if chunks else [text]

def _read_pdf(path: str) -> str:
    """Extract text from PDF."""
    try:
        import pypdf
        with open(path, "rb") as f:
            reader = pypdf.PdfReader(f)
            return "\n".join(page.extract_text() or "" for page in reader.pages)
    except ImportError:
        return f"[PDF: {path} — install pypdf to read]"
    except Exception as e:
        return f"[PDF read error: {e}]"