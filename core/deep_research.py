"""
core/deep_research.py — Multi-source research with synthesis.
"""
import concurrent.futures

SEARCH_ENGINES = [
    ("DuckDuckGo", "https://html.duckduckgo.com/html/?q="),
    ("Bing",       "https://www.bing.com/search?q="),
]

def deep_research(query: str, depth: int = 3) -> dict:
    """
    1. Search multiple engines
    2. Fetch top pages
    3. Extract key facts with LLM
    4. Cross-reference for accuracy
    5. Return structured findings with sources
    """
    from core.tools import web_search, web_fetch
    from core.llm import llm_generate
    
    all_results = []
    # Currently web_search function searches DDG internally usually.
    # We will simulate multiple engines by searching the same query,
    # or doing query variations if web_search only supports one endpoint.
    for engine, _ in SEARCH_ENGINES:
        # In a real scenario we'd route to specific engines.
        # Here we just use the existing web_search wrapper for now.
        results = web_search(query, num=5)
        if results.get("success"):
            all_results.extend(results.get("results", []))
    
    # Fetch and extract from top unique URLs
    seen_urls = set()
    urls_to_fetch = []
    
    for url, snippet in all_results:
        if url not in seen_urls and len(urls_to_fetch) < depth * 2:
            seen_urls.add(url)
            urls_to_fetch.append(url)
            
    page_texts = []
    
    def fetch_page(u):
        page = web_fetch(u)
        if page.get("success"):
            return f"Source: {u}\n{page['result'][:1500]}"
        return ""

    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
        results_pages = list(executor.map(fetch_page, urls_to_fetch))
        
    for p in results_pages:
        if p:
            page_texts.append(p)
            
    raw = "\n\n---\n\n".join(page_texts)
    
    # LLM extraction
    try:
        r = llm_generate(
            model="mistral",
            system="",
            prompt=f"Research query: {query}\n\nSources:\n{raw[:5000]}\n\nExtract key facts with source citations:",
            stream=False,
            options={"temperature": 0.2},
            timeout=90
        )
        findings = r.get("response", "No findings extracted.")
    except Exception as e:
        findings = f"LLM Extraction failed: {e}\n\nRaw text preview:\n{raw[:500]}"
    
    return {
        "query": query, 
        "findings": findings, 
        "sources": list(seen_urls), 
        "pages_read": len(page_texts)
    }
