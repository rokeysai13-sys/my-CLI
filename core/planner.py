"""
core/planner.py — Task Decomposition Engine
Breaks big goals into structured sub-tasks with assigned specialist agents.
"""
import json, re
from config.loader import cfg
from core.llm import llm_generate

PLANNER_SYSTEM = """You are a master project planner for an autonomous AI agent system called kirannn.

When given a high-level goal, you MUST respond with ONLY a JSON plan like this:
{
  "goal": "original goal",
  "complexity": "simple|medium|complex",
  "estimated_steps": 3,
  "sub_tasks": [
    {
      "id": 1,
      "title": "Short task name",
      "description": "What exactly needs to be done",
      "agent": "researcher|coder|analyst|writer|shell|finance|health|twin|debate|github",
      "depends_on": [],
      "parallel": true
    }
  ],
  "final_output": "What the final deliverable should be"
}

Agent types:
- researcher: web search, URL fetching, data gathering
- coder: writing/executing Python or shell code
- analyst: synthesizing data, finding patterns, scoring confidence
- writer: drafting reports, summaries, structured documents
- shell: file operations, system commands, process management
- finance: budget analysis, expenses, market trends, stocks
- health: fitness tracking, sleep hygiene, recovery, wellness
- twin: digital twin simulation of user preferences, email drafting
- debate: resolve complex questions or trade-offs via multi-agent debate
- github: sync repository data, check git status, update project context in memory

Respond ONLY with the JSON. No other text."""


def decompose(goal: str, model: str = None) -> dict:
    """Break a goal into structured sub-tasks."""
    model = model or cfg("models", "planner", default="llama3")
    try:
        r = llm_generate(
            model=model,
            system=PLANNER_SYSTEM,
            prompt=f"Create a plan for: {goal}",
            stream=False,
            options={"temperature": 0.2}
        )
        raw = r.get("response", "").strip()
        
        # Extract JSON
        match = re.search(r'\{.*\}', raw, re.DOTALL)
        if match:
            plan = json.loads(match.group())
            return {"success": True, "plan": plan}
        return {"success": False, "error": "Could not parse plan", "raw": raw}
    except Exception as e:
        return {"success": False, "error": str(e)}


def format_plan_md(plan: dict) -> str:
    """Format a plan as readable markdown."""
    if not plan.get("success"):
        return f"Planning failed: {plan.get('error')}"
    
    p = plan["plan"]
    lines = [
        f"## 📋 Plan: {p.get('goal', 'Unknown')}",
        f"**Complexity:** {p.get('complexity', '?')} | **Steps:** {p.get('estimated_steps', '?')}",
        "",
        "### Sub-Tasks"
    ]
    sub_tasks = p.get("sub_tasks") or p.get("plan") or []
    for t in sub_tasks:
        parallel = "⚡ parallel" if t.get("parallel") else "→ sequential"
        deps = f" (after {t['depends_on']})" if t.get("depends_on") else ""
        title = t.get("title") or t.get("task", "Subtask")
        desc = t.get("description") or t.get("task", "")
        lines.append(f"{t['id']}. **[{t['agent'].upper()}]** {title}{deps} _{parallel}_")
        lines.append(f"   {desc}")
    
    lines += ["", f"**Final Output:** {p.get('final_output', '?')}"]
    return "\n".join(lines)