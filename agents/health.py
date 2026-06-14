"""
agents/health.py — Health Monitor Agent
Tracks fitness goals, sleep, and well-being.
"""
from core.llm import llm_generate
from core.logger import logger

class HealthAgent:
    def __init__(self):
        self.role_prompt = """You are a supportive, knowledgeable, and proactive Health Monitor Agent.
Your goal is to help the user track fitness, sleep, and overall well-being.
Always prioritize safety and suggest consulting a doctor for medical issues."""

    def analyze_sleep(self, sleep_data: dict) -> dict:
        """Analyze recent sleep patterns."""
        prompt = f"""{self.role_prompt}

The user provided the following sleep data for the past few days: {sleep_data}
Analyze this data, pointing out any sleep debt or irregular patterns. Provide 2 tips for better sleep hygiene tonight."""
        
        try:
            logger.info("Health Agent analyzing sleep data...")
            response = llm_generate(prompt, model="mistral")
            return {"status": "success", "analysis": response}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def fitness_checkin(self, recent_activity: str) -> dict:
        """Provide encouragement and analysis of fitness activity."""
        prompt = f"""{self.role_prompt}

The user's recent fitness activity: "{recent_activity}"
Provide a very encouraging, short response. Suggest a minor optimization or recovery tip if applicable."""
        
        try:
            response = llm_generate(prompt, model="llama3")
            return {"status": "success", "feedback": response}
        except Exception as e:
            return {"status": "error", "message": str(e)}

def run_health_agent(task_type: str, data: any) -> dict:
    agent = HealthAgent()
    if task_type == "sleep":
        return agent.analyze_sleep(data)
    elif task_type == "fitness":
        return agent.fitness_checkin(data)
    return {"error": "Unknown task type"}
