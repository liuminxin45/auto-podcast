import os
from pathlib import Path
from typing import Dict, Any
from nodes.assets.config import AssetsConfig


def run(state: Dict[str, Any], config: AssetsConfig = None) -> Dict[str, Any]:
    config = config or AssetsConfig()
    logs = state.get("logs", [])
    errors = state.get("errors", [])
    
    import time as _time
    from datetime import datetime
    _t0 = _time.time()
    
    logs.append(f"[AssetsNode] ========== 节点启动 ==========")
    logs.append(f"[AssetsNode] 启动时间: {datetime.now().isoformat()}")
    logs.append(f"[AssetsNode] 输入状态: episode_id={state.get('episode_id', 'N/A')}")
    logs.append(f"[AssetsNode] 配置: generate_cover={config.generate_cover}, output_dir={config.output_dir}")
    _dbg = state.get("runtime_config", {}).get("debug_mode", {}).get("enabled", False)
    logs.append(f"[AssetsNode] debug_mode={_dbg} (此节点不使用LLM, 不受debug_mode影响)")

    try:
        Path(config.output_dir).mkdir(parents=True, exist_ok=True)
        episode_id = state.get("episode_id", "unknown")

        if config.generate_cover:
            logs.append(f"[AssetsNode] 生成封面中...")
            cover_path = _generate_cover(episode_id, state, config)
            state["cover_path"] = cover_path
            logs.append(f"[AssetsNode] 封面生成完成: {cover_path}")
        else:
            logs.append(f"[AssetsNode] 跳过封面生成 (generate_cover=False)")
    except Exception as e:
        errors.append({"node": "assets", "message": str(e), "detail": str(e)})
        logs.append(f"[AssetsNode] ✗ 错误: {str(e)}")
    
    _elapsed = _time.time() - _t0
    logs.append(f"[AssetsNode] ========== 节点完成 ==========")
    logs.append(f"[AssetsNode] 完成时间: {datetime.now().isoformat()} | 耗时: {_elapsed:.2f}s")
    cover_path = state.get("cover_path", "")
    logs.append(f"[AssetsNode] 输出: cover_path={cover_path if cover_path else 'N/A'}")
    logs.append(f"[AssetsNode] 错误数: {len([e for e in errors if e.get('node') == 'assets'])}")

    state["logs"] = logs
    state["errors"] = errors
    return state


def _generate_cover(episode_id: str, state: Dict, config: AssetsConfig) -> str:
    from PIL import Image, ImageDraw, ImageFont

    w, h = config.cover_size
    img = Image.new("RGB", (w, h), color=(30, 30, 60))
    draw = ImageDraw.Draw(img)

    title = state.get("script", {}).get("title", state.get("selected_topic", {}).get("title", "Podcast"))

    try:
        font = ImageFont.truetype("arial.ttf", 60)
    except (IOError, OSError):
        font = ImageFont.load_default()

    bbox = draw.textbbox((0, 0), title, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    draw.text(((w - tw) / 2, (h - th) / 2), title, fill="white", font=font)

    cover_path = os.path.join(config.output_dir, f"{episode_id}_cover.png")
    img.save(cover_path)
    return cover_path
