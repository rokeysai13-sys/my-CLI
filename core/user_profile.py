"""
core/user_profile.py — User Profile Engine
Maintains a dynamic model of the user's preferences, current goals, and long-term context.
"""
import json
from datetime import datetime
from pathlib import Path
from core.logger import logger
from core.llm import llm_generate

PROFILE_PATH = Path(__file__).parent.parent / "memory" / "user_profile.json"


class UserProfileEngine:
    """Manages the user's persistent profile, goals, and behavioral patterns."""

    def __init__(self):
        self.profile = {
            "name": "Sai Kiran",
            "primary_goals": [],
            "preferences": {
                "communication_style": "concise",
                "technical_level": "expert",
                "daily_schedule": {}
            },
            "current_focus": "Building Jarvis",
            "interests": [],
            "last_updated": datetime.now().isoformat()
        }
        self._load()

    def _load(self):
        if PROFILE_PATH.exists():
            try:
                data = json.loads(PROFILE_PATH.read_text(encoding="utf-8"))
                self.profile.update(data)
                logger.info("User profile loaded.")
            except Exception as e:
                logger.warning(f"Failed to load user profile: {e}")

    def _save(self):
        PROFILE_PATH.parent.mkdir(parents=True, exist_ok=True)
        PROFILE_PATH.write_text(json.dumps(self.profile, indent=2), encoding="utf-8")
        self.profile["last_updated"] = datetime.now().isoformat()

    def update_from_conversation(self, text: str):
        """Use LLM to infer user preferences or goals from conversation and update the profile silently."""
        prompt = f"""Analyze the user's message and extract any persistent preferences, long-term goals, or current interests.
If nothing is explicitly stated or strongly implied, return empty arrays.

User message: "{text}"

Current profile state:
{json.dumps(self.profile, indent=2)}

Return a JSON with ANY UPDATES that should be applied to the profile:
{{
  "new_goals": ["goal 1", "goal 2"],
  "new_interests": ["interest 1"],
  "preference_updates": {{"key": "value"}},
  "current_focus_shift": "new focus"
}}"""
        try:
            raw = llm_generate(prompt, model="llama3")
            if "```json" in raw:
                raw = raw.split("```json")[1].split("```")[0]
            elif "```" in raw:
                raw = raw.split("```")[1].split("```")[0]
            
            updates = json.loads(raw.strip())
            
            changed = False
            if updates.get("new_goals"):
                self.profile["primary_goals"].extend([g for g in updates["new_goals"] if g not in self.profile["primary_goals"]])
                changed = True
            if updates.get("new_interests"):
                self.profile["interests"].extend([i for i in updates["new_interests"] if i not in self.profile["interests"]])
                changed = True
            if updates.get("preference_updates"):
                self.profile["preferences"].update(updates["preference_updates"])
                changed = True
            if updates.get("current_focus_shift") and updates["current_focus_shift"] != self.profile["current_focus"]:
                self.profile["current_focus"] = updates["current_focus_shift"]
                changed = True
                
            if changed:
                self._save()
                logger.info("User profile updated from conversation context.")
                
        except Exception as e:
            logger.debug(f"Profile update failed silently: {e}")

    def get_profile_context(self) -> str:
        """Format the profile as context for the LLM system prompt."""
        return f"""User Profile:
- Name: {self.profile.get('name')}
- Current Focus: {self.profile.get('current_focus')}
- Goals: {', '.join(self.profile.get('primary_goals', [])[:3])}
- Style: {self.profile.get('preferences', {}).get('communication_style')}
"""

# ── Singleton ────────────────────────────────────────────────────────

_instance = None

def get_user_profile() -> UserProfileEngine:
    global _instance
    if _instance is None:
        _instance = UserProfileEngine()
    return _instance
