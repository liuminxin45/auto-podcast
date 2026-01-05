"""
TTS配置修复测试脚本
测试voice配置是否能正确读取
"""

import yaml
from pathlib import Path

def test_config_loading():
    """测试配置加载"""
    print("=" * 60)
    print("测试配置加载")
    print("=" * 60)
    
    config = {}
    
    # 加载 settings.yaml
    settings_path = Path("config/base/settings.yaml")
    if settings_path.exists():
        with open(settings_path, "r", encoding="utf-8") as f:
            settings = yaml.safe_load(f) or {}
            config.update(settings)
            print(f"\n✓ 已加载 settings.yaml")
            print(f"  tts.voice = {config.get('tts', {}).get('voice')}")
            print(f"  类型: {type(config.get('tts', {}).get('voice'))}")
    
    # 加载 pipeline.yaml
    pipeline_path = Path("config/base/pipeline.yaml")
    if pipeline_path.exists():
        with open(pipeline_path, "r", encoding="utf-8") as f:
            pipeline_cfg = yaml.safe_load(f) or {}
            config.update(pipeline_cfg)
            print(f"\n✓ 已加载 pipeline.yaml")
            print(f"  tts.voice = {config.get('tts', {}).get('voice')}")
            print(f"  类型: {type(config.get('tts', {}).get('voice'))}")
    
    # 测试voice读取逻辑
    print("\n" + "=" * 60)
    print("测试voice读取逻辑")
    print("=" * 60)
    
    voice_cfg = config.get("tts", {}).get("voice") or ""
    print(f"\nvoice_cfg = {voice_cfg}")
    print(f"类型: {type(voice_cfg)}")
    
    # 使用修复后的逻辑
    if isinstance(voice_cfg, dict):
        voice = voice_cfg.get("default", "")
        print(f"\n✓ voice是字典，提取default: {voice}")
    else:
        voice = str(voice_cfg).strip()
        print(f"\n✓ voice是字符串: {voice}")
    
    # 验证结果
    print("\n" + "=" * 60)
    print("验证结果")
    print("=" * 60)
    
    if voice and isinstance(voice, str):
        print(f"\n✅ 测试通过！")
        print(f"   最终voice值: {voice}")
        print(f"   类型: {type(voice)}")
        return True
    else:
        print(f"\n❌ 测试失败！")
        print(f"   voice值: {voice}")
        print(f"   类型: {type(voice)}")
        return False

if __name__ == "__main__":
    success = test_config_loading()
    exit(0 if success else 1)
