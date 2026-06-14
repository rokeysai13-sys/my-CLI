"""
agents/github_agent.py — GitHub Agent Wrapper
Allows the orchestrator and planner to invoke repository syncing as a sub-agent task.
"""
from core.github_memory import sync_github_repo

def run_github_agent(project_name: str, repo_path_or_url: str) -> dict:
    """Sync repository and update project memory context."""
    res = sync_github_repo(project_name, repo_path_or_url)
    if res.get("status") == "success":
        p = res.get("project", {})
        return {
            "agent": "github",
            "task": f"Sync repository {repo_path_or_url}",
            "result": f"Successfully synced repo data into Project Memory for '{project_name}'.\n\nContext:\n{p.get('context')}",
            "next_steps": p.get("next_steps", [])
        }
    return {
        "agent": "github",
        "task": f"Sync repository {repo_path_or_url}",
        "error": res.get("error", "Sync failed.")
    }
