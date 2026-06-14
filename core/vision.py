"""
core/vision.py — Vision input module.
Accept image uploads and analyze them using multimodal LLMs.
"""
import os
import base64
import requests
from pathlib import Path

from core.logger import logger

try:
    from PIL import Image
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False


class VisionEngine:
    """Analyze images using local Ollama multimodal models or cloud APIs."""

    def __init__(self, ollama_url: str = "http://localhost:11434", model: str = "llava"):
        self.ollama_url = ollama_url
        self.model = model
        logger.info(f"VisionEngine init — model: {model}, Ollama: {ollama_url}")

    def _image_to_base64(self, image_path: str) -> str:
        """Convert an image file to base64 string."""
        with open(image_path, "rb") as f:
            return base64.b64encode(f.read()).decode("utf-8")

    def analyze_image(self, image_path: str, prompt: str = "Describe this image in detail.") -> str:
        """
        Analyze an image using a multimodal LLM.
        
        Args:
            image_path: Path to the image file
            prompt: What to ask about the image
            
        Returns:
            Text description/analysis from the model
        """
        if not os.path.exists(image_path):
            raise FileNotFoundError(f"Image not found: {image_path}")

        img_b64 = self._image_to_base64(image_path)

        try:
            # Use Ollama's multimodal API
            response = requests.post(
                f"{self.ollama_url}/api/generate",
                json={
                    "model": self.model,
                    "prompt": prompt,
                    "images": [img_b64],
                    "stream": False
                },
                timeout=120
            )
            
            if response.status_code == 200:
                result = response.json().get("response", "")
                logger.info(f"Vision analysis complete: {len(result)} chars")
                return result
            else:
                logger.error(f"Ollama vision error: {response.status_code}")
                return f"Error: Ollama returned status {response.status_code}"

        except requests.ConnectionError:
            logger.error("Cannot connect to Ollama for vision analysis")
            return "Error: Cannot connect to Ollama. Ensure it is running on localhost:11434"
        except Exception as e:
            logger.error(f"Vision analysis failed: {e}")
            return f"Error: {str(e)}"

    def read_handwriting(self, image_path: str) -> str:
        """Specialized prompt for reading handwritten notes."""
        return self.analyze_image(
            image_path, 
            "Read and transcribe all handwritten text in this image. Be precise and preserve the structure."
        )

    def analyze_whiteboard(self, image_path: str) -> str:
        """Specialized prompt for whiteboard photos."""
        return self.analyze_image(
            image_path,
            "Analyze this whiteboard photo. Transcribe all text, describe any diagrams or flowcharts, "
            "and summarize the key ideas being discussed."
        )

    def describe_error(self, image_path: str) -> str:
        """Specialized prompt for error screenshots."""
        return self.analyze_image(
            image_path,
            "This is a screenshot of an error or bug. Identify the error type, read the error message, "
            "determine what application or code is involved, and suggest possible fixes."
        )


# ── Singleton ────────────────────────────────────────────────────────

_instance = None

def get_vision_engine(ollama_url: str = "http://localhost:11434", model: str = "llava") -> VisionEngine:
    global _instance
    if _instance is None:
        _instance = VisionEngine(ollama_url=ollama_url, model=model)
    return _instance
