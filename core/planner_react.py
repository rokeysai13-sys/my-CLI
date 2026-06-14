"""
core/planner_react.py — ReAct-style Task Planner.
Decomposes complex goals into subtask DAGs and auto-routes them to the right agents.
"""
import json
from core.logger import logger
from core.llm import llm_generate
from config.loader import cfg


def react_plan(goal: str, model: str = None) -> dict:
    """
    ReAct-style planning: Thought → Action → Observation loop.
    Decomposes a complex goal into a structured execution plan.
    
    Args:
        goal: The user's complex request (e.g., "prepare my internship applications")
        model: LLM model to use for planning
        
    Returns:
        dict with 'goal', 'thoughts', 'plan' (list of subtasks)
    """
    if model is None:
        model = cfg("models", "planner", default="llama3")

    system_prompt = """You are an expert task planner. Given a complex goal, decompose it into
a series of concrete subtasks. For each subtask, assign the best agent type.

Available agent types:
- researcher: web search, information gathering, fact-checking
- coder: write code, fix bugs, create scripts
- analyst: analyze data, synthesize findings, compare options
- writer: create documents, emails, reports, summaries
- shell: run system commands, file operations
- browser: visit websites, fill forms, extract data
- finance: budget analysis, expenses, market trends, stocks
- health: fitness tracking, sleep hygiene, recovery, wellness
- twin: digital twin simulation of user preferences, email drafting
- debate: resolve complex questions or trade-offs via multi-agent debate
- github: sync repository data, check git status, update project context in memory

Respond in this JSON format:
{
  "thoughts": "Your reasoning about how to break this down",
  "plan": [
    {
      "id": 1,
      "task": "Description of subtask",
      "agent": "agent_type",
      "depends_on": [],
      "priority": "high/medium/low",
      "estimated_minutes": 5
    }
  ],
  "total_estimated_minutes": 30
}"""

    prompt = f"Decompose this goal into an actionable plan:\n\n{goal}"

    try:
        raw = llm_generate(prompt, model=model, system=system_prompt)
        
        # Parse JSON from response
        if "```json" in raw:
            raw = raw.split("```json")[1].split("```")[0]
        elif "```" in raw:
            raw = raw.split("```")[1].split("```")[0]

        plan = json.loads(raw.strip())
        plan["goal"] = goal
        plan["status"] = "planned"
        
        logger.info(f"ReAct plan created: {len(plan.get('plan', []))} subtasks for '{goal[:50]}...'")
        return plan

    except json.JSONDecodeError:
        logger.warning("Failed to parse plan JSON, returning raw response")
        return {
            "goal": goal,
            "thoughts": raw,
            "plan": [{"id": 1, "task": goal, "agent": "researcher", "depends_on": [], "priority": "high"}],
            "status": "fallback"
        }
    except Exception as e:
        logger.error(f"Planning failed: {e}")
        return {"goal": goal, "error": str(e), "status": "error"}


def execute_plan(plan: dict) -> dict:
    """
    Execute a ReAct plan by routing subtasks to the appropriate agents.
    Respects dependency ordering.
    """
    from core.subagents import orchestrate
    
    if plan.get("status") == "error":
        return {"error": "Cannot execute a failed plan", "plan": plan}

    # Convert our plan format to the orchestrator's expected format
    orchestrator_plan = {
        "success": True,
        "plan": {
            "goal": plan["goal"],
            "sub_tasks": []
        }
    }

    for task in plan.get("plan", []):
        orchestrator_plan["plan"]["sub_tasks"].append({
            "id": task["id"],
            "task": task["task"],
            "agent": task["agent"],
            "depends_on": task.get("depends_on", [])
        })

    logger.info(f"Executing plan with {len(orchestrator_plan['plan']['sub_tasks'])} tasks...")
    result = orchestrate(orchestrator_plan)
    
    return {
        "goal": plan["goal"],
        "plan": plan,
        "execution": result,
        "status": "executed"
    }
