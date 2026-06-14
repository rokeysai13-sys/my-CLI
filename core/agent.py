"""
core/agent.py — Master Orchestrator (FIXED)
Better tool-call parsing — handles model wrapping JSON in text/code blocks
"""
import json, re, requests
from pathlib import Path
from core.logger import logger
from .tools import call_tool, tools_manifest, memory_read, soul_read, memory_append
from config.loader import cfg

OLLAMA_URL   = lambda: cfg("models", "ollama_url", default="http://localhost:11434") + "/api/generate"
DEFAULT_MODEL = lambda: cfg("models", "fallback", default="llama3")
MAX_STEPS    = cfg("agents", "max_steps", default=10)

SYSTEM_PROMPT = """You are kirannn, an autonomous AI agent with real tools.

{soul}

{tools}

## STRICT RULES FOR TOOL USE
When you want to use a tool, respond with ONLY this JSON — nothing else, no explanation:
{{"tool": "tool_name", "args": {{"arg1": "value1"}}}}

When you have your final answer (no more tools needed), respond in plain text.
NEVER mix JSON and text in the same response.
NEVER ask the user permission before using a tool — just use it.
NEVER say "Please let me know when ready" — just act.

## Examples
User: list files in {base_dir}
You: {{"tool": "file_list", "args": {{"path": "{base_dir}"}}}}

User: what time is it
You: {{"tool": "shell_exec", "args": {{"command": "date /t"}}}}

User: search for latest AI news
You: {{"tool": "web_search", "args": {{"query": "latest AI news 2026"}}}}
"""

# Resolve base_dir once at module level
_BASE_DIR = str(Path(__file__).parent.parent.resolve()).replace("\\", "/")

def run_agent(message: str, model: str = None, session_id: str = None) -> dict:
    model = model or DEFAULT_MODEL()
    
    # Intercept "Continue Jarvis"
    is_continue_cmd = message.strip().lower().replace(".", "").replace("!", "") == "continue jarvis"
    if is_continue_cmd:
        from core.github_memory import sync_github_repo
        from core.project import ProjectManager
        from core.mission import MissionManager
        import asyncio
        
        # Determine active project name
        pm = ProjectManager()
        active_project_name = "Jarvis"
        if pm.projects:
            sorted_projects = sorted(pm.projects.values(), key=lambda p: p.updated_at, reverse=True)
            active_project_name = sorted_projects[0].name
        
        # Default repo path is base directory of this agent system
        repo_path = str(Path(__file__).parent.parent.resolve()).replace("\\", "/")
        
        logger.info(f"[CONTINUE JARVIS] Found active project: '{active_project_name}'. Syncing repository intelligence...")
        
        # Run repository sync/deep scan
        sync_res = sync_github_repo(active_project_name, repo_path)
        project_dict = sync_res.get("project", {})
        
        # Formulate next step using LLM
        prompt = (
            f"Analyze the repository intelligence for project '{active_project_name}':\n"
            f"Repo location: {project_dict.get('repo')}\n"
            f"Architecture overview: {project_dict.get('architecture')}\n"
            f"Open Todos: {json.dumps(project_dict.get('todos', []), indent=2)}\n"
            f"Open Issues: {json.dumps(project_dict.get('issues', []), indent=2)}\n"
            f"Est. Progress: {project_dict.get('progress')}%\n\n"
            f"Based on this codebase state, formulate the single most important and concrete task to execute next to advance the project.\n"
            f"Explain your reasoning and state the task clearly.\n\n"
            f"Return your decision in JSON format matching this exact schema:\n"
            f"{{\n"
            f"  \"reasoning\": \"Your detailed reasoning...\",\n"
            f"  \"task_title\": \"Brief title of the next task\",\n"
            f"  \"task_description\": \"Detailed description of exactly what needs to be implemented or run.\"\n"
            f"}}\n"
            f"Return only the JSON object."
        )
        
        next_task = {"task_title": "Continue development", "task_description": "Advance the project roadmap"}
        try:
            from core.llm import llm_generate
            raw_decision = llm_generate(prompt=prompt, system="You are an autonomous engineering lead deciding the next step.", model="llama3")
            raw_clean = raw_decision.strip()
            match = re.search(r"```json\s*(.*?)\s*```", raw_clean, re.DOTALL)
            if match:
                raw_clean = match.group(1)
            else:
                match_braces = re.search(r"(\{.*\})", raw_clean, re.DOTALL)
                if match_braces:
                    raw_clean = match_braces.group(1)
            next_task = json.loads(raw_clean)
        except Exception as e:
            logger.warning(f"Failed to dynamically formulate next task: {e}")
            
        logger.info(f"[CONTINUE JARVIS] Selected task: '{next_task.get('task_title')}' - {next_task.get('task_description')}")
        
        # Spawn a new mission to execute this task
        mission_manager = MissionManager()
        mission = mission_manager.create_mission(
            goal=f"{next_task.get('task_title')}: {next_task.get('task_description')}",
            mode="multi_agent"
        )
        
        # Execute the first step of this mission autonomously!
        logger.info(f"[CONTINUE JARVIS] Launching step 1 of mission {mission.mission_id}...")
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
        if loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(lambda: asyncio.run(mission_manager.execute_mission_step(mission.mission_id)))
                step_res = future.result()
        else:
            step_res = loop.run_until_complete(mission_manager.execute_mission_step(mission.mission_id))
            
        response_text = (
            f"### 🤖 Continue Jarvis Executed\n\n"
            f"**Repository Intelligence Summary for '{active_project_name}':**\n"
            f"- **Repo Path:** `{project_dict.get('repo')}`\n"
            f"- **Progress:** `{project_dict.get('progress')}%`\n"
            f"- **Found TODOs:** {len(project_dict.get('todos', []))}\n"
            f"- **Found Issues:** {len(project_dict.get('issues', []))}\n\n"
            f"**Next Task Selected (Reasoning: *{next_task.get('reasoning', 'N/A')}*):**\n"
            f"> **{next_task.get('task_title')}**  \n"
            f"> {next_task.get('task_description')}\n\n"
            f"**Autonomously Spawned Mission:** `{mission.mission_id}`  \n"
            f"**Step Execution Result:**\n"
            f"```\n"
            f"Status: {step_res.get('status')}\n"
            f"Success: {step_res.get('success', 'N/A')}\n"
            f"Result: {step_res.get('result', 'No output.')}\n"
            f"```"
        )
        
        return {"response": response_text, "project": project_dict, "mission_id": mission.mission_id, "step_result": step_res}

    soul   = soul_read().get("result", "")[:600]
    memory = memory_read().get("result", "")[:800]
    tools  = tools_manifest()

    complex_keywords = ["research", "analyze", "investigate", "compare",
                        "comprehensive", "deep dive", "study", "report on",
                        "explain in detail", "overview of"]
    is_complex = (any(kw in message.lower() for kw in complex_keywords)
                  or len(message) > 400)

    if is_complex:
        return run_full_pipeline(message, model)

    return run_tool_loop(message, model, soul, memory, tools)


