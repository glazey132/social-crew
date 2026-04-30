"""
Mock LLM class for environments that may not have full CrewAI support.
Provides a simple interface for single-user operation.
"""

class LLM:
    """Stub LLM class for environments without Ollama/external LLM."""
    
    def __init__(self, model: str = "dummy", base_url: str = "http://localhost:11434"):
        self.model = model
        self.base_url = base_url
        self._initialized = False
    
    @property
    def api_key(self) -> str:
        return self._api_key if hasattr(self, '_api_key') else ""
    
    @api_key.setter
    def api_key(self, value: str):
        self._api_key = value
    
    def generate(self, prompt: str, **kwargs) -> str:
        """Generate text (mock implementation)."""
        return f"[MOCK] Response to: {prompt[:50]}"

