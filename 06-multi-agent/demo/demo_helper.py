"""
Demo 辅助工具

提供统一的 Agent 创建和配置功能，支持真实 LLM 和 Mock 模式。
"""
import os
import sys
import logging

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)

# 添加依赖路径
demo_dir = os.path.dirname(os.path.abspath(__file__))
skill_dir = os.path.dirname(demo_dir)
workspace = os.path.dirname(skill_dir)

sys.path.insert(0, skill_dir)  # 06-multi-agent
sys.path.insert(0, workspace)  # /workspace


def create_mock_agent(name: str, role: str, response_template: str = None):
    """
    创建 Mock Agent（用于测试和演示）
    
    Args:
        name: Agent 名称
        role: Agent 角色
        response_template: 响应模板（可选）
    
    Returns:
        可调用的 Agent 函数
    """
    def mock_agent(prompt: str) -> str:
        # 截取 prompt 前 50 字符用于显示
        prompt_preview = prompt[:50] if len(prompt) > 50 else prompt
        
        if response_template:
            # 替换模板中的占位符
            return response_template.replace("{prompt}", prompt_preview).replace("{role}", role)
        
        # 根据角色生成不同风格的响应
        role_responses = {
            "数据收集员": f"[{name}] 收集到的数据：{prompt_preview}...",
            "分析师": f"[{name}] 分析结果：基于输入'{prompt_preview[:30]}'，我的分析结论是...",
            "撰写员": f"[{name}] 撰写内容：{prompt_preview}，整合后的文档如下...",
            "审查员": f"[{name}] 审查意见：'{prompt_preview[:30]}' 内容符合要求",
            "调度员": f"[{name}] 任务分配：将'{prompt_preview[:30]}'分解为子任务...",
            "正方": f"[{name}] 正方观点：支持'{prompt_preview[:30]}'，理由是...",
            "反方": f"[{name}] 反方观点：反对'{prompt_preview[:30]}'，反驳如下...",
            "仲裁者": f"[{name}] 仲裁结论：综合辩论内容，最终裁决...",
        }
        
        return role_responses.get(role, f"[{name}] ({role}) 处理结果：{prompt_preview}")
    
    return mock_agent


def print_config_info():
    """打印配置信息"""
    provider = os.getenv("LLM_PROVIDER", "mock")
    model = os.getenv("LLM_MODEL", "default")
    
    print("=" * 60)
    print("多 Agent 协作配置")
    print("=" * 60)
    print(f"  LLM 提供商: {provider}")
    print(f"  Model: {model}")
    print()


def print_result(result, title: str = "执行结果"):
    """打印协作结果"""
    print("-" * 60)
    print(f"{title}:")
    print("-" * 60)
    print(result.summary())
    print()
    
    if hasattr(result, 'agent_results') and result.agent_results:
        print("各 Agent 结果:")
        for name, output in result.agent_results.items():
            if output:
                print(f"  {name}: {output[:100]}..." if len(str(output)) > 100 else f"  {name}: {output}")
        print()


def print_communication_trace(messages):
    """打印通信追踪"""
    print("=" * 60)
    print("通信追踪记录")
    print("=" * 60)
    for msg in messages:
        print(f"  [{msg['message_type']}] {msg['sender']} -> {msg['receiver']}")
        content_preview = str(msg['content'])[:50]
        print(f"    内容: {content_preview}...")
    print()