"""
memory/vector_store.py — Persistent vector memory with ChromaDB
Semantic search, conversation recall, long-term memory
Install: pip install chromadb
"""
import json, datetime, hashlib, os, sys, threading
os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["TRANSFORMERS_OFFLINE"] = "1"
from pathlib import Path
from core.logger import logger

try:
    import chromadb
    from chromadb.config import Settings
    CHROMA_OK = True
except ImportError:
    CHROMA_OK = False

BASE = Path(__file__).parent.parent
DB_PATH = str(BASE / "memory" / "chroma_db")

# ── Client singleton ──────────────────────────────────────────────────────────
_client = None
_collections = {}
_embedding_fn = None
_client_lock = threading.Lock()

class CachingOllamaEmbeddingFunction:
    def __init__(self, url, model_name):
        self.url = url
        self.model_name = model_name
        self._underlying = None
        self.cache = {}
        
    def name(self) -> str:
        return "ollama"

    def embed_query(self, input):
        return self(input)

    def embed_documents(self, input):
        return self(input)

    def __call__(self, input):
        if not self._underlying:
            import chromadb.utils.embedding_functions as embedding_functions
            self._underlying = embedding_functions.OllamaEmbeddingFunction(
                url=self.url,
                model_name=self.model_name
            )
            
        results = []
        to_fetch = []
        fetch_indices = []
        
        for idx, text in enumerate(input):
            if text in self.cache:
                results.append((idx, self.cache[text]))
            else:
                to_fetch.append(text)
                fetch_indices.append(idx)
                
        if to_fetch:
            fetched = self._underlying(to_fetch)
            for idx, text, emb in zip(fetch_indices, to_fetch, fetched):
                self.cache[text] = emb
                results.append((idx, emb))
                
        results.sort(key=lambda x: x[0])
        return [r[1] for r in results]

def _get_embedding_fn():
    global _embedding_fn
    if _embedding_fn is None:
        try:
            from config.loader import OLLAMA_URL
            _embedding_fn = CachingOllamaEmbeddingFunction(
                url=f"{OLLAMA_URL()}/api/embeddings",
                model_name="nomic-embed-text"
            )
        except Exception as e:
            print(f"Failed to init embedding fn: {e}")
            _embedding_fn = None
    return _embedding_fn

def _get_client():
    global _client
    if not CHROMA_OK:
        return None
    with _client_lock:
        if _client is None:
            if hasattr(sys, "_chroma_client") and sys._chroma_client is not None:
                _client = sys._chroma_client
            else:
                Path(DB_PATH).mkdir(parents=True, exist_ok=True)
                _client = chromadb.PersistentClient(path=DB_PATH)
                sys._chroma_client = _client
    return _client

def _get_collection(name: str):
    global _collections
    c = _get_client()
    if c is None:
        return None
    if name not in _collections:
        _collections[name] = c.get_or_create_collection(
            name=name,
            embedding_function=_get_embedding_fn(),
            metadata={"hnsw:space": "cosine"}
        )
    return _collections[name]

# ── Core operations ───────────────────────────────────────────────────────────

def store_memory(text: str, metadata: dict = None, collection: str = "memories") -> dict:
    """Store a text chunk in vector memory."""
    if not CHROMA_OK:
        return _fallback_store(text, metadata)
    try:
        col = _get_collection(collection)
        doc_id = hashlib.md5(f"{text}{datetime.datetime.now().isoformat()}".encode()).hexdigest()
        meta = {
            "timestamp": datetime.datetime.now().isoformat(),
            "type": "memory",
            **(metadata or {})
        }
        col.add(documents=[text], ids=[doc_id], metadatas=[meta])
        return {"success": True, "id": doc_id, "collection": collection}
    except Exception as e:
        return {"success": False, "error": str(e)}


# ── BM25 Sparse Index Cache ───────────────────────────────────────────────────
_bm25_cache = {}

def _get_bm25_index(collection_name: str):
    """Retrieve or build BM25 index for a collection."""
    try:
        from rank_bm25 import BM25Okapi
    except ImportError:
        logger.warning("[VECTOR STORE] rank-bm25 not installed. Skipping sparse search hybrid ranking.")
        return None
    col = _get_collection(collection_name)
    if not col: return None
    
    # Very simple caching strategy: rebuild if count changes.
    # In production, you'd want incremental updates.
    count = col.count()
    if count == 0: return None
    
    cached = _bm25_cache.get(collection_name)
    if cached and cached["count"] == count:
        return cached["index"], cached["docs"], cached["ids"], cached["metas"]
        
    # Fetch all docs to build index
    all_data = col.get()
    docs = all_data["documents"]
    tokenized_docs = [doc.lower().split() for doc in docs]
    
    bm25 = BM25Okapi(tokenized_docs)
    _bm25_cache[collection_name] = {
        "count": count,
        "index": bm25,
        "docs": docs,
        "ids": all_data["ids"],
        "metas": all_data["metadatas"]
    }
    return bm25, docs, all_data["ids"], all_data["metadatas"]

