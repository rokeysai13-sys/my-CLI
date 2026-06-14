"""
core/subagents.py — Specialist Sub-Agent Pool
Each agent has a focused role. Orchestrator runs them in parallel.
"""
import re, json
from concurrent.futures import ThreadPoolExecutor
from .tools import (web_search, web_fetch, shell_exec, code_exec,
                    memory_append, file_write, save_report)

from config.loader import cfg
from core.llm import llm_generate

# ── Individual specialist agents ──────────────────────────────────────────────

def researcher_agent(task: str, context: str = "") -> dict:
    """Searches web, fetches pages in parallel, returns gathered raw data."""
    findings = []
    sources = []
    
    # Step 1: Search for the topic
    search = web_search(task, num=5)
    if search["success"]:
        findings.append(f"Search results for '{task}':")
        results = search.get("results", [])[:3]
        for url, snippet in results:
            findings.append(f"- {url}\n  {snippet}")
            sources.append(url)
            
        # Step 2: Fetch pages in parallel
        def fetch_url(url):
            page = web_fetch(url)
            if page["success"]:
                return f"Content from {url}:\n{page['result'][:1000]}"
            return ""
            
        with ThreadPoolExecutor(max_workers=3) as executor:
            pages = list(executor.map(fetch_url, sources))
            
        findings.extend(p for p in pages if p)
    
    raw = "\n".join(findings)
    
    # Step 3: Ask model to extract key facts
    model = cfg("models", "research", default="mistral")
    try:
        r = llm_generate(
            model=model,
            system="You are a research analyst. Extract key facts, statistics, and insights from raw data. Be precise.",
            prompt=f"Task: {task}\n\nRaw data:\n{raw[:4000]}\n\nExtract the most important findings as bullet points.",
            stream=False,
            options={"temperature": 0.3}
        )
        summary = r.get("response", raw[:1000])
    except Exception as e:
        summary = f"{raw[:1500]}\n\n(Summarization error: {e})"
    
    return {"agent": "researcher", "task": task, "findings": summary, "sources": sources}


def coder_agent(task: str, context: str = "") -> dict:
    """Writes and optionally executes code to solve a problem."""
    model = cfg("models", "code", default="deepseek-coder:6.7b")
    try:
        r = llm_generate(
            model=model,
            system="You are an expert programmer. Write clean, working Python code. If the task needs execution, add: # EXECUTE at the top of the code.",
            prompt=f"Task: {task}\nContext: {context[:500]}",
            stream=False,
            options={"temperature": 0.2}
        )
        response = r.get("response", "")
    except Exception as e:
        return {"agent": "coder", "task": task, "error": str(e)}
    
    # Extract code block
    code_match = re.search(r"```python\n?(.*?)```", response, re.DOTALL)
    code = code_match.group(1) if code_match else ""
    
    executed = None
    if "# EXECUTE" in response and code:
        executed = code_exec(code, "python")
    
    return {"agent": "coder", "task": task, "code": code, "response": response, "executed": executed}


def analyst_agent(task: str, data: str = "", context: str = "") -> dict:
    """Synthesizes data, scores confidence, finds patterns."""
    model = cfg("models", "judge", default="llama3")
    try:
        r = llm_generate(
            model=model,
            system="You are a senior data analyst. For every major claim or conclusion, assign a confidence level: [HIGH], [MEDIUM], or [LOW]. Structure your analysis clearly with sections.",
            prompt=f"Analyze this for: {task}\n\nData:\n{data[:3000]}\n\nProvide structured analysis with confidence scores.",
            stream=False,
            options={"temperature": 0.3}
        )
        analysis = r.get("response", "No analysis available")
    except Exception as e:
        return {"agent": "analyst", "task": task, "error": str(e)}
    
    return {"agent": "analyst", "task": task, "analysis": analysis}


def writer_agent(task: str, data: str = "", title: str = "Report") -> dict:
    """Produces polished, publication-ready reports."""
    model = cfg("models", "fallback", default="llama3")
    try:
        r = llm_generate(
            model=model,
            system="You are a professional technical writer. Write publication-ready reports with Executive Summary, Key Findings (with [HIGH/MEDIUM/LOW] confidence), Detailed Analysis, Sources, and Conclusion. Use proper Markdown formatting.",
            prompt=f"Write a comprehensive report on: {task}\n\nResearch data:\n{data[:4000]}",
            stream=False,
            options={"temperature": 0.4}
        )
        report = r.get("response", "Report generation failed")
    except Exception as e:
        return {"agent": "writer", "task": task, "error": str(e)}
    
    # Auto-save to disk
    saved = save_report(title, report)
    
    return {"agent": "writer", "task": task, "report": report, "saved_to": saved.get("path")}


