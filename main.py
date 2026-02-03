"""
Auto-Podcast Main Entry Point

LangGraph 驱动的播客自动生成系统主入口。
"""

import os
import sys
from datetime import datetime
from pathlib import Path
import yaml
from src.schemas.state import PodcastState
from src.graphs.podcast_graph import create_podcast_graph


def load_config(config_path: str = None) -> dict:
    """加载配置文件"""
    if config_path and os.path.exists(config_path):
        with open(config_path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)
    
    return {
        "fetch": {
            "sources": [
                {"type": "rss", "url": "https://hnrss.org/frontpage"},
            ],
            "max_items_per_source": 10
        },
        "script": {
            "target_duration_minutes": 15
        },
        "tts": {
            "voice_mapping": {
                "主持人A": "zh-CN-XiaoxiaoNeural",
                "主持人B": "zh-CN-YunxiNeural"
            }
        },
        "publish": {
            "podcast_title": "AI 科技播客",
            "podcast_description": "AI 自动生成的科技播客节目"
        }
    }


def main():
    """主函数"""
    print("=" * 60)
    print("Auto-Podcast - LangGraph 播客生成系统")
    print("=" * 60)
    
    config_path = sys.argv[1] if len(sys.argv) > 1 else None
    config = load_config(config_path)
    
    print(f"\n[配置] 加载配置: {config_path or '默认配置'}")
    
    episode_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    initial_state = PodcastState(episode_id=episode_id)
    
    print(f"[初始化] Episode ID: {episode_id}")
    print(f"[初始化] 创建时间: {initial_state.created_at}")
    
    print("\n[图构建] 创建 LangGraph 主图...")
    graph = create_podcast_graph(config)
    
    print("[执行] 开始运行主流程...\n")
    
    try:
        final_state = graph.invoke(initial_state)
        
        print("\n" + "=" * 60)
        print("执行完成")
        print("=" * 60)
        
        if final_state.errors:
            print("\n[错误]")
            for error in final_state.errors:
                print(f"  - [{error['node']}] {error['message']}")
        
        if final_state.logs:
            print("\n[日志]")
            for log in final_state.logs:
                print(f"  {log}")
        
        print("\n[产物]")
        if final_state.final_audio_path:
            print(f"  音频: {final_state.final_audio_path}")
        if final_state.cover_path:
            print(f"  封面: {final_state.cover_path}")
        if final_state.rss_path:
            print(f"  RSS: {final_state.rss_path}")
        if final_state.storage_info:
            print(f"  存储: {final_state.storage_info.get('base_dir', '')}")
        
        print("\n" + "=" * 60)
        
        if final_state.errors:
            sys.exit(1)
        else:
            print("✓ 播客生成成功！")
            sys.exit(0)
    
    except Exception as e:
        print(f"\n[致命错误] {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