def _rrf_score(rank: int, k: int = 60) -> float:
    return 1.0 / (k + rank)


# ── Cross-Encoder Re-ranker Cache ───────────────────────────────────────────
_cross_encoder = None

def _get_cross_encoder():
    """Lazy load the cross encoder to save memory if not used."""
    global _cross_encoder
    if _cross_encoder is None:
        try:
            from sentence_transformers import CrossEncoder
            # Tiny, fast, and very effective for passage ranking
            _cross_encoder = CrossEncoder('cross-encoder/ms-marco-MiniLM-L-6-v2')
        except Exception as e:
            print(f"Failed to load CrossEncoder: {e}")
            _cross_encoder = False # False means tried and failed
    return _cross_encoder if _cross_encoder is not False else None


def search_memory(query: str, n_results: int = 5, collection: str = "memories") -> dict:
    """Semantic + Keyword Hybrid search over stored memories using RRF and Cross-Encoder."""
    if not CHROMA_OK:
        return _fallback_search(query)
    try:
        col = _get_collection(collection)
        count = col.count()
        if count == 0:
            return {"success": True, "results": [], "query": query}
            
        # 1. Semantic Search (ChromaDB)
        semantic_results = col.query(
            query_texts=[query],
            n_results=min(n_results * 4, count) # Fetch many for re-ranking
        )
        
        # 2. Sparse Search (BM25)
        bm25_data = _get_bm25_index(collection)
        
        scores_map = {} # id -> rrf_score
        items_map = {} # id -> item_data
        
        # Process Semantic Results
        if semantic_results["documents"]:
            for rank, (doc, doc_id, meta, dist) in enumerate(zip(
                semantic_results["documents"][0],
                semantic_results["ids"][0],
                semantic_results["metadatas"][0],
                semantic_results.get("distances", [[0]*len(semantic_results["ids"][0])])[0]
            )):
                scores_map[doc_id] = scores_map.get(doc_id, 0) + _rrf_score(rank)
                items_map[doc_id] = {"text": doc, "id": doc_id, "metadata": meta, "distance": dist}
                
        # Process Sparse Results
        if bm25_data:
            bm25, docs, ids, metas = bm25_data
            tokenized_query = query.lower().split()
            doc_scores = bm25.get_scores(tokenized_query)
            
            # Sort by BM25 score descending
            top_bm25 = sorted(zip(ids, docs, metas, doc_scores), key=lambda x: x[3], reverse=True)[:n_results * 4]
            
            for rank, (doc_id, doc, meta, score) in enumerate(top_bm25):
                if score <= 0: continue # Skip zero relevance
                scores_map[doc_id] = scores_map.get(doc_id, 0) + _rrf_score(rank)
                if doc_id not in items_map:
                    items_map[doc_id] = {"text": doc, "id": doc_id, "metadata": meta, "distance": 1.0}
                    
        # 3. Combine and Sort by RRF
        combined = []
        for doc_id, rrf in scores_map.items():
            item = items_map[doc_id]
            item["rrf_score"] = rrf
            combined.append(item)
            
        combined.sort(key=lambda x: x["rrf_score"], reverse=True)
        top_k_candidates = combined[:n_results * 2] # take top 2N candidates to the cross-encoder
        
        # 4. Cross-Encoder Re-ranking
        encoder = _get_cross_encoder()
        if encoder and top_k_candidates:
            # Prepare pairs: (query, document_text)
            cross_inp = [[query, item["text"]] for item in top_k_candidates]
            cross_scores = encoder.predict(cross_inp)
            
            # Attach scores and re-sort
            for idx, item in enumerate(top_k_candidates):
                item["cross_score"] = float(cross_scores[idx])
                
            top_k_candidates.sort(key=lambda x: x["cross_score"], reverse=True)
            
        final_results = top_k_candidates[:n_results]

        return {"success": True, "results": final_results, "query": query, "total": count}
    except Exception as e:
        import traceback
        traceback.print_exc()
        return {"success": False, "error": str(e), "results": []}


def store_conversation(session_id: str, role: str, content: str) -> dict:
    """Store a conversation turn."""
    return store_memory(
        text=content,
        metadata={"type": "conversation", "role": role, "session": session_id},
        collection="conversations"
    )