def shell_agent(task: str, context: str = "") -> dict:
    """Handles file system operations and system commands."""
    model = cfg("models", "fallback", default="llama3")
    try:
        r = llm_generate(
            model=model,
            system="You are a system administrator. Given a task, respond with ONLY the shell command to run. No explanation.",
            prompt=f"Task: {task}",
            stream=False,
            options={"temperature": 0.1}
        )
        command = r.get("response", "").strip().strip("`")
    except Exception as e:
        return {"agent": "shell", "task": task, "error": str(e)}
    
    result = shell_exec(command)
    return {"agent": "shell", "task": task, "command": command, "result": result}


def self_coder_agent(capability_needed: str) -> dict:
    """
    The self-improvement agent. When kirannn can't do something,
    it writes its own code/skill to handle it.
    """
    model = cfg("models", "code", default="deepseek-coder:6.7b")
    try:
        r = llm_generate(
            model=model,
            system="You write Python skill modules for an autonomous AI agent. Each skill must be a Python function that takes keyword arguments and returns a dict with {success, result/error}. Output ONLY the Python code, no explanation.",
            prompt=f"""Write a Python skill function for: {capability_needed}

The function should:
1. Be named after the capability (snake_case)
2. Accept **kwargs
3. Return {{"success": True/False, "result": ...}} 
4. Handle errors gracefully

Output only the Python function code.""",
            stream=False,
            options={"temperature": 0.2}
        )
        code = r.get("response", "")
    except Exception as e:
        return {"success": False, "error": str(e)}
    
    # Extract and save as a new skill
    code_match = re.search(r"```python\n?(.*?)```", code, re.DOTALL)
    skill_code = code_match.group(1) if code_match else code
    
    # Try to extract function name
    name_match = re.search(r"def (\w+)", skill_code)
    skill_name = name_match.group(1) if name_match else "custom_skill"
    
    # Save to skills_hub
    from pathlib import Path
    skill_path = Path(__file__).parent.parent / "skills_hub" / f"{skill_name}.py"
    skill_path.write_text(skill_code, encoding="utf-8")
    
    memory_append(f"Self-coded new skill: {skill_name} for '{capability_needed}'", "Learned Facts")
    
    return {"success": True, "skill_name": skill_name, "code": skill_code, "path": str(skill_path)}


def finance_agent(task: str, context: str = "") -> dict:
    """Finance specialist agent wrapper for orchestrator."""
    from agents.finance import run_finance_agent
    task_lower = task.lower()
    if any(kw in task_lower for kw in ["market", "brief", "ticker", "stock", "price"]):
        import re
        tickers = re.findall(r'\b[A-Z]{1,5}\b', task)
        if not tickers:
            tickers = ["AAPL", "GOOGL", "MSFT"]
        return run_finance_agent("market", tickers)
    else:
        return run_finance_agent("expenses", [task])

def health_agent(task: str, context: str = "") -> dict:
    """Health specialist agent wrapper for orchestrator."""
    from agents.health import run_health_agent
    task_lower = task.lower()
    if "sleep" in task_lower:
        return run_health_agent("sleep", {"info": task})
    else:
        return run_health_agent("fitness", task)

def twin_agent(task: str, context: str = "") -> dict:
    """Digital Twin specialist agent wrapper for orchestrator."""
    from agents.digital_twin import run_digital_twin
    task_lower = task.lower()
    if "email" in task_lower or "draft" in task_lower:
        return run_digital_twin("draft_email", {
            "recipient": "recipient",
            "topic": task,
            "key_points": [task]
        })
    else:
        return run_digital_twin("predict", {"scenario": task})

def debate_agent(task: str, context: str = "") -> dict:
    """Debate specialist agent wrapper for orchestrator."""
    from core.agent import run_debate
    res = run_debate(task)
    return {
        "agent": "debate",
        "task": task,
        "response": res.get("response", ""),
        "winner": res.get("winner"),
        "all_rounds": res.get("all_rounds")
    }

