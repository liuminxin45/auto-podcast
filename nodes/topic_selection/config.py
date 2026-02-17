from dataclasses import dataclass
from typing import Dict, Any


@dataclass
class TopicSelectionConfig:
    min_cluster_size: int = 3
    max_topics: int = 1
    use_llm_scoring: bool = True
    llm_model: str = "gpt-4o-mini"
    api_key: str = ""
    api_base: str = ""
    temperature: float = 0.3
    
    # Auto Selection Mode (for Discover layer)
    mode: str = "cluster"  # "cluster" or "analyze_relevance"
    target_topic: str = ""
    time_range_hours: int = 24
    focus_instruction: str = ""
    min_match_score: int = 70
    max_items: int = 10

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TopicSelectionConfig":
        defaults = {
            "min_cluster_size": 3, "max_topics": 1, "use_llm_scoring": True,
            "llm_model": "gpt-4o-mini", "api_key": "", "api_base": "", "temperature": 0.3,
            "mode": "cluster", "target_topic": "", "time_range_hours": 24,
            "focus_instruction": "", "min_match_score": 70, "max_items": 10
        }
        merged = {**defaults, **data}
        return cls(**{k: v for k, v in merged.items() if k in cls.__dataclass_fields__})
