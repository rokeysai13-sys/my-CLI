"""
core/github_memory.py — GitHub Memory Module
Queries local git status and GitHub API details, summarizes repository state, and wires it directly into Project Memory.
"""
import os
import subprocess
import requests
import json
import datetime
from pathlib import Path
from core.logger import logger
from core.llm import llm_generate
from core.project import ProjectManager
from config.loader import cfg

def get_git_info(repo_path: str) -> dict:
    """Retrieve branch, status, and recent commits from a local git repository."""
    info = {"local": True, "branch": "unknown", "status": "", "commits": []}
    p = Path(repo_path).resolve()
    
    if not (p / ".git").exists():
        info["local"] = False
        return info

    try:
        # Get current branch
        branch = subprocess.check_output(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=str(p),
            stderr=subprocess.DEVNULL
        ).decode("utf-8").strip()
        info["branch"] = branch
    except:
        pass

    try:
        # Get recent 5 commits
        commits_raw = subprocess.check_output(
            ["git", "log", "-n", "5", "--oneline"],
            cwd=str(p),
            stderr=subprocess.DEVNULL
        ).decode("utf-8").strip()
        info["commits"] = [c.strip() for c in commits_raw.split("\n") if c.strip()]
    except:
        pass

    try:
        # Get uncommitted changes summary
        status_raw = subprocess.check_output(
            ["git", "status", "--short"],
            cwd=str(p),
            stderr=subprocess.DEVNULL
        ).decode("utf-8").strip()
        info["status"] = status_raw
    except:
        pass

    return info

def get_github_api_info(repo_url: str) -> dict:
    """Retrieve details from the GitHub REST API for a remote URL."""
    info = {"local": False, "repo_name": "", "description": "", "open_issues_count": 0, "commits": []}
    
    # Parse owner and repo from URL (e.g. https://github.com/owner/repo)
    parts = repo_url.replace("https://github.com/", "").replace(".git", "").split("/")
    if len(parts) < 2:
        return info
    
    owner, repo = parts[0], parts[1]
    info["repo_name"] = f"{owner}/{repo}"

    headers = {"User-Agent": "kirannn-agent/1.0"}
    token = os.getenv("GITHUB_TOKEN") or cfg("api_keys", "github")
    if token:
        headers["Authorization"] = f"token {token}"

    try:
        # Get repo metadata
        r = requests.get(f"https://api.github.com/repos/{owner}/{repo}", headers=headers, timeout=5)
        if r.status_code == 200:
            res = r.json()
            info["description"] = res.get("description", "")
            info["open_issues_count"] = res.get("open_issues_count", 0)
    except:
        pass

    try:
        # Get recent 5 commits
        r = requests.get(f"https://api.github.com/repos/{owner}/{repo}/commits?per_page=5", headers=headers, timeout=5)
        if r.status_code == 200:
            info["commits"] = [c["commit"]["message"].split("\n")[0] for c in r.json()]
    except:
        pass

    return info

