from dataclasses import dataclass
from typing import Dict, Any


@dataclass
class StoreConfig:
    storage_type: str = "local"
    local_base_dir: str = "out/published"
    generate_metadata: bool = True

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "StoreConfig":
        defaults = {"storage_type": "local", "local_base_dir": "out/published", "generate_metadata": True}
        merged = {**defaults, **data}
        return cls(**{k: v for k, v in merged.items() if k in cls.__dataclass_fields__})
