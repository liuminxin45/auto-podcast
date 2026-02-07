from dataclasses import dataclass
from typing import Dict, Any


@dataclass
class StagesConfig:
    words_per_minute: int = 150
    max_segment_duration: int = 120

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "StagesConfig":
        defaults = {"words_per_minute": 150, "max_segment_duration": 120}
        merged = {**defaults, **data}
        return cls(**{k: v for k, v in merged.items() if k in cls.__dataclass_fields__})
