"""
core/code_context.py — Code Context Awareness using AST parsing.
Allows the agent to deeply understand Python codebases by extracting classes, functions, and docstrings.
"""
import ast
import os
from pathlib import Path
from core.logger import logger

class CodeContextAnalyzer:
    """Parses Python code to provide structural context to the LLM."""

    def __init__(self, root_dir: str):
        self.root_dir = Path(root_dir)

    def analyze_file(self, filepath: str) -> dict:
        """Parse a single Python file and extract its structure."""
        full_path = self.root_dir / filepath
        if not full_path.exists() or not full_path.is_file() or not str(full_path).endswith('.py'):
            return {"error": "File not found or not a Python file"}

        try:
            with open(full_path, "r", encoding="utf-8") as f:
                content = f.read()
            
            tree = ast.parse(content)
            
            structure = {
                "file": str(filepath),
                "classes": [],
                "functions": [],
                "imports": []
            }

            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef):
                    methods = [n.name for n in node.body if isinstance(n, ast.FunctionDef)]
                    structure["classes"].append({
                        "name": node.name,
                        "docstring": ast.get_docstring(node),
                        "methods": methods
                    })
                elif isinstance(node, ast.FunctionDef):
                    # Only grab top-level functions
                    if not any(isinstance(parent, ast.ClassDef) for parent in ast.walk(tree) if hasattr(parent, 'body') and node in parent.body):
                         structure["functions"].append({
                             "name": node.name,
                             "docstring": ast.get_docstring(node),
                             "args": [a.arg for a in node.args.args]
                         })
                elif isinstance(node, ast.Import):
                    for alias in node.names:
                        structure["imports"].append(alias.name)
                elif isinstance(node, ast.ImportFrom):
                    structure["imports"].append(f"{node.module}")

            return structure

        except Exception as e:
            logger.error(f"Failed to parse {filepath}: {e}")
            return {"error": str(e)}

    def search_codebase(self, query: str) -> list:
        """Find files containing a specific class or function name."""
        # Simple implementation for now, could be improved with an index
        results = []
        for root, _, files in os.walk(self.root_dir):
            if '.venv' in root or '__pycache__' in root or '.git' in root:
                continue
            for file in files:
                if file.endswith('.py'):
                    rel_path = Path(root).relative_to(self.root_dir) / file
                    try:
                         with open(Path(root) / file, "r", encoding="utf-8") as f:
                             content = f.read()
                             if query in content:
                                 # Do a deeper parse if matched
                                 struct = self.analyze_file(str(rel_path))
                                 results.append(struct)
                    except Exception:
                         pass
        return results

    def format_for_llm(self, structure: dict) -> str:
        """Format the AST structure into a prompt-friendly string."""
        if "error" in structure:
            return f"Error analyzing code: {structure['error']}"

        res = [f"File: {structure['file']}"]
        res.append("Imports: " + ", ".join(structure.get("imports", [])))
        res.append("\nClasses:")
        for c in structure.get("classes", []):
            res.append(f"  class {c['name']}:")
            if c['docstring']:
                res.append(f"    \"\"\"{c['docstring'].split(chr(10))[0]}\"\"\"")
            if c['methods']:
                res.append(f"    Methods: {', '.join(c['methods'])}")
                
        res.append("\nFunctions:")
        for f in structure.get("functions", []):
            res.append(f"  def {f['name']}({', '.join(f['args'])}):")
            if f['docstring']:
                res.append(f"    \"\"\"{f['docstring'].split(chr(10))[0]}\"\"\"")

        return "\n".join(res)

def get_code_analyzer(root_dir: str = ".") -> CodeContextAnalyzer:
    return CodeContextAnalyzer(root_dir)
