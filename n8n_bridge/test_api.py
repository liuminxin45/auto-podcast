"""
测试 n8n Bridge API 的各个端点
"""

import requests
import json

BASE_URL = "http://127.0.0.1:8000"

def test_health():
    """测试健康检查"""
    print("\n=== 测试健康检查 ===")
    response = requests.get(f"{BASE_URL}/health")
    print(f"状态码: {response.status_code}")
    print(f"响应: {response.json()}")
    return response.status_code == 200

def test_config_list():
    """测试配置列表"""
    print("\n=== 测试配置列表 ===")
    response = requests.get(f"{BASE_URL}/api/config/list")
    print(f"状态码: {response.status_code}")
    data = response.json()
    print(f"配置总数: {data['total']}")
    print(f"前 5 个配置: {list(data['configs'].keys())[:5]}")
    return response.status_code == 200

def test_config_get():
    """测试获取单个配置"""
    print("\n=== 测试获取单个配置 ===")
    payload = {
        "config_type": "env",
        "key": "LLM_PROVIDER"
    }
    response = requests.post(f"{BASE_URL}/api/config/get", json=payload)
    print(f"状态码: {response.status_code}")
    print(f"响应: {response.json()}")
    return response.status_code == 200

def test_config_get_yaml():
    """测试获取 YAML 配置"""
    print("\n=== 测试获取 YAML 配置 ===")
    payload = {
        "config_type": "yaml",
        "key": "llm.provider"
    }
    response = requests.post(f"{BASE_URL}/api/config/get", json=payload)
    print(f"状态码: {response.status_code}")
    if response.status_code == 200:
        print(f"响应: {response.json()}")
    else:
        print(f"错误: {response.text}")
    return response.status_code == 200

def test_search_bocha():
    """测试博查搜索"""
    print("\n=== 测试博查搜索 ===")
    payload = {
        "query": "人工智能最新进展",
        "provider": "bocha",
        "count": 3,
        "api_type": "ai-search"
    }
    response = requests.post(f"{BASE_URL}/api/search/call", json=payload)
    print(f"状态码: {response.status_code}")
    if response.status_code == 200:
        data = response.json()
        print(f"搜索成功: {data.get('success')}")
        print(f"结果长度: {len(data.get('results', ''))}")
        print(f"前 200 字符: {data.get('results', '')[:200]}")
    else:
        print(f"错误: {response.text}")
    return response.status_code == 200

def test_llm_call():
    """测试 LLM 调用"""
    print("\n=== 测试 LLM 调用 ===")
    payload = {
        "provider": "deepseek",
        "prompt": "用一句话介绍人工智能",
        "temperature": 0.7,
        "max_tokens": 100
    }
    response = requests.post(f"{BASE_URL}/api/llm/call", json=payload)
    print(f"状态码: {response.status_code}")
    if response.status_code == 200:
        data = response.json()
        print(f"调用成功: {data.get('success')}")
        print(f"响应: {data.get('response', '')[:200]}")
    else:
        print(f"错误: {response.text}")
    return response.status_code == 200

def main():
    """运行所有测试"""
    print("=" * 60)
    print("开始测试 n8n Bridge API")
    print("=" * 60)
    
    results = {
        "健康检查": test_health(),
        "配置列表": test_config_list(),
        "获取单个配置": test_config_get(),
        "获取 YAML 配置": test_config_get_yaml(),
        "博查搜索": test_search_bocha(),
        "LLM 调用": test_llm_call(),
    }
    
    print("\n" + "=" * 60)
    print("测试结果汇总")
    print("=" * 60)
    for test_name, passed in results.items():
        status = "✅ 通过" if passed else "❌ 失败"
        print(f"{test_name}: {status}")
    
    total = len(results)
    passed = sum(results.values())
    print(f"\n总计: {passed}/{total} 通过")
    
    return passed == total

if __name__ == "__main__":
    import sys
    success = main()
    sys.exit(0 if success else 1)
