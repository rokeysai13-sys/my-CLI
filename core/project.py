"""
core/project.py — Project Memory System
Manages stateful projects, keeping track of status, next steps, architectural decisions, repositories, and context.
"""
import json
import datetime
from pathlib import Path
from core.logger import logger

PROJECTS_FILE = Path(__file__).parent.parent / "memory" / "projects.json"

class Project:
    def __init__(self, name: str, status: str = "active", next_steps: list = None, decisions: list = None, repos: list = None, context: str = "", created_at: str = None, updated_at: str = None, repo: str = "", architecture: str = "", todos: list = None, issues: list = None, progress: int = 0):
        self.name = name
        self.status = status  # active, completed, archived
        self.next_steps = next_steps or []
        self.decisions = decisions or []
        self.repos = repos or []
        self.context = context
        self.created_at = created_at or datetime.datetime.now().isoformat()
        self.updated_at = updated_at or datetime.datetime.now().isoformat()
        self.repo = repo
        self.architecture = architecture
        self.todos = todos or []
        self.issues = issues or []
        self.progress = progress

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "status": self.status,
            "next_steps": self.next_steps,
            "decisions": self.decisions,
            "repos": self.repos,
            "context": self.context,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "repo": self.repo,
            "architecture": self.architecture,
            "todos": self.todos,
            "issues": self.issues,
            "progress": self.progress
        }

class ProjectManager:
    def __init__(self):
        self.projects = {}
        self.load_projects()

    def load_projects(self):
        """Load persistent projects from projects.json."""
        if PROJECTS_FILE.exists():
            try:
                data = json.loads(PROJECTS_FILE.read_text(encoding="utf-8"))
                for name, p_data in data.items():
                    self.projects[name] = Project(**p_data)
                logger.info(f"Loaded {len(self.projects)} projects.")
            except Exception as e:
                logger.error(f"Failed to load projects: {e}")

    def save_projects(self):
        """Persist projects to projects.json."""
        try:
            PROJECTS_FILE.parent.mkdir(parents=True, exist_ok=True)
            data = {name: p.to_dict() for name, p in self.projects.items()}
            PROJECTS_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")
        except Exception as e:
            logger.error(f"Failed to save projects: {e}")

    def create_project(self, name: str, repos: list = None, context: str = "") -> Project:
        """Create a new project workspace context."""
        project = Project(name=name, repos=repos, context=context)
        self.projects[name] = project
        self.save_projects()
        logger.info(f"Project context created: '{name}'")
        return project

    def update_project(self, name: str, status: str = None, next_steps: list = None, context: str = None) -> dict:
        """Update fields of an existing project workspace."""
        project = self.projects.get(name)
        if not project:
            return {"error": "Project not found"}
        
        if status is not None:
            project.status = status
        if next_steps is not None:
            project.next_steps = next_steps
        if context is not None:
            project.context = context
            
        project.updated_at = datetime.datetime.now().isoformat()
        self.save_projects()
        return {"status": "success", "project": project.to_dict()}

    def add_decision(self, name: str, decision: str) -> dict:
        """Log an architectural/development decision directly to a project's history."""
        project = self.projects.get(name)
        if not project:
            return {"error": "Project not found"}
        
        decision_entry = {
            "timestamp": datetime.datetime.now().isoformat(),
            "decision": decision
        }
        project.decisions.append(decision_entry)
        project.updated_at = datetime.datetime.now().isoformat()
        self.save_projects()
        return {"status": "success", "project": project.to_dict()}
