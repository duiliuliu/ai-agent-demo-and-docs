"""
Demo 辅助工具 - 支持 Mock 和真实 LLM

功能：
1. 统一的日志配置（支持 info 输出）
2. 创建 Mock Agent 或真实 LLM Agent
3. 集成前面章节的 LLM 客户端和推理引擎

环境变量配置：
  LLM_PROVIDER=openai|zhipu|deepseek|mock (默认 mock)
  LLM_API_KEY=your-api-key
  LLM_BASE_URL=api-base-url
  LLM_MODEL=model-name
"""
import os
import sys
import logging
import importlib.util
from typing import Any, Callable

# 配置日志输出到控制台（info 级别全部打印）
logging.basicConfig(
    level=logging.INFO,
    format='%(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)

# 路径配置
demo_dir = os.path.dirname(os.path.abspath(__file__))
skill_dir = os.path.dirname(demo_dir)
workspace = os.path.dirname(skill_dir)

sys.path.insert(0, skill_dir)
sys.path.insert(0, workspace)

logger = logging.getLogger(__name__)


# ========== LLM 客户端加载 ==========

def _load_foundation_llm():
    """
    加载 01-foundation 模块的 LLM 客户端
    
    返回:
        llm_client: LLM 客户端实例或 None
    """
    provider = os.getenv("LLM_PROVIDER", "mock")
    
    if provider == "mock":
        return None
    
    api_key = os.getenv("LLM_API_KEY", "")
    base_url = os.getenv("LLM_BASE_URL", "")
    model = os.getenv("LLM_MODEL", "")
    
    if not api_key:
        logger.warning(f"[demo_helper] 未设置 LLM_API_KEY，将使用 mock 模式")
        return None
    
    try:
        # 动态加载 01-foundation 的 skill 包
        foundation_skill_dir = os.path.join(workspace, "01-foundation", "skill")
        
        if foundation_skill_dir not in sys.path:
            sys.path.insert(0, foundation_skill_dir)
        
        if provider.lower() in ["openai", "gpt"]:
            from openai_client import OpenAIClient, LLMConfig
            config = LLMConfig(api_key=api_key, base_url=base_url or None, model=model or "gpt-3.5-turbo")
            client = OpenAIClient(config=config)
            
        elif provider.lower() in ["zhipu", "glm"]:
            from zhipu_client import ZhipuClient, LLMConfig
            config = LLMConfig(api_key=api_key, base_url=base_url or None, model=model or "glm-4-flash")
            client = ZhipuClient(config=config)
            
        elif provider.lower() in ["deepseek"]:
            from deepseek_client import DeepSeekClient, LLMConfig
            config = LLMConfig(api_key=api_key, base_url=base_url or None, model=model or "deepseek-chat")
            client = DeepSeekClient(config=config)
            
        else:
            logger.warning(f"[demo_helper] 未知的 LLM 提供商: {provider}")
            return None
        
        logger.info(f"[demo_helper] 成功加载 {provider} LLM 客户端，model={config.model}")
        return client
        
    except Exception as e:
        logger.warning(f"[demo_helper] 加载 LLM 客户端失败: {e}，将使用 mock 模式")
        return None


# ========== Agent 创建工厂 ==========

def create_agent(name: str, role: str, response_template: str = None,
                 use_llm: bool = True, system_prompt: str = "") -> Any:
    """
    创建 Agent（自动选择真实 LLM 或 Mock）
    
    Args:
        name: Agent 名称
        role: Agent 角色/职责
        response_template: Mock 响应模板
        use_llm: 是否尝试使用真实 LLM
        system_prompt: 系统提示词（用于真实 LLM）
    
    Returns:
        agent: 可调用的 Agent 函数或对象
    """
    # 尝试加载真实 LLM
    llm_client = None
    if use_llm:
        llm_client = _load_foundation_llm()
    
    if llm_client is not None:
        # 返回真实 LLM Agent
        logger.info(f"  [Agent] {name}: 使用真实 LLM ({role})")
        return create_llm_agent(name, role, llm_client, system_prompt)
    else:
        # 返回 Mock Agent
        logger.info(f"  [Agent] {name}: 使用 Mock ({role})")
        return create_mock_agent(name, role, response_template)


def create_mock_agent(name: str, role: str, response_template: str = None) -> Callable:
    """创建 Mock Agent（用于测试和演示）"""
    def mock_agent(prompt: str) -> str:
        prompt_preview = prompt[:80] if len(prompt) > 80 else prompt
        
        if response_template:
            return response_template.replace("{prompt}", prompt_preview).replace("{role}", role)
        
        role_responses = {
            "数据收集员": f"[{name}] 收集到的数据：基于输入'{prompt_preview[:40]}...'，我收集到以下信息...",
            "分析师": f"[{name}] 分析结果：基于输入数据，我的分析结论是...",
            "撰写员": f"[{name}] 撰写内容：整合分析结果，我撰写了以下内容...",
            "审查员": f"[{name}] 审查意见：内容符合规范要求，建议发布",
            "调度员": f"[{name}] 任务分配：将任务分解为子任务并分配给各执行者",
            "正方": f"[{name}] 正方观点：我支持这个方案，主要理由包括...",
            "反方": f"[{name}] 反方观点：我反对这个方案，反驳如下...",
            "仲裁者": f"[{name}] 仲裁结论：综合正反双方观点，最终结论为...",
            "研究": f"[{name}] 研究结果：经过深入研究，我发现...",
            "数据分析": f"[{name}] 数据分析结果：数据显示趋势是...",
            "撰写": f"[{name}] 撰写完成：基于以上分析，报告如下...",
            "编辑": f"[{name}] 编辑审核：检查完毕，已优化部分表述",
            "质检": f"[{name}] 质检通过：内容质量达标，建议发布",
            "方案设计": f"[{name}] 设计方案：我提出以下技术方案...",
        }
        
        default_resp = f"[{name}] ({role}) 处理结果：{prompt_preview}..."
        return role_responses.get(role, default_resp)
    
    return mock_agent


def create_llm_agent(name: str, role: str, llm_client, system_prompt: str = "") -> Callable:
    """创建使用真实 LLM 的 Agent"""
    
    # 构建系统提示词
    if not system_prompt:
        system_prompt = f"""你是一个专业的 AI 助手，角色是【{role}】。
请根据你的专业视角回答问题。保持简洁、准确。

你的名字是：{name}
你的角色是：{role}
"""
    
    def llm_agent(prompt: str) -> str:
        full_prompt = f"{system_prompt}\n\n用户问题/任务：{prompt}"
        
        try:
            response = llm_client.complete(full_prompt)
            
            if hasattr(response, 'content'):
                return response.content
            elif hasattr(response, 'text'):
                return response.text
            else:
                return str(response)
                
        except Exception as e:
            logger.error(f"[{name}] LLM 调用失败: {e}")
            return f"[{name}] 调用失败: {str(e)}"
    
    return llm_agent


def print_config_info():
    """打印配置信息"""
    provider = os.getenv("LLM_PROVIDER", "mock")
    model = os.getenv("LLM_MODEL", "default")
    api_key_status = "已配置" if os.getenv("LLM_API_KEY") else "未配置"
    
    print("=" * 60)
    print("多 Agent 协作框架配置")
    print("=" * 60)
    print(f"  LLM 提供商: {provider}")
    print(f"  Model: {model}")
    print(f"  API Key: {api_key_status}")
    if os.getenv("LLM_BASE_URL"):
        print(f"  Base URL: {os.getenv('LLM_BASE_URL')}")
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
                output_str = str(output)
                preview = output_str[:100] + "..." if len(output_str) > 100 else output_str
                print(f"  {name}: {preview}")
        print()


def print_communication_trace(messages):
    """打印通信追踪记录"""
    print("=" * 60)
    print("通信追踪记录")
    print("=" * 60)
    for msg in messages:
        msg_type = msg.get('message_type', 'unknown')
        sender = msg.get('sender', '?')
        receiver = msg.get('receiver', '?')
        content = str(msg.get('content', ''))[:50]
        print(f"  [{msg_type}] {sender} -> {receiver}: {content}...")
    print()