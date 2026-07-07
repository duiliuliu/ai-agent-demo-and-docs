"""
Demo 2: 管理配置和 Prompt

这是 Demo 1 的升级版，展示如何：
1. 使用 JSON 配置文件管理 LLM 参数
2. 使用环境变量覆盖配置文件
3. 使用 Prompt 模板统一管理提示词
4. 动态填充模板变量

运行方式: python demo/02_config_and_prompt.py

配置文件: demo/config.json
环境变量: LLM_API_KEY, LLM_MODEL 等
"""

import os
import sys
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from skill import OpenAIClient, LLMConfig


class PromptTemplate:
    """
    Prompt 模板管理器
    支持从文件加载模板，并动态填充变量
    """
    
    def __init__(self, templates: dict):
        """
        Args:
            templates: 模板字典，key 是模板名称，value 是模板字符串
        """
        self.templates = templates
    
    @classmethod
    def from_file(cls, file_path: str) -> "PromptTemplate":
        """从 JSON 文件加载模板"""
        with open(file_path, "r", encoding="utf-8") as f:
            templates = json.load(f)
        return cls(templates)
    
    def render(self, template_name: str, **kwargs) -> str:
        """
        渲染模板，填充变量
        
        Args:
            template_name: 模板名称
            **kwargs: 模板变量
        
        Returns:
            str: 渲染后的完整 prompt
        """
        if template_name not in self.templates:
            raise ValueError(f"模板不存在: {template_name}")
        
        template = self.templates[template_name]
        
        try:
            return template.format(**kwargs)
        except KeyError as e:
            raise ValueError(f"模板缺少变量: {e}")


def load_config():
    """
    加载配置：先从配置文件加载，再用环境变量覆盖
    配置优先级：默认值 < 配置文件 < 环境变量
    """
    config_path = os.path.join(os.path.dirname(__file__), "config.json")
    
    # 1. 从配置文件加载
    if os.path.exists(config_path):
        print(f"加载配置文件: {config_path}")
        file_config = LLMConfig.from_file(config_path)
    else:
        print("配置文件不存在，使用默认配置")
        file_config = LLMConfig()
    
    # 2. 从环境变量加载
    env_config = LLMConfig.from_env()
    
    # 3. 合并配置：环境变量覆盖配置文件
    merged_config = file_config.merge(env_config)
    
    return merged_config


def main():
    print("Demo 2: 管理配置和 Prompt")
    print("-" * 60)
    
    # 加载配置
    config = load_config()
    print(f"\n最终配置:")
    print(f"  Provider: {config.provider}")
    print(f"  Model: {config.model}")
    print(f"  Temperature: {config.temperature}")
    print(f"  Max Tokens: {config.max_tokens}")
    print(f"  Timeout: {config.timeout}s")
    
    # 加载 Prompt 模板
    template_path = os.path.join(os.path.dirname(__file__), "prompt_templates.json")
    if not os.path.exists(template_path):
        # 如果模板文件不存在，创建一个默认模板
        default_templates = {
            "analyze_text": "请分析以下文本，并给出你的见解：\n\n{text}\n\n分析结果：",
            "summarize": "请用不超过{max_length}字总结以下内容：\n\n{content}\n\n总结：",
            "translate": "请将以下{source_lang}文本翻译成{target_lang}：\n\n{text}\n\n翻译结果：",
        }
        with open(template_path, "w", encoding="utf-8") as f:
            json.dump(default_templates, f, indent=2, ensure_ascii=False)
        print(f"\n创建默认模板文件: {template_path}")
    
    prompt_manager = PromptTemplate.from_file(template_path)
    print(f"可用模板: {list(prompt_manager.templates.keys())}")
    
    # 创建客户端
    client = OpenAIClient(config)
    
    # 使用模板生成 Prompt 并调用
    print("\n" + "="*60)
    print("示例 1: 使用 analyze_text 模板")
    print("="*60)
    text_to_analyze = "人工智能正在改变我们的生活方式，从智能家居到自动驾驶，AI技术的应用越来越广泛。"
    prompt = prompt_manager.render("analyze_text", text=text_to_analyze)
    print(f"渲染后的 Prompt:\n{prompt}\n")
    
    try:
        response = client.complete(prompt)
        print(f"响应内容:\n{response.content}")
        print(f"Token 消耗: {response.total_tokens}")
    except Exception as e:
        print(f"调用失败: {e}")
    
    # 示例 2: 使用 summarize 模板
    print("\n" + "="*60)
    print("示例 2: 使用 summarize 模板")
    print("="*60)
    long_content = """
    机器学习是人工智能的一个分支，它使计算机能够从数据中学习并做出预测或决策，而无需被明确编程。
    机器学习算法使用统计技术使计算机能够从数据中学习。随着更多数据可用，这些算法可以提高其性能。
    机器学习在许多领域都有应用，包括图像识别、自然语言处理、推荐系统和自动驾驶汽车。
    监督学习、无监督学习和强化学习是机器学习的三大主要类型。
    """
    prompt = prompt_manager.render("summarize", content=long_content, max_length=50)
    print(f"渲染后的 Prompt:\n{prompt}\n")
    
    try:
        response = client.complete(prompt)
        print(f"响应内容:\n{response.content}")
        print(f"Token 消耗: {response.total_tokens}")
    except Exception as e:
        print(f"调用失败: {e}")
    
    # 示例 3: 使用 translate 模板
    print("\n" + "="*60)
    print("示例 3: 使用 translate 模板")
    print("="*60)
    chinese_text = "我爱学习人工智能"
    prompt = prompt_manager.render("translate", text=chinese_text, source_lang="中文", target_lang="英文")
    print(f"渲染后的 Prompt:\n{prompt}\n")
    
    try:
        response = client.complete(prompt)
        print(f"响应内容:\n{response.content}")
        print(f"Token 消耗: {response.total_tokens}")
    except Exception as e:
        print(f"调用失败: {e}")


if __name__ == "__main__":
    main()
