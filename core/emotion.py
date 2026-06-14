"""
core/emotion.py — Mood / Emotion Model
Detects the user's emotional state from text and adjusts the agent's persona/tone.
"""
import json
from collections import deque
from core.logger import logger
from core.llm import llm_generate


class EmotionModel:
    """Tracks the user's current mood and determines the appropriate agent persona."""

    def __init__(self, history_size=5):
        # Store recent detected emotions to smooth out spikes
        self.recent_emotions = deque(maxlen=history_size)
        self.current_mood = "neutral"
        self.agent_tone = "helpful and concise"

    def analyze_sentiment(self, text: str) -> dict:
        """Analyze text to determine user emotion and appropriate response tone."""
        prompt = f"""Analyze the emotional state of the user based on this text.
Determine their primary emotion and how the AI should respond.

User text: "{text}"

Emotions: happy, sad, angry, stressed, focused, confused, neutral.
Tones: empathetic, concise, encouraging, technical, playful, calming.

Respond in JSON:
{{
  "emotion": "stressed",
  "intensity": 8,
  "recommended_tone": "calming",
  "reasoning": "User is using urgent language and caps"
}}"""
        try:
            raw = llm_generate(prompt, model="llama3")
            if "```json" in raw:
                raw = raw.split("```json")[1].split("```")[0]
            elif "```" in raw:
                raw = raw.split("```")[1].split("```")[0]
            
            result = json.loads(raw.strip())
            
            emotion = result.get("emotion", "neutral")
            tone = result.get("recommended_tone", "helpful")
            
            self.recent_emotions.append(emotion)
            self._update_state()
            
            result["current_baseline_mood"] = self.current_mood
            result["active_agent_tone"] = self.agent_tone
            
            return result
            
        except Exception as e:
            logger.error(f"Emotion analysis failed: {e}")
            return {"emotion": "neutral", "recommended_tone": "helpful", "error": str(e)}

    def _update_state(self):
        """Update the baseline mood based on recent history."""
        if not self.recent_emotions:
            return
            
        # Simple majority voting for current mood
        mood_counts = {}
        for mood in self.recent_emotions:
            mood_counts[mood] = mood_counts.get(mood, 0) + 1
            
        self.current_mood = max(mood_counts, key=mood_counts.get)
        
        # Map mood to agent tone
        tone_map = {
            "angry": "calm, de-escalating, and strictly factual",
            "stressed": "reassuring, structured, and helpful",
            "focused": "extremely concise and technical, no fluff",
            "confused": "patient, explanatory, using simple analogies",
            "sad": "empathetic and warm",
            "happy": "enthusiastic and collaborative",
            "neutral": "helpful, concise, and professional"
        }
        
        self.agent_tone = tone_map.get(self.current_mood, tone_map["neutral"])

    def get_tone_instruction(self) -> str:
        """Get the current tone instruction to inject into the system prompt."""
        return f"CRITICAL TONE INSTRUCTION: The user seems {self.current_mood}. You MUST be {self.agent_tone}."


# ── Singleton ────────────────────────────────────────────────────────

_instance = None

def get_emotion_model() -> EmotionModel:
    global _instance
    if _instance is None:
        _instance = EmotionModel()
    return _instance
