from dataclasses import dataclass
from typing import Dict, Any


@dataclass
class AudioPostprocessConfig:
    output_dir: str = "out/episodes"
    output_format: str = "mp3"
    normalize_loudness: bool = True
    target_loudness: float = -16.0
    add_bgm: bool = False
    bgm_path: str = ""
    bgm_volume: float = 0.15

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AudioPostprocessConfig":
        defaults = {"output_dir": "out/episodes", "output_format": "mp3",
                    "normalize_loudness": True, "target_loudness": -16.0,
                    "add_bgm": False, "bgm_path": "", "bgm_volume": 0.15}
        merged = {**defaults, **data}
        return cls(**{k: v for k, v in merged.items() if k in cls.__dataclass_fields__})
