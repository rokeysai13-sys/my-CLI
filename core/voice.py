"""
core/voice.py — Voice I/O module for Kirannn.
Provides speech-to-text (Whisper) and text-to-speech (pyttsx3).
"""
import os
import tempfile
import threading
from pathlib import Path

try:
    import pyttsx3
    TTS_AVAILABLE = True
except ImportError:
    TTS_AVAILABLE = False

try:
    import whisper
    STT_AVAILABLE = True
except ImportError:
    STT_AVAILABLE = False

from core.logger import logger


class VoiceEngine:
    """Unified voice I/O engine with Whisper STT and pyttsx3 TTS."""

    def __init__(self, whisper_model: str = "base"):
        self.whisper_model_name = whisper_model
        self._whisper_model = None
        self._tts_engine = None
        self._tts_lock = threading.Lock()

        logger.info(f"VoiceEngine init — STT available: {STT_AVAILABLE}, TTS available: {TTS_AVAILABLE}")

    # ── Speech-to-Text (Whisper) ─────────────────────────────────────

    def _load_whisper(self):
        """Lazy-load the Whisper model."""
        if self._whisper_model is None:
            if not STT_AVAILABLE:
                raise RuntimeError("openai-whisper is not installed. Run: pip install openai-whisper")
            logger.info(f"Loading Whisper model '{self.whisper_model_name}'...")
            self._whisper_model = whisper.load_model(self.whisper_model_name)
            logger.info("Whisper model loaded.")
        return self._whisper_model

    def transcribe(self, audio_path: str, language: str = None) -> str:
        """
        Transcribe an audio file to text using Whisper.
        
        Args:
            audio_path: Path to audio file (wav, mp3, ogg, etc.)
            language: Optional language code (e.g. 'en', 'hi')
            
        Returns:
            Transcribed text string.
        """
        if not os.path.exists(audio_path):
            raise FileNotFoundError(f"Audio file not found: {audio_path}")

        model = self._load_whisper()
        
        options = {}
        if language:
            options["language"] = language

        logger.info(f"Transcribing: {audio_path}")
        result = model.transcribe(audio_path, **options)
        text = result.get("text", "").strip()
        logger.info(f"Transcription result: {text[:100]}...")
        return text

    # ── Text-to-Speech (pyttsx3) ─────────────────────────────────────

    def _get_tts_engine(self):
        """Get or create the pyttsx3 engine (thread-safe)."""
        if not TTS_AVAILABLE:
            raise RuntimeError("pyttsx3 is not installed. Run: pip install pyttsx3")
        if self._tts_engine is None:
            self._tts_engine = pyttsx3.init()
            # Configure voice properties
            self._tts_engine.setProperty('rate', 175)     # Speed
            self._tts_engine.setProperty('volume', 0.9)   # Volume
            # Try to select a clear voice
            voices = self._tts_engine.getProperty('voices')
            if voices and len(voices) > 1:
                # Prefer a female voice for Jarvis-like feel (index 1 on Windows)
                self._tts_engine.setProperty('voice', voices[1].id)
        return self._tts_engine

    def speak(self, text: str):
        """Speak text aloud using the system TTS engine."""
        with self._tts_lock:
            engine = self._get_tts_engine()
            logger.info(f"Speaking: {text[:80]}...")
            engine.say(text)
            engine.runAndWait()

    def speak_to_file(self, text: str, output_path: str = None) -> str:
        """
        Convert text to an audio file.
        
        Args:
            text: Text to convert
            output_path: Optional output file path. Auto-generated if None.
            
        Returns:
            Path to the generated audio file.
        """
        if output_path is None:
            output_path = os.path.join(tempfile.gettempdir(), "kirannn_tts_output.wav")

        with self._tts_lock:
            engine = self._get_tts_engine()
            engine.save_to_file(text, output_path)
            engine.runAndWait()
            
        logger.info(f"TTS saved to: {output_path}")
        return output_path


# ── Singleton instance ───────────────────────────────────────────────

_engine = None

def get_voice_engine(whisper_model: str = "base") -> VoiceEngine:
    """Get or create the global VoiceEngine singleton."""
    global _engine
    if _engine is None:
        _engine = VoiceEngine(whisper_model=whisper_model)
    return _engine
