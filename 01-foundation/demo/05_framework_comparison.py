"""
Demo 5: 市面上主流 LLM 框架对比分析

本示例展示如何使用不同的框架调用 LLM，并进行对比分析：
1. 原生 OpenAI SDK
2. LiteLLM（统一多厂商 API）
3. LangChain（应用开发框架）
4. LlamaIndex（数据索引框架）
5. FastChat（对话系统框架）

运行方式: python demo/05_framework_comparison.py

注意：本示例主要展示框架的代码风格和调用方式，
部分示例需要安装对应的依赖包。
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def compare_frameworks():
    """对比不同框架的特点"""
    print("="*80)
    print("LLM 框架对比分析")
    print("="*80)
    
    frameworks = [
        {
            "name": "OpenAI SDK",
            "description": "OpenAI 官方 SDK，最基础的调用方式",
            "pros": ["官方支持，稳定可靠", "API 文档完善", "支持流式调用", "社区活跃"],
            "cons": ["只支持 OpenAI 系列模型", "功能较基础，需要自己封装", "缺乏高级特性"],
            "适用场景": ["快速原型开发", "只使用 OpenAI 模型", "需要精细控制调用"],
            "安装": "pip install openai",
        },
        {
            "name": "LiteLLM",
            "description": "统一多厂商 LLM API，支持 100+ 模型",
            "pros": ["统一 API，无缝切换模型", "支持几乎所有主流模型", "内置重试和错误处理", "支持代理和缓存"],
            "cons": ["社区维护，可能有延迟", "部分模型特性支持不完整"],
            "适用场景": ["需要支持多种模型", "跨平台迁移", "成本优化（选择最便宜模型）"],
            "安装": "pip install litellm",
        },
        {
            "name": "LangChain",
            "description": "LLM 应用开发框架，提供链式调用能力",
            "pros": ["丰富的组件库", "支持 RAG、Agent、工具调用", "强大的社区生态", "模块化设计"],
            "cons": ["学习曲线陡峭", "版本迭代快，API 不稳定", "抽象层级高，调试困难"],
            "适用场景": ["复杂 Agent 应用", "RAG 系统", "需要多种组件组合"],
            "安装": "pip install langchain",
        },
        {
            "name": "LlamaIndex",
            "description": "专注于数据索引和 RAG 的框架",
            "pros": ["强大的数据连接能力", "内置 RAG 流水线", "支持多种文档格式", "与 LangChain 兼容"],
            "cons": ["主要聚焦 RAG，通用能力弱", "学习曲线较陡"],
            "适用场景": ["文档问答系统", "企业知识库", "数据密集型应用"],
            "安装": "pip install llama-index",
        },
        {
            "name": "FastChat",
            "description": "开放的对话系统框架，支持模型部署",
            "pros": ["支持模型部署（vLLM 集成）", "多轮对话管理", "支持函数调用", "性能优化"],
            "cons": ["部署复杂度较高", "文档相对较少"],
            "适用场景": ["自建对话服务", "需要高性能推理", "模型私有化部署"],
            "安装": "pip install "fastchat",
        },
        {
            "name": "本项目 skill",
            "description": "从零实现的轻量级 LLM 调用框架",
            "pros": ["代码透明，易于理解", "轻量级，无过多依赖", "接口简洁", "适合学习"],
            "cons": ["功能较少，需要自行扩展", "无社区支持", "不适合大型项目"],
            "适用场景": ["学习 LLM 调用原理", "小型项目", "定制化需求"],
            "安装": "无需安装，直接引用 skill/",
        },
    ]
    
    for i, fw in enumerate(frameworks, 1):
        print(f"\n{i}. {fw['name']}")
        print("-" * 60)
        print(f"描述: {fw['description']}")
        print("\n优点:")
        for p in fw["pros"]:
            print(f"  - {p}")
        print("\n缺点:")
        for c in fw["cons"]:
            print(f"  - {c}")
        print("\n适用场景:")
        for s in fw["适用场景"]:
            print(f"  - {s}")
        print(f"\n安装: {fw['安装']}")


def show_openai_sdk_example():
    """展示 OpenAI SDK 的调用方式"""
    print("\n" + "="*80)
    print("示例 1: OpenAI SDK 调用")
    print("="*80)
    print("""
# 安装: pip install openai

from openai import OpenAI

client = OpenAI(
    api_key=os.getenv("OPENAI_API_KEY"),
)

# 同步调用
response = client.chat.completions.create(
    model="gpt-3.5-turbo",
    messages=[{"role": "user", "content": "Hello"}],
)
print(response.choices[0].message.content)

# 流式调用
stream = client.chat.completions.create(
    model="gpt-3.5-turbo",
    messages=[{"role": "user", "content": "Hello"}],
    stream=True,
)
for chunk in stream:
    print(chunk.choices[0].delta.content or "", end="")
""")


def show_litellm_example():
    """展示 LiteLLM 的调用方式"""
    print("\n" + "="*80)
    print("示例 2: LiteLLM 调用（统一多厂商）")
    print("="*80)
    print("""
# 安装: pip install litellm

from litellm import completion

# 调用 OpenAI
response = completion(
    model="gpt-3.5-turbo",
    messages=[{"role": "user", "content": "Hello"}],
    api_key=os.getenv("OPENAI_API_KEY"),
)

# 调用智普（只需改 model 和 api_key）
response = completion(
    model="zhipu/glm-4",
    messages=[{"role": "user", "content": "Hello"}],
    api_key=os.getenv("ZHIPU_API_KEY"),
)

# 调用 DeepSeek
response = completion(
    model="deepseek/deepseek-chat",
    messages=[{"role": "user", "content": "Hello"}],
    api_key=os.getenv("DEEPSEEK_API_KEY"),
)

