"""
agents/finance.py — Autonomous Finance Agent
Analyzes spending, tracks market trends, and optimizes budgets.
"""
from core.llm import llm_generate
from core.logger import logger
from datetime import datetime

class FinanceAgent:
    def __init__(self):
        self.role_prompt = """You are a highly analytical and proactive Autonomous Finance Agent.
Your goal is to optimize the user's budget, analyze market trends, and provide actionable financial advice.
You should be objective, data-driven, and slightly conservative with risk."""

    def analyze_expenses(self, expense_data: list) -> dict:
        """Analyze a list of recent expenses."""
        prompt = f"""{self.role_prompt}

Analyze the following recent expenses and identify patterns, potential savings, and budget anomalies.
Expenses: {expense_data}

Return a concise summary of your findings and 3 actionable tips."""
        
        try:
            logger.info("Finance Agent analyzing expenses...")
            response = llm_generate(prompt, model="mistral")
            return {"status": "success", "analysis": response}
        except Exception as e:
            logger.error(f"Finance Agent error: {e}")
            return {"status": "error", "message": str(e)}

    def market_brief(self, tickers: list) -> dict:
        """Generate a brief on specific market tickers."""
        # In a real scenario, this would use a tool to fetch live data (e.g. yfinance)
        prompt = f"""{self.role_prompt}

The user is tracking these assets: {tickers}.
Provide a very brief hypothetical market outlook for today ({datetime.now().strftime('%Y-%m-%d')}) based on general knowledge.
Keep it under 3 sentences per asset."""
        
        try:
            response = llm_generate(prompt, model="mistral")
            return {"status": "success", "brief": response}
        except Exception as e:
            return {"status": "error", "message": str(e)}

def run_finance_agent(task_type: str, data: any) -> dict:
    agent = FinanceAgent()
    if task_type == "expenses":
        return agent.analyze_expenses(data)
    elif task_type == "market":
        return agent.market_brief(data)
    return {"error": "Unknown task type"}