def github_agent(task: str, context: str = "") -> dict:
    """GitHub specialist agent wrapper for orchestrator."""
    from agents.github_agent import run_github_agent
    import re
    # Try regex first to find repo/project details in the task description
    project_name = "default"
    repo_path_or_url = "c:/my_ai_team"
    
    # Check for URLs
    urls = re.findall(r'https?://[^\s]+', task)
    if urls:
        repo_path_or_url = urls[0]
    else:
        # Look for absolute or relative paths
        path_match = re.search(r'(?:[a-zA-Z]:[\\/][^:*\?"<>|\r\n]+|/[^:*\?"<>|\r\n]+|\.[\\/][^:*\?"<>|\r\n]+)', task)
        if path_match:
            repo_path_or_url = path_match.group(0).rstrip(".")
            
    # Try to extract project name
    proj_match = re.search(r'(?:project|repo)\s+[\'"]?([a-zA-Z0-9_-]+)[\'"]?', task, re.IGNORECASE)
    if proj_match:
        project_name = proj_match.group(1)
    else:
        # Fallback to LLM to extract cleanly from task and context
        try:
            from core.llm import llm_generate
            parser_prompt = f"""Extract the project name and repository path/URL from this task description.
If not specified, use 'default' for project name and 'c:/my_ai_team' for repo path.

TASK: {task}
CONTEXT: {context}

Return ONLY a JSON object: {{"project_name": "...", "repo_path_or_url": "..."}}"""
            r = llm_generate(parser_prompt, model="llama3")
            res = json.loads(r.get("response", "{}"))
            project_name = res.get("project_name", project_name)
            repo_path_or_url = res.get("repo_path_or_url", repo_path_or_url)
        except:
            pass
            
    return run_github_agent(project_name, repo_path_or_url)

# ── Orchestrator: runs sub-agents in parallel ─────────────────────────────────

AGENT_MAP = {
    "researcher": researcher_agent,
    "coder":      coder_agent,
    "analyst":    analyst_agent,
    "writer":     writer_agent,
    "shell":      shell_agent,
    "finance":    finance_agent,
    "health":     health_agent,
    "twin":       twin_agent,
    "debate":     debate_agent,
    "github":     github_agent,
}

def orchestrate(plan: dict, max_workers: int = 4) -> dict:
    """
    Take a decomposed plan and execute sub-tasks based on their exact dependency graph (DAG).
    Tasks run concurrently as soon as all their dependencies are met.
    """
    from concurrent.futures import wait, FIRST_COMPLETED
    if not plan.get("success"):
        return {"error": "Invalid plan"}
    
    sub_tasks = plan["plan"].get("sub_tasks", [])
    results = {}
    task_context = {}  # accumulated context passed between tasks
    
    pending = {t["id"]: t for t in sub_tasks}
    completed = set()
    futures = {}
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        while pending or futures:
            # Schedule tasks whose dependencies are met
            to_submit = []
            for tid, t in pending.items():
                deps = t.get("depends_on", [])
                if all(d in completed for d in deps):
                    to_submit.append(tid)
            
            for tid in to_submit:
                t = pending.pop(tid)
                agent_fn = AGENT_MAP.get(t["agent"], researcher_agent)
                # Build context from completed dependencies
                dep_context = "\n".join(str(task_context.get(d, "")) for d in t.get("depends_on", []))
                all_context = dep_context + "\n" + "\n".join(task_context.values())
                
                f = executor.submit(agent_fn, t["description"], all_context[:1000])
                futures[f] = t
                
            if not futures:
                if pending:
                    # Deadlock due to circular or missing dependencies
                    for tid in pending:
                        results[tid] = {"error": "Deadlock/Unmet dependencies"}
                    break
                break
            
            # Wait for at least one future to complete
            done, _ = wait(futures.keys(), return_when=FIRST_COMPLETED)
            
            for f in done:
                t = futures.pop(f)
                try:
                    result = f.result(timeout=120)
                except Exception as e:
                    result = {"error": str(e)}
                    
                results[t["id"]] = result
                task_context[t["id"]] = _extract_text(result)
                completed.add(t["id"])
                memory_append(f"Task {t['id']} [{t['agent']}]: {t['title']} → done", "Completed Tasks")
    
    return {
        "plan": plan["plan"],
        "results": results,
        "context": task_context
    }


def _extract_text(result: dict) -> str:
    """Pull the most useful text out of any result dict."""
    for key in ["findings", "analysis", "report", "response", "stdout", "result"]:
        if key in result and result[key]:
            return str(result[key])[:600]
    return str(result)[:300]