# 自动重试和错误处理
response = completion(
    model="gpt-3.5-turbo",
    messages=[{"role": "user", "content": "Hello"}],
    max_retries=3,
    timeout=30,
)
""")


def show_langchain_example():
    """展示 LangChain 的调用方式"""
    print("\n" + "="*80)
    print("示例 3: LangChain 调用")
    print("="*80)
    print("""
# 安装: pip install langchain langchain-openai

from langchain_openai import ChatOpenAI
from langchain.prompts import ChatPromptTemplate
from langchain.schema.output_parser import StrOutputParser

# 创建 LLM
llm = ChatOpenAI(model="gpt-3.5-turbo")

# 创建 Prompt 模板
prompt = ChatPromptTemplate.from_messages([
    ("system", "你是一个专业助手"),
    ("user", "{input}"),
])

# 创建链式调用
chain = prompt | llm | StrOutputParser()

# 执行
result = chain.invoke({"input": "请介绍人工智能"})
print(result)

# RAG 示例（需要额外安装依赖）
# from langchain.document_loaders import WebBaseLoader
# from langchain.vectorstores import FAISS
# from langchain.embeddings import OpenAIEmbeddings
# ...
""")


def show_llamaindex_example():
    """展示 LlamaIndex 的调用方式"""
    print("\n" + "="*80)
    print("示例 4: LlamaIndex 调用（RAG 场景）")
    print("="*80)
    print("""
# 安装: pip install llama-index llama-index-llms-openai

from llama_index.llms.openai import OpenAI
from llama_index.core import VectorStoreIndex, SimpleDirectoryReader

# 加载文档
documents = SimpleDirectoryReader("data/").load_data()

# 创建索引
index = VectorStoreIndex.from_documents(documents)

# 创建查询引擎
query_engine = index.as_query_engine()

# 查询
response = query_engine.query("文档中的主要观点是什么？")
print(response)

# 对话模式
chat_engine = index.as_chat_engine()
response = chat_engine.chat("请详细解释一下")
print(response)
""")


def show_fastchat_example():
    """展示 FastChat 的调用方式"""
    print("\n" + "="*80)
    print("示例 5: FastChat 调用")
    print("="*80)
    print("""
# 安装: pip install "fastchat"

# 部署模型（命令行）
# python -m fastchat.serve.controller
# python -m fastchat.serve.model_worker --model-path lmsys/vicuna-7b-v1.5
# python -m fastchat.serve.openai_api_server --host localhost --port 8000

# Python 调用（通过 OpenAI 兼容 API）
from openai import OpenAI

client = OpenAI(
    api_key="EMPTY",
    base_url="http://localhost:8000/v1",
)

response = client.chat.completions.create(
    model="vicuna-7b-v1.5",
    messages=[{"role": "user", "content": "Hello"}],
)
print(response.choices[0].message.content)
""")


def show_our_skill_example():
    """展示本项目 skill 的调用方式"""
    print("\n" + "="*80)
    print("示例 6: 本项目 skill 调用")
    print("="*80)
    print("""
# 无需安装，直接引用

from skill import OpenAIClient, ZhipuClient, LLMConfig, Tracer, RetryClient

# 创建配置
config = LLMConfig(
    api_key=os.getenv("LLM_API_KEY"),
    model="gpt-3.5-turbo",
    temperature=0.7,
)

# 创建客户端
client = OpenAIClient(config)

# 添加追踪
tracer = Tracer(log_file="llm_trace.log")

# 添加重试和预算管理
retry_client = RetryClient(client, config)

# 调用
response = retry_client.complete("请介绍人工智能")
print(response.content)

# 查看预算状态
status = retry_client.get_budget_status()
print(f"Token 使用率: {status['percentage']:.2f}%")
""")


def summarize_recommendations():
    """总结推荐选择"""
    print("\n" + "="*80)
    print("框架选择建议")
    print("="*80)
    print("""
选择哪个框架取决于你的需求：

1. 如果你只是想快速调用 LLM，不需要复杂功能：
   → OpenAI SDK（只使用 OpenAI）或 LiteLLM（多模型支持）

2. 如果你需要构建复杂的 Agent 或 RAG 系统：
   → LangChain（功能全面）或 LlamaIndex（专注 RAG）

3. 如果你需要自建高性能对话服务：
   → FastChat + vLLM

4. 如果你想学习 LLM 调用的底层原理：
   → 本项目 skill（代码透明，易于理解）

5. 如果你需要跨平台迁移或成本优化：
   → LiteLLM（统一 API，无缝切换）

推荐学习路径：
1. 先用本项目 skill 理解底层原理
2. 再学习 OpenAI SDK 掌握基础调用
3. 最后根据需求选择 LangChain 或 LlamaIndex
""")


def main():
    print("Demo 5: 市面上主流 LLM 框架对比分析")
    print("-" * 80)
    print("本示例展示不同框架的特点、优缺点和适用场景。")
    print("代码示例仅展示调用方式，不会实际执行。")
    print("-" * 80)
    
    compare_frameworks()
    show_openai_sdk_example()
    show_litellm_example()
    show_langchain_example()
    show_llamaindex_example()
    show_fastchat_example()
    show_our_skill_example()
    summarize_recommendations()
    
    print("\n" + "-" * 80)
    print("Demo 5 完成!")
    print("要点总结:")
    print("  1. 没有最好的框架，只有最适合的框架")
    print("  2. 根据项目复杂度和需求选择")
    print("  3. 学习底层原理有助于更好地使用高级框架")


if __name__ == "__main__":
    main()
