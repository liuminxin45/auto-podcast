"""Unified LLM client for Python nodes."""
from typing import List, Dict, Any, Optional
import requests
import json
import time

DEFAULT_TIMEOUT = 60
DEFAULT_TEMPERATURE = 0.3
BATCH_SIZE = 10
BATCH_DELAY = 0.5


class LLMError(Exception):
    """LLM operation error."""
    def __init__(self, message: str, code: str = "UNKNOWN", details: Any = None):
        super().__init__(message)
        self.code = code
        self.details = details


class LLMClient:
    """Unified LLM API client with consistent error handling."""
    
    def __init__(self, api_base: str, api_key: str, model: str, temperature: float = DEFAULT_TEMPERATURE):
        if not api_base or not api_key:
            raise LLMError("Missing API credentials", "AUTH")
        
        self.api_base = api_base.rstrip('/')
        self.api_key = api_key
        self.model = model
        self.temperature = temperature
        self._session = requests.Session()
    
    def call(self, messages: List[Dict[str, str]], timeout: int = DEFAULT_TIMEOUT) -> Dict[str, Any]:
        """Make a single LLM API call."""
        headers = self._build_headers()
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": self.temperature,
        }
        
        try:
            response = self._session.post(
                f"{self.api_base}/chat/completions",
                headers=headers,
                json=payload,
                timeout=timeout
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.Timeout:
            raise LLMError("Request timeout", "TIMEOUT")
        except requests.exceptions.RequestException as e:
            raise LLMError(f"Network error: {str(e)}", "NETWORK", details=str(e))
    
    def extract_content(self, response: Dict[str, Any]) -> str:
        """Extract message content from LLM response."""
        try:
            return response["choices"][0]["message"]["content"]
        except (KeyError, IndexError) as e:
            raise LLMError("Invalid response format", "PARSE", details=str(e))
    
    def parse_json_response(self, content: str) -> Any:
        """Parse JSON from LLM response, handling markdown code blocks."""
        content = content.strip()
        
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0].strip()
        elif "```" in content:
            content = content.split("```")[1].split("```")[0].strip()
        
        try:
            return json.loads(content)
        except json.JSONDecodeError as e:
            raise LLMError(f"JSON parse error: {str(e)}", "PARSE", details=content[:200])
    
    def batch_analyze(
        self, 
        items: List[Any], 
        prompt_fn, 
        parse_fn,
        logs: Optional[List[str]] = None
    ) -> List[Any]:
        """Analyze items in batches with rate limiting."""
        results = []
        total_batches = (len(items) - 1) // BATCH_SIZE + 1
        
        for i in range(0, len(items), BATCH_SIZE):
            batch = items[i:i + BATCH_SIZE]
            batch_num = i // BATCH_SIZE + 1
            
            if logs:
                logs.append(f"Analyzing batch {batch_num}/{total_batches}")
            
            try:
                prompt = prompt_fn(batch)
                response = self.call([{"role": "user", "content": prompt}])
                content = self.extract_content(response)
                parsed = self.parse_json_response(content)
                batch_results = parse_fn(batch, parsed)
                results.extend(batch_results)
                
                time.sleep(BATCH_DELAY)
            except LLMError as e:
                if logs:
                    logs.append(f"Batch {batch_num} failed: {e}")
                for item in batch:
                    results.append(self._create_error_result(item, str(e)))
        
        return results
    
    def _build_headers(self) -> Dict[str, str]:
        """Build request headers based on API provider."""
        headers = {"Content-Type": "application/json"}
        
        if "openai.azure.com" in self.api_base:
            headers["api-key"] = self.api_key
        else:
            headers["Authorization"] = f"Bearer {self.api_key}"
        
        return headers
    
    def _create_error_result(self, item: Any, error: str) -> Any:
        """Create error result for failed batch item."""
        if isinstance(item, dict):
            return {**item, "_error": error}
        return item
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self._session.close()
