"""
Demo 06: Agent 平台模式（Agent Platform）

场景：Agent 动态注册到平台，自行发现和协作
协作模式：AGENT_PLATFORM（动态发现）
通信方式：发布-订阅（Pub/Sub）

适用场景：
  - 开放环境：Agent 来源不确定
  - 动态需求：任务类型变化大
  - 灵活协作：Agent 自行匹配任务

运行方式：
  python demo/06_agent_platform.py
"""
import os
import sys
import logging

logging.basicConfig(level=logging.INFO, format='%(message)s')

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from demo.demo_helper import create_mock_agent, print_config_info, print_result
from agent_swarm import AgentSwarm, CollaborationPattern
from communication_bus import PubSubBus


class AgentPlatform:
    """
    Agent 平台
    
    支持：
    1. Agent 动态注册和发现
    2. 能力匹配和任务分发
    3. 发布-订阅通信
    4. 运行时协作关系建立
    """

    def __init__(self, name: str = "agent_platform"):
        self.name = name
        self.bus = PubSubBus()
        self.agents: dict = {}
        self.capability_index: dict = {}  # capability -> [agent_names]

    def register_agent(self, name: str, agent_instance, capabilities: list) -> None:
        """注册 Agent 到平台"""
        self.agents[name] = agent_instance

        # 索引能力
        for cap in capabilities:
            if cap not in self.capability_index:
                self.capability_index[cap] = []
            self.capability_index[cap].append(name)

        # 创建订阅主题
        self.bus.create_topic(f"task_for_{name}")
        self.bus.subscribe(name, f"task_for_{name}")

        logging.info(f"[Platform] Agent '{name}' 注册成功，能力: {capabilities}")

    def find_agents_by_capability(self, capability: str) -> list:
        """根据能力查找 Agent"""
        return self.capability_index.get(capability, [])

    def publish_task(self, task: str, required_capabilities: list, trace_id: str = "") -> dict:
        """发布任务到平台"""
        results = {}

        for cap in required_capabilities:
            agents = self.find_agents_by_capability(cap)

            for agent_name in agents:
                agent = self.agents[agent_name]

                # 发布任务给匹配的 Agent
                self.bus.publish(
                    sender="platform",
                    topic=f"task_for_{agent_name}",
                    content=task,
                    trace_id=trace_id
                )

                # 获取 Agent 响应（简化：直接调用）
                result = self._call_agent(agent_name, agent, task)
                results[agent_name] = result

                logging.info(f"[Platform] Agent '{agent_name}' 执行任务完成")

        return results

    def _call_agent(self, name: str, agent, prompt: str) -> str:
        """调用 Agent"""
        if hasattr(agent, 'run'):
            result = agent.run(prompt)
            return result.final_answer if hasattr(result, 'final_answer') else str(result)
        elif callable(agent):
            return str(agent(prompt))
        return str(agent)


def demo_agent_platform():
    """Agent 平台模式演示"""
    print_config_info()
    
    # 创建 Agent 平台
    platform = AgentPlatform(name="open_platform")
    
    # 动态注册多个 Agent（模拟开放环境）
    platform.register_agent(
        name="weather_agent",
        agent_instance=create_mock_agent("weather_agent", "天气服务",
            "[weather_agent] 天气查询结果：北京晴天25°C，上海多云28°C"),
        capabilities=["天气查询", "气象预报"]
    )
    
    platform.register_agent(
        name="flight_agent",
        agent_instance=create_mock_agent("flight_agent", "航班服务",
            "[flight_agent] 航班查询结果：CA123 北京-上海 08:00-10:30"),
        capabilities=["航班查询", "机票预订"]
    )
    
    platform.register_agent(
        name="hotel_agent",
        agent_instance=create_mock_agent("hotel_agent", "酒店服务",
            "[hotel_agent] 酒店查询结果：上海浦东香格里拉 ¥680/晚"),
        capabilities=["酒店查询", "房间预订"]
    )
    
    platform.register_agent(
        name="calc_agent",
        agent_instance=create_mock_agent("calc_agent", "计算服务",
            "[calc_agent] 计算结果：总价 = 680 + 580 = 1260元"),
        capabilities=["数学计算", "费用估算"]
    )
    
    # 展示平台能力索引
    print("=" * 60)
    print("Agent 平台能力索引")
    print("=" * 60)
    for cap, agents in platform.capability_index.items():
        print(f"  {cap}: {agents}")
    print()
    
    # 场景1：发布需要天气和航班的任务
    print("-" * 60)
    print("场景1：查询天气和航班")
    print("-" * 60)
    
    task1 = "查询北京天气和北京到上海的航班"
    results1 = platform.publish_task(
        task=task1,
        required_capabilities=["天气查询", "航班查询"],
        trace_id="task_001"
    )
    
    for agent, result in results1.items():
        print(f"  {agent}: {result}")
    
    # 场景2：发布需要酒店和计算的任务
    print()
    print("-" * 60)
    print("场景2：查询酒店并计算费用")
    print("-" * 60)
    
    task2 = "查询上海酒店价格并计算3晚费用"
    results2 = platform.publish_task(
        task=task2,
        required_capabilities=["酒店查询", "数学计算"],
        trace_id="task_002"
    )
    
    for agent, result in results2.items():
        print(f"  {agent}: {result}")
    
    return results1, results2


def explain_agent_platform():
    """解释 Agent 平台模式"""
    print()
    print("=" * 60)
    print("Agent 平台模式（Agent Platform）解析")
    print("=" * 60)
    print("""
## 协作流程

1. Agent 动态注册到平台，声明能力
2. 平台建立能力索引（capability -> agents）
3. 任务发布到平台，指定所需能力
4. 平台匹配 Agent，分发任务
5. Agent 执行任务，返回结果

## 关键设计点

1. **动态注册**：Agent 可以随时加入/离开平台
2. **能力索引**：快速匹配任务和 Agent
3. **发布-订阅**：Agent 订阅感兴趣的任务主题
4. **任务路由**：根据能力自动路由到合适的 Agent

## 与其他模式的区别

| 模式 | Agent关系 | 通信方式 | 适用场景 |
|------|-----------|----------|----------|
| Agent平台 | 动态发现 | 发布订阅 | 开放环境 |
| 主子模式 | 固定主从 | 集中式 | 封闭系统 |
| 流水线 | 固定顺序 | 黑板共享 | 流程固定 |

## 适用场景

- 开放环境：Agent 来源不确定
- 动态需求：任务类型变化大
- 灵活协作：需要运行时匹配

## 企业注意点

1. **能力认证**：Agent 声明的能力需要验证
2. **负载均衡**：同一能力多个 Agent 时需要均衡
3. **健康检查**：定期检查 Agent 可用性
4. **安全隔离**：Agent 之间不应有直接访问权限
5. **版本管理**：Agent 能力变更需要版本管理

## 扩展思考

Agent 平台是企业级多 Agent 系统的基础设施：
- 类似微服务注册中心（如 Nacos、Consul）
- 支持 Agent 的生命周期管理
- 支持服务的发现和路由
- 支持监控和治理
""")


if __name__ == "__main__":
    demo_agent_platform()
    explain_agent_platform()