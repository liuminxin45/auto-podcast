from dataclasses import dataclass
from typing import Dict, Any


@dataclass
class ResearchConfig:
    enable_web_search: bool = False
    max_search_results: int = 5
    llm_model: str = "gpt-4o-mini"
    api_key: str = ""
    api_base: str = ""
    temperature: float = 0.5

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ResearchConfig":
        defaults = {"enable_web_search": False, "max_search_results": 5,
                    "llm_model": "gpt-4o-mini", "api_key": "", "api_base": "", "temperature": 0.5}
        merged = {**defaults, **data}
        return cls(**{k: v for k, v in merged.items() if k in cls.__dataclass_fields__})