def run_tool_loop(message: str, model: str, soul: str, memory: str, tools: str) -> dict:
    system = SYSTEM_PROMPT.format(soul=soul, tools=tools, base_dir=_BASE_DIR)
    trace  = []
    # Build conversation as a growing prompt
    conversation = f"Memory snapshot:\n{memory}\n\nUser request: {message}"

    for step in range(MAX_STEPS):
        try:
            from core.llm import llm_generate
            r = llm_generate(
                model=model,
                system=system,
                prompt=conversation,
                stream=False,
                options={"temperature": 0.2, "stop": ["\n\nUser:", "User:"]},
                timeout=90
            )
            reply = r.get("response", "").strip()
        except Exception as e:
            return {"response": f"Model error: {e}", "trace": trace}

        if not reply:
            # Empty reply — give model a nudge
            conversation += "\nAssistant: [thinking]\nContinue with your response:"
            continue

        tool_call = _parse_tool_call(reply)

        if tool_call:
            name   = tool_call.get("tool", "")
            args   = tool_call.get("args", {})

            if not name:
                break

            result = call_tool(name, **args)
            trace.append({"step": step+1, "tool": name, "args": args, "result": result})

            # Build result summary for next prompt
            if result.get("success"):
                result_text = _summarize_result(result)
            else:
                result_text = f"Tool failed: {result.get('error', 'unknown error')}"

            conversation += (
                f"\nAssistant called: {name}({json.dumps(args)[:100]})"
                f"\nTool result: {result_text[:800]}"
                f"\nNow provide your final answer to the user based on this result:"
            )
        else:
            # Plain text = final answer
            if trace:
                memory_append(f"Task: {message[:60]} | Tools: {[t['tool'] for t in trace]}")
            return {"response": reply, "trace": trace, "steps": len(trace)}

    # Fell through max steps — ask for summary
    try:
        from core.llm import llm_generate
        r = llm_generate(
            model=model,
            system="Summarize what was accomplished based on the tool results. Be concise.",
            prompt=conversation + "\n\nSummarize what you found/did:",
            stream=False,
            options={"temperature": 0.3},
            timeout=60
        )
        final = r.get("response", "Task completed.").strip()
    except:
        final = "Task completed. Check the trace for details."

    return {"response": final, "trace": trace, "steps": len(trace)}


