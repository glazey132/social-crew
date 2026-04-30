"""
Minimal agent factory for single-user operation.
Uses direct Ollama API instead of CrewAI LLM for Python 3.9 compatibility.
"""

import logging
from typing import Dict

from pipeline.llm import build_crew_llm

LOGGER = logging.getLogger(__name__)


def build_social_crew(llm_model: str, llm_base_url: str) -> Dict[str, "Crew"]:
    """
    Build a CrewAI-compatible LLM wrapper for Ollama.
    
    For single-user operation without complex crew configurations,
    this provides a minimal LLM that can be used with Crew tasks.
    """
    llm = build_crew_llm(llm_model, llm_base_url)
    LOGGER.info("Built OllamaLLM wrapper with model=%s, base_url=%s", llm.model, llm.base_url)
    return {"llm": llm}
