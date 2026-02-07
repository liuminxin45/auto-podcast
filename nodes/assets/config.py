from dataclasses import dataclass, field
from typing import Dict, Any, List


@dataclass
class AssetsConfig:
    output_dir: str = "out/assets"
    generate_cover: bool = True
    cover_size: List[int] = field(default_factory=lambda: [1400, 1400])

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AssetsConfig":
        defaults = {"output_dir": "out/assets", "generate_cover": True, "cover_size": [1400, 1400]}
        merged = {**defaults, **data}
        return cls(**{k: v for k, v in merged.items() if k in cls.__dataclass_fields__})
