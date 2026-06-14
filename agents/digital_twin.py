"""
agents/digital_twin.py — Digital Twin Agent
Simulates the user to draft emails, answer basic questions, or predict user preferences.
"""
from core.llm import llm_generate
from core.logger import logger
from core.user_profile import get_user_profile

class DigitalTwinAgent:
    def __init__(self):
        self.profile = get_user_profile()
        
    def _build_twin_prompt(self) -> str:
        """Constructs a prompt that instructs the LLM to behave exactly like the user."""
        return f"""You are a Digital Twin of the user. You must think, write, and respond EXACTLY as they would.
Do NOT act like an AI assistant. Use the first person ("I", "my").

{self.profile.get_profile_context()}

Adopt their tone, use their preferred communication style, and reference their goals/interests if relevant.
"""

    def draft_email(self, recipient: str, topic: str, key_points: list) -> dict:
        """Draft an email sounding like the user."""
        prompt = f"""{self._build_twin_prompt()}

Draft an email to {recipient} about "{topic}".
Make sure to include these key points:
- {chr(10).join(f"- {p}" for p in key_points)}

Write the subject line and body. Remember, you ARE the user. Be natural."""
        
        try:
            logger.info("Digital Twin drafting email...")
            response = llm_generate(prompt, model="llama3")
            return {"status": "success", "draft": response}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def predict_preference(self, scenario: str) -> dict:
        """Predict how the user would react to a scenario."""
        prompt = f"""{self._build_twin_prompt()}

Scenario: {scenario}

Based on everything you know about yourself (the user), how would you respond to or handle this scenario? What would your preference be?"""
        
        try:
            response = llm_generate(prompt, model="mistral")
            return {"status": "success", "prediction": response}
        except Exception as e:
            return {"status": "error", "message": str(e)}

def run_digital_twin(task_type: str, data: dict) -> dict:
    agent = DigitalTwinAgent()
    if task_type == "draft_email":
        return agent.draft_email(data.get("recipient", "Unknown"), data.get("topic", "Update"), data.get("key_points", []))
    elif task_type == "predict":
        return agent.predict_preference(data.get("scenario", ""))
    return {"error": "Unknown task type"}