def sync_github_repo(project_name: str, repo_path_or_url: str) -> dict:
    """Sync repo status details directly into Project Memory."""
    logger.info(f"[GITHUB MEMORY] Syncing project '{project_name}' with repo: {repo_path_or_url}")
    
    # 1. Determine if local path or remote URL and fetch stats
    repo_data = {}
    is_local = os.path.exists(repo_path_or_url) or Path(repo_path_or_url).is_absolute()
    if is_local:
        repo_data = get_git_info(repo_path_or_url)
    else:
        repo_data = get_github_api_info(repo_path_or_url)

    # 2. Summarize repository state using LLM
    summary_prompt = f"""You are the Project Memory coordinator for an autonomous agent system. 
You are given repository status details. Please analyze them and write a concise, highly detailed summary:
1. What is the current focus of the repository based on recent commits or status?
2. What are the uncommitted changes or active developments?
3. Inferred immediate next steps.

REPOSITORY DETAILS:
{json.dumps(repo_data, indent=2)}

Respond with a clean summary. Avoid fluff."""
    
    try:
        summary_res = llm_generate(summary_prompt, model="mistral")
        summary = summary_res.get("response", "Could not analyze repository.")
    except Exception as e:
        summary = f"Error analyzing repo: {e}"

    # 3. Write/Sync directly to Project Memory
    manager = ProjectManager()
    project = manager.projects.get(project_name)
    
    if not project:
        # Create new project if it doesn't exist
        project = manager.create_project(name=project_name, repos=[repo_path_or_url])
    
    # Update project details
    project.repo = repo_path_or_url
    project.context = f"GitHub Sync Details:\n- Location: {repo_path_or_url}\n- Active Branch: {repo_data.get('branch', 'main')}\n\nRepository Status Summary:\n{summary}"
    
    # 4. Deep scanning (Repository Intelligence)
    if is_local:
        project.todos = extract_code_todos(repo_path_or_url)
        project.architecture = generate_architecture_overview(repo_path_or_url)
    else:
        project.todos = []
        project.architecture = f"Remote Repository: {repo_path_or_url}"
        
    project.issues = extract_issues(repo_path_or_url, repo_data)
    project.progress = calculate_progress(len(project.todos), repo_path_or_url)

    # Infer next steps list from LLM response and update project
    next_steps_prompt = f"""Given this repository summary, extract exactly 3 concrete, bullet-pointed next steps for the agent to execute.
Return ONLY a JSON array of strings: ["step 1", "step 2", "step 3"]

SUMMARY:
{summary}"""
    
    try:
        ns_res = llm_generate(next_steps_prompt, model="llama3")
        raw = ns_res.get("response", "[]")
        start_idx = raw.find('[')
        end_idx = raw.rfind(']')
        if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
            raw = raw[start_idx:end_idx+1]
        next_steps = json.loads(raw.strip())
        if isinstance(next_steps, list):
            project.next_steps = next_steps
    except Exception as e:
        logger.warning(f"Failed to infer next steps: {e}")

    # Add a sync decision
    project.decisions.append({
        "timestamp": datetime.datetime.now().isoformat(),
        "decision": f"Synced repository data from {repo_path_or_url}."
    })
    
    project.updated_at = datetime.datetime.now().isoformat()
    manager.save_projects()
    
    return {
        "status": "success",
        "project": project.to_dict(),
        "repo_data": repo_data
    }

def extract_code_todos(directory_path: str) -> list:
    """Scan all source files for comments containing TODO or FIXME."""
    import re
    todos = []
    p = Path(directory_path).resolve()
    if not p.exists() or not p.is_dir():
        return todos

    exclude_dirs = {".git", ".venv", "node_modules", "__pycache__", ".pytest_cache", ".system_generated", ".gemini", "venv", "dist", "build"}
    valid_exts = {".py", ".js", ".ts", ".html", ".css", ".json", ".yml", ".yaml", ".md", ".sh", ".ps1"}
    
    for root, dirs, files in os.walk(str(p)):
        dirs[:] = [d for d in dirs if d not in exclude_dirs]
        for file in files:
            file_path = Path(root) / file
            if file_path.suffix not in valid_exts:
                continue
            
            try:
                rel_path = file_path.relative_to(p).as_posix()
            except ValueError:
                rel_path = file_path.name

            try:
                content = file_path.read_text(encoding="utf-8", errors="replace")
                for line_num, line in enumerate(content.splitlines(), 1):
                    match = re.search(r"\b(TODO|FIXME)\b\s*[:\-]?\s*(.*)", line, re.IGNORECASE)
                    if match:
                        todo_type = match.group(1).upper()
                        todo_text = match.group(2).strip()
                        todos.append({
                            "file": rel_path,
                            "line": line_num,
                            "type": todo_type,
                            "text": todo_text
                        })
            except Exception as e:
                logger.warning(f"Failed to read file for TODO scan: {file_path}. Error: {e}")
                
    return todos

