"""
Demo 1: 直接调用 LLM

这是最简单的 LLM 调用示例，展示如何：
1. 创建不同提供商（OpenAI、智普、DeepSeek）的客户端
2. 直接调用 complete() 方法获取响应
3. 打印响应内容

运行方式: python demo/01_direct_llm_call.py

注意：需要在环境变量中设置对应提供商的 API Key：
- OpenAI: export LLM_API_KEY=your-openai-key
- 智普: export LLM_API_KEY=your-zhipu-key
- DeepSeek: export LLM_API_KEY=your-deepseek-key

也可以在代码中直接修改 api_key 参数。
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from skill import OpenAIClient, ZhipuClient, DeepSeekClient, LLMConfig


def call_openai():
    """调用 OpenAI API"""
    print("\n" + "="*60)
    print("1. 调用 OpenAI (gpt-3.5-turbo)")
    print("="*60)
    
    config = LLMConfig(
        provider="openai",
        api_key=os.getenv("OPENAI_API_KEY", os.getenv("LLM_API_KEY", "sk-demo")),
        model="gpt-3.5-turbo",
    )
    
    client = OpenAIClient(config)
    
    try:
        response = client.complete("请用一句话介绍什么是人工智能？")
        print(f"响应内容: {response.content}")
        print(f"模型: {response.model}")
        print(f"Token 消耗: {response.total_tokens} (prompt={response.prompt_tokens}, completion={response.completion_tokens})")
        print(f"延迟: {response.latency_ms:.2f}ms")
    except Exception as e:
        print(f"调用失败: {e}")


def call_zhipu():
    """调用智普 AI API"""
    print("\n" + "="*60)
    print("2. 调用 智普 AI (glm-4-flash)")
    print("="*60)
    
    config = LLMConfig(
        provider="zhipu",
        api_key=os.getenv("ZHIPU_API_KEY", os.getenv("LLM_API_KEY", "")),
        model="glm-4-flash",
    )
    
    client = ZhipuClient(config)
    
    try:
        response = client.complete("请用一句话介绍什么是人工智能？")
        print(f"响应内容: {response.content}")
        print(f"模型: {response.model}")
        print(f"Token 消耗: {response.total_tokens} (prompt={response.prompt_tokens}, completion={response.completion_tokens})")
        print(f"延迟: {response.latency_ms:.2f}ms")
    except Exception as e:
        print(f"调用失败: {e}")


def call_deepseek():
    """调用 DeepSeek API"""
    print("\n" + "="*60)
    print("3. 调用 DeepSeek (deepseek-chat)")
    print("="*60)
    
    config = LLMConfig(
        provider="deepseek",
        api_key=os.getenv("DEEPSEEK_API_KEY", os.getenv("LLM_API_KEY", "")),
        model="deepseek-chat",
    )
    
    client = DeepSeekClient(config)
    
    try:
        response = client.complete("请用一句话介绍什么是人工智能？")
        print(f"响应内容: {response.content}")
        print(f"模型: {response.model}")
        print(f"Token 消耗: {response.total_tokens} (prompt={response.prompt_tokens}, completion={response.completion_tokens})")
        print(f"延迟: {response.latency_ms:.2f}ms")
    except Exception as e:
        print(f"调用失败: {e}")


def call_streaming():
    """流式调用示例"""
    print("\n" + "="*60)
    print("4. 流式调用 OpenAI (逐字返回)")
    print("="*60)
    
    config = LLMConfig(
        provider="openai",
        api_key=os.getenv("OPENAI_API_KEY", os.getenv("LLM_API_KEY", "sk-demo")),
        model="gpt-3.5-turbo",
    )
    
    client = OpenAIClient(config)
    
    try:
        print("响应内容:", end=" ", flush=True)
        for chunk in client.stream("请用一句话介绍什么是人工智能？"):
            print(chunk.content, end="", flush=True)
        print("\n")
    except Exception as e:
        print(f"调用失败: {e}")


if __name__ == "__main__":
    print("Demo 1: 直接调用 LLM")
    print("-" * 60)
    print("本示例展示如何直接创建不同提供商的 LLM 客户端并调用。")
    print("由于需要真实的 API Key，未配置 Key 的提供商调用会失败。")
    print("-" * 60)
    
    call_openai()
    call_zhipu()
    call_deepseek()
    call_streaming()
