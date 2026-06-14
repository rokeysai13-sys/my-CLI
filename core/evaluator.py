"""
core/evaluator.py — Self-Evaluation Loop.
Scores agent outputs 1-10 and retries if below threshold.
"""
import json
from core.logger import logger
from core.llm import llm_generate
from config.loader import cfg


class SelfEvaluator:
    """Grades agent outputs and triggers retries if quality is insufficient."""

    def __init__(self, threshold: int = 6, max_retries: int = 2):
        self.threshold = threshold
        self.max_retries = max_retries
        self.history = []  # Track all evaluations for quality monitoring

    def evaluate(self, task: str, output: str, agent_name: str = "unknown") -> dict:
        """
        Score an agent's output 1-10.
        
        Args:
            task: The original task/prompt
            output: The agent's response
            agent_name: Which agent produced this
            
        Returns:
            dict with 'score', 'feedback', 'pass'
        """
        model = cfg("models", "judge", default="llama3")

        eval_prompt = f"""You are a strict quality evaluator. Score this agent output from 1-10.

TASK: {task}

AGENT OUTPUT:
{output[:3000]}

Evaluate on these criteria:
1. Completeness — Does it fully address the task?
2. Accuracy — Are facts and claims correct?
3. Clarity — Is it well-structured and readable?
4. Actionability — Can the user act on this response?

Respond in JSON:
{{
  "score": 7,
  "criteria": {{
    "completeness": 8,
    "accuracy": 7,
    "clarity": 7,
    "actionability": 6
  }},
  "feedback": "Brief explanation of score",
  "improvements": ["suggestion 1", "suggestion 2"]
}}"""

        try:
            raw = llm_generate(eval_prompt, model=model)
            
            if "```json" in raw:
                raw = raw.split("```json")[1].split("```")[0]
            elif "```" in raw:
                raw = raw.split("```")[1].split("```")[0]

            result = json.loads(raw.strip())
            result["agent"] = agent_name
            result["pass"] = result.get("score", 0) >= self.threshold

            self.history.append(result)
            logger.info(f"Eval [{agent_name}]: score={result.get('score')}/10, pass={result['pass']}")
            return result

        except Exception as e:
            logger.error(f"Evaluation failed: {e}")
            return {"score": 5, "feedback": "Evaluation failed", "pass": True, "error": str(e)}

    def evaluate_and_retry(self, task: str, agent_fn, agent_name: str = "unknown", **kwargs) -> dict:
        """
        Run an agent, evaluate, and retry if score is below threshold.
        
        Args:
            task: The task to perform
            agent_fn: Callable that takes (task, **kwargs) and returns a result dict
            agent_name: Name for logging
            
        Returns:
            dict with 'result', 'evaluation', 'attempts'
        """
        attempts = []

        for attempt in range(1, self.max_retries + 2):  # +2 because range is exclusive and we start at 1
            logger.info(f"Attempt {attempt}/{self.max_retries + 1} for {agent_name}")

            # Run the agent
            result = agent_fn(task, **kwargs)
            output_text = result.get("response", result.get("text", str(result)))

            # Evaluate
            evaluation = self.evaluate(task, output_text, agent_name)
            attempts.append({"attempt": attempt, "evaluation": evaluation})

            if evaluation["pass"] or attempt > self.max_retries:
                return {
                    "result": result,
                    "evaluation": evaluation,
                    "attempts": attempts,
                    "total_attempts": attempt,
                    "final_score": evaluation.get("score", 0)
                }

            # If failed, enhance the task with feedback for retry
            feedback = evaluation.get("feedback", "")
            improvements = evaluation.get("improvements", [])
            task = f"""{task}

PREVIOUS ATTEMPT FEEDBACK (score: {evaluation.get('score')}/10):
{feedback}
Improvements needed: {', '.join(improvements)}
Please address these issues in your response."""

            logger.info(f"Retrying {agent_name} — score was {evaluation.get('score')}/10")

    def get_quality_report(self) -> dict:
        """Generate a quality report from all evaluations."""
        if not self.history:
            return {"total_evals": 0, "message": "No evaluations yet"}

        scores = [e.get("score", 0) for e in self.history]
        agents = {}
        for e in self.history:
            agent = e.get("agent", "unknown")
            if agent not in agents:
                agents[agent] = []
            agents[agent].append(e.get("score", 0))

        return {
            "total_evals": len(self.history),
            "avg_score": round(sum(scores) / len(scores), 1),
            "pass_rate": round(sum(1 for s in scores if s >= self.threshold) / len(scores) * 100, 1),
            "per_agent": {
                name: {
                    "count": len(s),
                    "avg": round(sum(s) / len(s), 1),
                    "min": min(s),
                    "max": max(s)
                }
                for name, s in agents.items()
            }
        }


# ── Singleton ────────────────────────────────────────────────────────

_instance = None

def get_evaluator(threshold: int = 6) -> SelfEvaluator:
    global _instance
    if _instance is None:
        _instance = SelfEvaluator(threshold=threshold)
    return _instance