def generate_architecture_overview(directory_path: str) -> str:
    """Generate architecture outline using LLM based on directory contents and tech stack files."""
    p = Path(directory_path).resolve()
    if not p.exists() or not p.is_dir():
        return "Not a local repository path."

    exclude_dirs = {".git", ".venv", "node_modules", "__pycache__", ".pytest_cache", ".system_generated", ".gemini", "venv", "dist", "build"}
    structure = []
    try:
        for item in sorted(p.iterdir()):
            if item.name in exclude_dirs:
                continue
            if item.is_dir():
                sub_items = [sub.name for sub in sorted(item.iterdir()) if not sub.name.startswith("__")][:5]
                sub_str = ", ".join(sub_items)
                structure.append(f"- {item.name}/ ({sub_str})")
            else:
                structure.append(f"- {item.name}")
    except Exception as e:
        return f"Failed to list directory structure: {e}"
            
    tech_stack = []
    for conf_file in ["requirements.txt", "package.json", "setup.py", "cargo.toml"]:
        if (p / conf_file).exists():
            tech_stack.append(conf_file)
            
    readme_content = ""
    readme_path = p / "README.md"
    if readme_path.exists():
        try:
            readme_content = readme_path.read_text(encoding="utf-8", errors="replace")[:1000]
        except:
            pass

    prompt = (
        f"Generate a technical architecture overview for the project located at '{directory_path}'.\n\n"
        f"Directory structure:\n" + "\n".join(structure) + "\n\n"
        f"Detected configuration files: {', '.join(tech_stack)}\n\n"
        f"README Snippet:\n{readme_content}\n\n"
        f"Write a concise, professional technical overview. Explain the stack, main directory modules, and core flow. Avoid generic fluff."
    )
    
    try:
        res = llm_generate(prompt=prompt, system="You are a principal software architect summarizing codebases.", model="llama3")
        return res.get("response", "Could not generate architecture overview.").strip()
    except Exception as e:
        logger.error(f"Failed to generate architecture overview: {e}")
        return f"Architecture analysis failed: {e}"

def calculate_progress(todos_count: int, repo_path: str) -> int:
    """Calculate progress percentage based on completed tasks in missions vs pending todos."""
    completed_count = 0
    missions_file = Path(__file__).parent.parent / "memory" / "missions.json"
    if missions_file.exists():
        try:
            missions = json.loads(missions_file.read_text(encoding="utf-8"))
            for m_data in missions.values():
                progress = m_data.get("progress", {})
                completed_count += len(progress.get("completed_tasks", []))
        except Exception as e:
            logger.warning(f"Error loading missions for progress: {e}")
            
    total = completed_count + todos_count
    if total == 0:
        return 100
    progress_pct = int((completed_count / total) * 100)
    return min(max(progress_pct, 0), 100)

def extract_issues(repo_path_or_url: str, repo_data: dict) -> list:
    """Extract issues list from git status or remote issues."""
    issues = []
    
    status_raw = repo_data.get("status", "")
    if status_raw:
        for line in status_raw.splitlines():
            line = line.strip()
            if not line:
                continue
            parts = line.split(maxsplit=1)
            if len(parts) == 2:
                symbol, file_name = parts[0], parts[1]
                desc_map = {"M": "Modified", "A": "Added", "D": "Deleted", "??": "Untracked"}
                desc = desc_map.get(symbol, f"Status '{symbol}'")
                issues.append({
                    "title": f"Uncommitted changes in: {file_name}",
                    "description": f"File is currently in '{desc}' state. Needs to be committed or discarded.",
                    "source": "local_git"
                })
                
    remote_issues_count = repo_data.get("open_issues_count", 0)
    if remote_issues_count > 0:
        issues.append({
            "title": f"Remote Open Issues: {remote_issues_count}",
            "description": f"There are {remote_issues_count} open issues on remote repository.",
            "source": "github_api"
        })
        
    if not issues:
        issues.append({
            "title": "Clean repository status",
            "description": "All changes are committed and no outstanding git issues detected.",
            "source": "git_status"
        })
        
    return issues
