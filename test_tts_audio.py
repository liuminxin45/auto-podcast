"""
TTS音频生成测试脚本
测试TTS配置是否正确，能否成功生成音频
"""

import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# 加载环境变量
load_dotenv(override=True)

def test_tts_synthesis():
    """测试TTS合成"""
    print("=" * 60)
    print("TTS音频生成测试")
    print("=" * 60)
    
    # 检查环境变量
    print("\n【环境变量检查】")
    doubao_mode = os.environ.get("DOUBAO_MODE", "")
    print(f"  DOUBAO_MODE: {doubao_mode}")
    print(f"  DOUBAO_APP_ID: {os.environ.get('DOUBAO_APP_ID', 'NOT SET')}")
    print(f"  DOUBAO_ACCESS_KEY: {'SET' if os.environ.get('DOUBAO_ACCESS_KEY') else 'NOT SET'}")
    print(f"  DOUBAO_TTS_VOICE: {os.environ.get('DOUBAO_TTS_VOICE', 'NOT SET')}")
    print(f"  DOUBAO_TTS_VERSION: {os.environ.get('DOUBAO_TTS_VERSION', 'NOT SET')}")
    print(f"  DOUBAO_TTS_V3_RESOURCE_ID: {os.environ.get('DOUBAO_TTS_V3_RESOURCE_ID', 'NOT SET')}")
    print(f"  DOUBAO_TTS_V3_URL: {os.environ.get('DOUBAO_TTS_V3_URL', 'NOT SET')}")
    
    # 导入TTS客户端
    print("\n【导入TTS客户端】")
    try:
        from src.tts.tts_client import TTSClientFactory
        print("  ✓ 成功导入TTSClientFactory")
    except Exception as e:
        print(f"  ✗ 导入失败: {e}")
        return False
    
    # 创建TTS客户端
    print("\n【创建TTS客户端】")
    try:
        client = TTSClientFactory.create_doubao_podcast_client(timeout_seconds=60)
        print(f"  ✓ 成功创建客户端: {type(client).__name__}")
    except Exception as e:
        print(f"  ✗ 创建失败: {e}")
        return False
    
    # 测试文本
    test_text = "这是一个测试音频，用于验证TTS配置是否正确。"
    print(f"\n【测试文本】")
    print(f"  {test_text}")
    
    # 获取speaker配置
    import yaml
    config_path = Path("config/base/settings.yaml")
    with open(config_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)
    
    voice = config.get("tts", {}).get("voice", "")
    print(f"\n【Speaker配置】")
    print(f"  voice: {voice}")
    print(f"  类型: {type(voice)}")
    
    # 合成音频
    print(f"\n【开始合成音频】")
    try:
        if doubao_mode in {"tts", "tts_v3_http"}:
            print(f"  使用模式: TTS V3 HTTP")
            result = client.synthesize(test_text, mode="tts_v3_http", speaker=voice)
        else:
            print(f"  使用模式: 默认")
            result = client.synthesize(test_text)
        
        audio_data = result.audio_data
        print(f"  ✓ 合成成功！")
        print(f"  音频大小: {len(audio_data)} bytes")
        print(f"  音频格式: {result.format}")
        print(f"  采样率: {result.sample_rate}")
        
        # 保存测试音频
        output_path = Path("test_tts_output.mp3")
        output_path.write_bytes(audio_data)
        print(f"  ✓ 音频已保存: {output_path}")
        
        return True
        
    except Exception as e:
        print(f"  ✗ 合成失败: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("\n开始TTS测试...\n")
    success = test_tts_synthesis()
    
    print("\n" + "=" * 60)
    if success:
        print("✅ TTS测试通过！")
        print("=" * 60)
        exit(0)
    else:
        print("❌ TTS测试失败！")
        print("=" * 60)
        exit(1)
