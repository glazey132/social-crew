"""
Minimal LLM wrapper for Ollama - compatible with Python 3.9.
Avoids CrewAI's complex dependencies.
"""

import json
import logging
import os
from typing import Dict, Optional
import requests

LOGGER = logging.getLogger(__name__)


class OllamaLLM:
    """Simple Ollama client wrapper."""
    
    def __init__(
        self,
        model: str = "ollama/qwen3.5:35b-a3b",
        base_url: str = "http://localhost:11434",
        timeout: int = 300,
    ):
        self.model = model
        self.base_url = base_url
        self.timeout = timeout
        self._api_key = os.getenv("OLLAMA_API_KEY", "")
    
    @property
    def api_key(self) -> str:
        return self._api_key
    
    @api_key.setter
    def api_key(self, value: str):
        self._api_key = value
    
    def generate(self, prompt: str, **kwargs) -> str:
        """Generate text using Ollama API."""
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
        }
        
        try:
            response = requests.post(
                f"{self.base_url}/api/generate",
                json=payload,
                timeout=self.timeout,
            )
            response.raise_for_status()
            result = response.json()
            return result.get("response", "")
            
        except Exception as e:
            LOGGER.error("Ollama API error: %s", e)
            return f"[ERROR] {e}"


class CrewLLM:
    """
    Wrapper to make OllamaLLM compatible with CrewAI's LLM interface.
    This allows us to use our simple client with crew tasks.
    """
    
    def __init__(self, ollama_client: OllamaLLM):
        self.model = ollama_client.model
        self.base_url = ollama_client.base_url
        self._ollama = ollama_client
    
    @property
    def api_key(self) -> str:
        return self._ollama.api_key
    
    @api_key.setter
    def api_key(self, value: str):
        self._ollama.api_key = value
    
    def generate(self, prompt: str, **kwargs) -> str:
        return self._ollama.generate(prompt, **kwargs)


def build_crew_llm(llm_model: str, llm_base_url: str) -> CrewLLM:
    """Build a CrewAI-compatible LLM wrapper around OllamaLLM."""
    ollama_client = OllamaLLM(model=llm_model, base_url=llm_base_url)
    return CrewLLM(ollama_client)
