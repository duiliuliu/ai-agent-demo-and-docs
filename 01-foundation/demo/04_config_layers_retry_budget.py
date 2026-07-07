"""
Demo 4: 配置分层、超时重试、Token 预算管理

这是 Demo 3 的升级版，展示如何：
1. 配置分层：默认值 < 配置文件 < 环境变量 < 代码传入
2. 超时控制：设置连接超时和读取超时
3. 指数退避重试：失败后自动重试，间隔递增
4. Token 预算管理：设置月度 Token 预算，超过阈值告警
5. 预算状态查询：实时查看预算使用情况

运行方式: python demo/04_config_layers_retry_budget.py

配置优先级说明:
- 默认值 (LLMConfig 类定义)
- config.json 文件
- 环境变量 (LLM_* 前缀)
- 代码传入参数 (最高优先级)

环境变量示例:
- LLM_API_KEY=your-key
- LLM_MODEL=gpt-3.5-turbo
- LLM_TIMEOUT=30
- LLM_MAX_RETRIES=3
- LLM_TOKEN_BUDGET=100000
- LLM_BUDGET_WARNING_THRESHOLD=0.8
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from skill import OpenAIClient, LLMConfig, RetryClient


def demonstrate_config_layers():
    """演示配置分层机制"""
    print("="*60)
    print("1. 配置分层演示")
    print("="*60)
    
    # 1. 默认配置
    default_config = LLMConfig()
    print("\n[默认配置] (来自 LLMConfig 类定义)")
    print(f"  Provider: {default_config.provider}")
    print(f"  Model: {default_config.model}")
    print(f"  Temperature: {default_config.temperature}")
    print(f"  Token Budget: {default_config.token_budget}")
    
    # 2. 配置文件
    config_path = os.path.join(os.path.dirname(__file__), "config.json")
    file_config = LLMConfig.from_file(config_path)
    print("\n[配置文件] (config.json)")
    print(f"  Model: {file_config.model}")
    print(f"  Max Tokens: {file_config.max_tokens}")
    
    # 3. 环境变量
    env_config = LLMConfig.from_env()
    print("\n[环境变量] (LLM_* 前缀)")
    print(f"  API Key: {'已设置' if env_config.api_key else '未设置'}")
    print(f"  Provider: {env_config.provider}")
    
    # 4. 代码传入
    code_config = LLMConfig(
        temperature=0.2,
        token_budget=50000,
    )
    print("\n[代码传入] (最高优先级)")
    print(f"  Temperature: {code_config.temperature}")
    print(f"  Token Budget: {code_config.token_budget}")
    
    # 5. 合并配置
    merged = default_config.merge(file_config).merge(env_config).merge(code_config)
    print("\n[最终合并配置]")
    print(f"  Provider: {merged.provider}")
    print(f"  Model: {merged.model}")
    print(f"  Temperature: {merged.temperature}")  # 来自代码传入
    print(f"  Token Budget: {merged.token_budget}")  # 来自代码传入
    print(f"  Max Retries: {merged.max_retries}")
    print(f"  Timeout: {merged.timeout}s")
    
    return merged


def demonstrate_retry_and_timeout(config: LLMConfig):
    """演示超时和重试机制"""
    print("\n" + "="*60)
    print("2. 超时重试演示")
    print("="*60)
    
    # 创建基础客户端
    base_client = OpenAIClient(config)
    
    # 创建带重试的客户端
    retry_client = RetryClient(base_client, config)
    
    print(f"配置: 超时={config.timeout}s, 最大重试={config.max_retries}次")
    
    prompts = [
        "请用一句话介绍人工智能",
        "什么是机器学习？",
        "解释一下深度学习",
    ]
    
    for i, prompt in enumerate(prompts, 1):
        print(f"\n调用 #{i}")
        try:
            response = retry_client.complete(prompt)
            print(f"  成功! Token: {response.total_tokens}, 延迟: {response.latency_ms:.2f}ms")
        except Exception as e:
            print(f"  失败: {e}")
    
    return retry_client


def demonstrate_budget_management(retry_client: RetryClient, config: LLMConfig):
    """演示 Token 预算管理"""
    print("\n" + "="*60)
    print("3. Token 预算管理演示")
    print("="*60)
    
    print(f"初始预算状态:")
    status = retry_client.get_budget_status()
    print(f"  已使用: {status['used']}")
    print(f"  预算: {status['budget']}")
    print(f"  剩余: {status['remaining']}")
    print(f"  使用率: {status['percentage']:.2f}%")
    
    # 模拟大量调用，触发预算警告
    print("\n开始大量调用以测试预算告警...")
    for i in range(10):
        try:
            response = retry_client.complete("请写一段关于人工智能的短文章，大约200字。")
            print(f"调用 #{i+1}: Token={response.total_tokens}, ", end="")
            
            status = retry_client.get_budget_status()
            print(f"使用率={status['percentage']:.2f}%")
            
            if status['remaining'] < 100:
                print("预算即将耗尽，停止调用")
                break
        except Exception as e:
            print(f"调用 #{i+1}: {e}")
            break
    
    # 最终状态
    print("\n最终预算状态:")
    status = retry_client.get_budget_status()
    print(f"  已使用: {status['used']}")
    print(f"  预算: {status['budget']}")
    print(f"  剩余: {status['remaining']}")
    print(f"  使用率: {status['percentage']:.2f}%")
    print(f"  是否触发警告: {'是' if status['warning_triggered'] else '否'}")


def main():
    print("Demo 4: 配置分层、超时重试、Token 预算管理")
    print("-" * 60)
    
    # 演示配置分层
    config = demonstrate_config_layers()
    
    # 演示超时重试
    retry_client = demonstrate_retry_and_timeout(config)
    
    # 演示预算管理
    demonstrate_budget_management(retry_client, config)
    
    print("\n" + "-" * 60)
    print("Demo 4 完成!")
    print("要点总结:")
    print("  1. 配置分层确保不同环境使用不同配置")
    print("  2. 超时重试提高了调用的稳定性")
    print("  3. Token 预算管理防止意外超支")


if __name__ == "__main__":
    main()