def _parse_tool_call(text: str):
    """
    Robustly extract a tool call JSON from model output.
    Handles: plain JSON, ```json blocks, mixed text+JSON, etc.
    """
    text = text.strip()

    # 1. Pure JSON
    try:
        obj = json.loads(text)
        if "tool" in obj:
            return obj
    except:
        pass

    # 2. JSON inside ```json ... ``` or ``` ... ```
    for pattern in [r'```json\s*(\{.*?\})\s*```', r'```\s*(\{.*?\})\s*```']:
        m = re.search(pattern, text, re.DOTALL)
        if m:
            try:
                obj = json.loads(m.group(1))
                if "tool" in obj:
                    return obj
            except:
                pass

    # 3. Any JSON object containing "tool" key
    for m in re.finditer(r'\{[^{}]*"tool"\s*:[^{}]*\}', text, re.DOTALL):
        try:
            obj = json.loads(m.group())
            if "tool" in obj:
                return obj
        except:
            pass

    # 4. Nested JSON (args as nested object)
    m = re.search(r'\{.*"tool".*\}', text, re.DOTALL)
    if m:
        try:
            obj = json.loads(m.group())
            if "tool" in obj:
                return obj
        except:
            pass

    return None


def _summarize_result(result: dict) -> str:
    """Extract the most useful text from a tool result."""
    for key in ["result", "stdout", "findings", "text", "content", "response"]:
        val = result.get(key)
        if val:
            if isinstance(val, list):
                return json.dumps(val[:5])
            return str(val)[:600]
    return json.dumps(result)[:400]


# ── Full pipeline ─────────────────────────────────────────────────────────────

def run_full_pipeline(message: str, model: str = DEFAULT_MODEL) -> dict:
    from .planner import decompose, format_plan_md
    from .subagents import orchestrate, analyst_agent, writer_agent

    plan = decompose(message, model=model)
    plan_text = format_plan_md(plan)

    if not plan.get("success"):
        soul   = soul_read().get("result", "")[:600]
        memory = memory_read().get("result", "")[:600]
        return run_tool_loop(message, model, soul, memory, tools_manifest())

    orch = orchestrate(plan)
    all_findings = "\n\n".join(
        f"=== Task {tid} ===\n{text}"
        for tid, text in orch.get("context", {}).items()
    )

    final    = analyst_agent(f"Synthesize: {message}", all_findings)
    report   = writer_agent(message, all_findings + "\n\n" + final.get("analysis",""), title=message[:40])
    memory_append(f"Pipeline: '{message[:60]}' → {len(orch.get('results',{}))} tasks")

    return {
        "response":    report.get("report", final.get("analysis", "Pipeline completed")),
        "plan":        plan_text,
        "sub_results": orch.get("results", {}),
        "report_path": report.get("saved_to"),
        "trace":       [{"tool": "planner"}, {"tool": "orchestrator"}, {"tool": "writer"}],
        "pipeline":    True
    }


# ── Direct agent runners ──────────────────────────────────────────────────────

def run_debate(message: str) -> dict:
    from agents.debate import run_debate as domain_debate
    from agents.vote import vote as domain_vote
    # Run the featureful 2-round debate
    all_rounds, final_answers = domain_debate(message, rounds=2)
    # Vote for the winner
    winner, votes, best_answer = domain_vote(message, final_answers)
    return {
        "responses": final_answers,
        "best": best_answer,
        "winner": winner,
        "all_rounds": all_rounds,
        "votes": votes,
        "response": best_answer
    }


def run_code_agent(message: str) -> dict:
    from .subagents import coder_agent
    return coder_agent(message)


def run_research_agent(message: str) -> dict:
    from .subagents import researcher_agent, analyst_agent
    research = researcher_agent(message)
    analysis = analyst_agent(message, research.get("findings",""))
    return {
        "findings": research.get("findings"),
        "analysis": analysis.get("analysis"),
        "sources":  research.get("sources", []),
        "response": analysis.get("analysis", research.get("findings",""))
    }