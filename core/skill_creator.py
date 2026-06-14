"""
core/skill_creator.py — Skill Auto-Creation Engine
Allows the system to write new skills (Python scripts) dynamically into the skills_hub directory,
extending its own capabilities at runtime.
"""
import os
import re
from pathlib import Path
from core.logger import logger
from core.llm import llm_generate
from core.tools import reload_skills

SKILLS_HUB_DIR = Path(__file__).parent.parent / "skills_hub"


class SkillCreator:
    """Generates new Python skills for the agent."""

    def __init__(self):
        SKILLS_HUB_DIR.mkdir(parents=True, exist_ok=True)

    def generate_skill(self, capability_description: str) -> dict:
        """
        Generate a new Python file to implement a requested capability.
        The file is saved to skills_hub/ and tools are reloaded.
        """
        prompt = f"""You are an expert Python developer writing a new skill for an AI agent.
The skill will be placed in the `skills_hub/` directory and automatically loaded.

REQUIREMENTS:
1. Create a Python script that implements: {capability_description}
2. The script must contain one or more functions with clear type hints and comprehensive docstrings.
3. The docstring MUST describe exactly what the function does, as this is used for LLM tool selection.
4. If it requires external libraries, mention them in comments.
5. Provide ONLY valid Python code. No markdown formatting (no ```python).

Example structure:
import requests

def fetch_weather(city: str) -> str:
    \"\"\"Fetches the current weather for a given city.\"\"\"
    return "Sunny"
"""
        try:
            logger.info(f"Generating new skill: {capability_description[:50]}...")
            code = llm_generate(prompt, model="deepseek-coder")
            
            # Clean markdown if the LLM ignored instructions
            if code.startswith("```python"):
                code = code.split("```python")[1].split("```")[0].strip()
            elif code.startswith("```"):
                code = code.split("```")[1].split("```")[0].strip()

            # Extract a good filename from the code or description
            filename_match = re.search(r'def\s+([a-z0-9_]+)\(', code)
            if filename_match:
                filename = f"{filename_match.group(1)}.py"
            else:
                filename = "new_skill.py"

            filepath = SKILLS_HUB_DIR / filename
            
            # Avoid overwriting existing important skills blindly
            counter = 1
            while filepath.exists():
                filepath = SKILLS_HUB_DIR / f"{filepath.stem}_{counter}.py"
                counter += 1

            filepath.write_text(code, encoding="utf-8")
            
            # Reload tools
            reload_results = reload_skills()
            
            return {
                "status": "success",
                "filename": filepath.name,
                "path": str(filepath),
                "code": code,
                "reload_info": reload_results
            }

        except Exception as e:
            logger.error(f"Skill creation failed: {e}")
            return {"status": "error", "error": str(e)}


# ── Singleton ────────────────────────────────────────────────────────

_instance = None

def get_skill_creator() -> SkillCreator:
    global _instance
    if _instance is None:
        _instance = SkillCreator()
    return _instance