def recall_conversation(session_id: str, query: str = None, n: int = 10) -> dict:
    """Recall conversation history for a session."""
    if not CHROMA_OK:
        return {"success": True, "results": []}
    try:
        col = _get_collection("conversations")
        if query:
            results = col.query(
                query_texts=[query],
                n_results=min(n, max(col.count(), 1)),
                where={"session": session_id}
            )
            docs = results["documents"][0] if results["documents"] else []
            metas = results["metadatas"][0] if results["metadatas"] else []
        else:
            results = col.get(where={"session": session_id})
            docs = results.get("documents", [])
            metas = results.get("metadatas", [])
        items = [{"text": d, "meta": m} for d, m in zip(docs, metas)]
        return {"success": True, "results": items[-n:]}
    except Exception as e:
        return {"success": False, "error": str(e), "results": []}


def store_document(text: str, source: str, doc_type: str = "document") -> dict:
    """Store a document for RAG retrieval."""
    from core.rag import _semantic_chunk_text
    chunks = _semantic_chunk_text(text, max_chunk_size=1500)
    stored = 0
    for i, chunk in enumerate(chunks):
        r = store_memory(
            text=chunk,
            metadata={"type": doc_type, "source": source, "chunk": i},
            collection="documents"
        )
        if r.get("success"):
            stored += 1
    return {"success": True, "chunks_stored": stored, "source": source}

def add_episodic_memory(agent_name: str, user_query: str, agent_response: str, context_used: str = "") -> dict:
    """Dynamically stores the outcome of an agent interaction as an episodic memory."""
    memory_text = f"User asked {agent_name}: {user_query}\nAgent replied: {agent_response}"
    if context_used:
        memory_text += f"\nContext used: {context_used}"
        
    return store_memory(
        text=memory_text,
        metadata={"type": "episodic", "agent": agent_name, "query": user_query[:50]},
        collection="memories"
    )


def retrieve_for_rag(query: str, n: int = 5) -> dict:
    """Retrieve relevant document chunks for RAG."""
    return search_memory(query, n_results=n, collection="documents")


def store_user_preference(key: str, value: str) -> dict:
    """Store a user preference."""
    return store_memory(
        text=f"{key}: {value}",
        metadata={"type": "preference", "key": key},
        collection="preferences"
    )


def get_user_preferences(query: str = "preferences") -> list:
    """Get relevant user preferences."""
    r = search_memory(query, n_results=10, collection="preferences")
    return [item["text"] for item in r.get("results", [])]


def summarize_and_compress(session_id: str) -> dict:
    """Summarize old conversation memories to save space."""
    import requests
    from config.loader import MODEL_FALLBACK, OLLAMA_URL
    history = recall_conversation(session_id, n=50)
    if not history.get("results"):
        return {"success": True, "result": "No memories to compress"}
    
    text = "\n".join(r["text"] for r in history["results"])
    try:
        r = requests.post(OLLAMA_URL() + "/api/generate", json={
            "model": MODEL_FALLBACK(),
            "prompt": f"Summarize this conversation history in 3-5 bullet points:\n{text[:3000]}",
            "stream": False, "options": {"temperature": 0.3}
        }, timeout=60)
        summary = r.json().get("response", "")
        store_memory(summary, {"type": "summary", "session": session_id}, "memories")
        return {"success": True, "summary": summary}
    except Exception as e:
        return {"success": False, "error": str(e)}


def memory_stats() -> dict:
    """Get memory system stats."""
    if not CHROMA_OK:
        return {"backend": "markdown_fallback", "chroma": False}
    try:
        c = _get_client()
        stats = {"backend": "chromadb", "chroma": True, "collections": {}}
        for name in ["memories", "conversations", "documents", "preferences"]:
            try:
                col = _get_collection(name)
                stats["collections"][name] = col.count()
            except:
                stats["collections"][name] = 0
        return stats
    except Exception as e:
        return {"backend": "error", "error": str(e)}


# ── Fallback (no ChromaDB) ────────────────────────────────────────────────────
_fallback_store_data = []

def _fallback_store(text: str, metadata: dict) -> dict:
    _fallback_store_data.append({"text": text, "meta": metadata or {}})
    return {"success": True, "id": str(len(_fallback_store_data)), "fallback": True}

def _fallback_search(query: str) -> dict:
    query_words = set(query.lower().split())
    results = []
    for item in _fallback_store_data:
        score = len(query_words & set(item["text"].lower().split()))
        if score > 0:
            results.append({"text": item["text"], "metadata": item["meta"], "distance": 1/score})
    results.sort(key=lambda x: x["distance"])
    return {"success": True, "results": results[:5], "fallback": True}


# ── Text chunking ─────────────────────────────────────────────────────────────
def _chunk_text(text: str, chunk_size: int = 800, overlap: int = 100) -> list:
    words = text.split()
    chunks = []
    i = 0
    while i < len(words):
        chunk = " ".join(words[i:i+chunk_size])
        chunks.append(chunk)
        i += chunk_size - overlap
    return chunks or [text]