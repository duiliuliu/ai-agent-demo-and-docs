"""
Demo 3: 记录 Token 消耗和日志

这是 Demo 2 的升级版，展示如何：
1. 使用 Tracer 记录每次 LLM 调用的详细信息
2. 记录 Token 消耗、延迟、模型信息
3. 输出结构化日志到控制台和文件
4. 获取统计信息（调用次数、总 Token、平均延迟）

运行方式: python demo/03_token_tracking_and_logging.py

本示例会生成日志文件: demo/llm_trace.log
"""

import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from skill import OpenAIClient, LLMConfig, Tracer, TraceRecord


def main():
    print("Demo 3: 记录 Token 消耗和日志")
    print("-" * 60)
    
    # 加载配置
    config = LLMConfig.from_env()
    
    # 创建追踪器，同时输出到控制台和文件
    log_file = os.path.join(os.path.dirname(__file__), "llm_trace.log")
    tracer = Tracer(enabled=True, log_file=log_file)
    print(f"追踪器已启动，日志文件: {log_file}")
    
    # 创建客户端
    client = OpenAIClient(config)
    
    # 定义要调用的 prompts
    prompts = [
        "请用一句话介绍什么是人工智能？",
        "机器学习和深度学习的区别是什么？",
        "AI 在医疗领域有哪些应用？",
        "什么是大语言模型？",
        "请解释一下 Transformer 架构？",
    ]
    
    print("\n开始调用 LLM...")
    print("-" * 60)
    
    for i, prompt in enumerate(prompts, 1):
        # 开始追踪
        trace_id = tracer.start()
        print(f"\n调用 #{i} - Trace ID: {trace_id}")
        print(f"Prompt: {prompt[:50]}...")
        
        try:
            # 调用 LLM
            response = client.complete(prompt)
            
            # 创建追踪记录
            record = TraceRecord(
                trace_id=trace_id,
                timestamp=datetime.now(),
                provider=config.provider,
                model=response.model,
                prompt=prompt,
                prompt_tokens=response.prompt_tokens,
                completion_tokens=response.completion_tokens,
                total_tokens=response.total_tokens,
                latency_ms=response.latency_ms,
                response=response.content,
                status="success",
            )
            
            # 记录追踪信息
            tracer.record(trace_id, record)
            
            # 打印响应摘要
            print(f"响应长度: {len(response.content)} 字符")
            print(f"Token 消耗: {response.total_tokens} (prompt={response.prompt_tokens}, completion={response.completion_tokens})")
            print(f"延迟: {response.latency_ms:.2f}ms")
            
        except Exception as e:
            # 创建失败记录
            record = TraceRecord(
                trace_id=trace_id,
                timestamp=datetime.now(),
                provider=config.provider,
                model=config.model,
                prompt=prompt,
                prompt_tokens=0,
                completion_tokens=0,
                total_tokens=0,
                latency_ms=0,
                response="",
                status="failed",
                error=str(e),
            )
            
            # 记录失败信息
            tracer.record(trace_id, record)
            print(f"调用失败: {e}")
    
    # 获取并打印统计信息
    print("\n" + "="*60)
    print("调用统计汇总")
    print("="*60)
    stats = tracer.get_stats()
    print(f"总调用次数: {stats['call_count']}")
    print(f"总 Token 消耗: {stats['total_tokens']}")
    print(f"平均延迟: {stats['average_latency_ms']:.2f}ms")
    
    # 重置统计
    tracer.reset_stats()
    print("\n统计信息已重置")
    
    print("\n提示: 请查看日志文件了解详细追踪信息")


if __name__ == "__main__":
    main()
