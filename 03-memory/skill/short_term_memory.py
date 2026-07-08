"""
短期记忆（Short-Term Memory）- 优化版

设计理念（替代原"按时间过期"）：
  把短期记忆建模为"会话段（SessionSegment）"列表，而不是平铺消息流。
  每个会话段是一个有内聚话题/任务的消息集合。
  滚动策略：
    1. 新消息追加到当前活跃段
    2. 检测"段边界信号"（话题切换/长停顿/用户明确结束）
    3. 段结束时做信息密度评分
    4. 高密度段保留，低密度段淘汰
    5. 始终只保留最近 N 个段（而非 N 条消息）

会话段的生命周期：
  ACTIVE    : 当前正在累积消息
  CLOSED    : 已结束，等待压缩后转长期
  PROMOTED  : 已提取关键信息到长期记忆

降噪评分：
  - 噪音/确认   : 0 分
  - 致谢/礼貌   : 0.2 分
  - 普通对话    : 0.5 分
  - 事实陈述    : 0.8 分
  - 偏好/决策   : 1.5 分
"""
from typing import Dict, Any, List, Optional
from collections import deque
from datetime import datetime, timedelta
import re
from .base_memory import BaseMemory, MemoryEntry


class SessionSegment:
    """一个有内聚话题的会话段"""

    def __init__(self, segment_id: int, topic: str = ""):
        self.segment_id = segment_id
        self.topic = topic
        self.messages: List[Dict[str, Any]] = []
        self.created_at = datetime.now()
        self.last_active_at = datetime.now()
        self.state = "active"  # active / closed / promoted

    def add_message(self, role: str, content: str) -> None:
        self.messages.append({
            "role": role,
            "content": content,
            "timestamp": datetime.now().isoformat()
        })
        self.last_active_at = datetime.now()

    def close(self) -> None:
        self.state = "closed"

    def mark_promoted(self) -> None:
        self.state = "promoted"

    def message_count(self) -> int:
        return len(self.messages)

    def token_estimate(self) -> int:
        return int(sum(len(m["content"]) for m in self.messages) / 4)

    def get_messages(self) -> List[Dict[str, Any]]:
        return list(self.messages)

    def is_empty(self) -> bool:
        return len(self.messages) == 0


class ShortTermMemory(BaseMemory):
    """基于会话段的短期记忆"""

    def __init__(
        self,
        max_segments: int = 5,           # 保留最近 N 个段
        max_tokens_per_segment: int = 800,  # 单段最大 Token
        segment_timeout_minutes: int = 5,   # 段超时（分钟）
        density_threshold: float = 0.3     # 段保留的最低信息密度
    ):
        self._segments: deque = deque(maxlen=max_segments)
        self._current_segment: Optional[SessionSegment] = None
        self._segment_counter = 0
        self._max_segments = max_segments
        self._max_tokens_per_segment = max_tokens_per_segment
        self._segment_timeout = timedelta(minutes=segment_timeout_minutes)
        self._density_threshold = density_threshold

    def _get_or_create_current_segment(self, topic: str = "") -> SessionSegment:
        if self._current_segment is None or self._is_segment_timed_out():
            self._finalize_current_segment()
            self._segment_counter += 1
            self._current_segment = SessionSegment(
                segment_id=self._segment_counter,
                topic=topic
            )
        return self._current_segment

    def _is_segment_timed_out(self) -> bool:
        if self._current_segment is None:
            return False
        return (datetime.now() - self._current_segment.last_active_at) > self._segment_timeout

    def _finalize_current_segment(self) -> None:
        """结束当前段，评估并决定是否保留"""
        if self._current_segment is None or self._current_segment.is_empty():
            self._current_segment = None
            return

        density = self._calculate_density(self._current_segment)
        if density >= self._density_threshold:
            self._current_segment.close()
            self._segments.append(self._current_segment)
        # 低密度段直接丢弃
        self._current_segment = None

    def _calculate_density(self, segment: SessionSegment) -> float:
        """计算会话段的信息密度"""
        if segment.is_empty():
            return 0.0
        total = 0.0
        for msg in segment.messages:
            total += self._message_value(msg["content"])
        return total / segment.message_count()

    def _message_value(self, content: str) -> float:
        """
        评估单条消息的信息价值
        返回 0~1.5 的分数
        """
        content = content.strip()
        if not content:
            return 0.0

        # 噪音
        if self._is_noise(content):
            return 0.0

        # 偏好/决策类（最高价值）
        preference_signals = ["喜欢", "偏好", "想要", "需要", "决定", "选", "改", "不想要"]
        if any(s in content for s in preference_signals):
            return 1.5

        # 事实陈述
        fact_patterns = [r"是.{1,20}", r"有.{1,20}", r"在.{1,30}", r"\d+", r"[A-Z]{2,}"]
        if any(re.search(p, content) for p in fact_patterns):
            return 0.8

        # 疑问（携带查询意图）
        if re.search(r"[?？]", content):
            return 0.6

        # 致谢/礼貌
        polite_patterns = ["谢谢", "感谢", "辛苦了", "麻烦", "请"]
        if any(s in content for s in polite_patterns):
            return 0.2

        # 默认中等价值
        return 0.5

    def _is_noise(self, content: str) -> bool:
        """检测噪音"""
        noise_patterns = [
            r"^[嗯哦啊哈嘿]+$",
            r"^(好的|是的|对|行|可以|ok|OK|yes|Yes)$",
            r"^(谢谢|多谢)$",
            r"^[.。，,！!？?~～]+$",
        ]
        for p in noise_patterns:
            if re.match(p, content, re.IGNORECASE):
                return True
        if len(content) < 2:
            return True
        return False

    # ---- BaseMemory 接口 ----
    def add(self, content: str, metadata: Optional[Dict[str, Any]] = None) -> None:
        meta = metadata or {}
        role = meta.get("role", "user")
        topic = meta.get("topic", "")
        self.add_message(role, content, topic)

    def add_message(self, role: str, content: str, topic: str = "") -> None:
        segment = self._get_or_create_current_segment(topic)
        segment.add_message(role, content)
        # 单段超 Token 限制时立即结束
        if segment.token_estimate() > self._max_tokens_per_segment:
            self._finalize_current_segment()

    def get(self, limit: int = 10) -> List[MemoryEntry]:
        """获取最近的记忆条目（扁平化所有段）"""
        self._finalize_current_segment()
        all_messages = []
        for seg in self._segments:
            for msg in seg.get_messages():
                all_messages.append((seg, msg))
        # 加上当前段
        if self._current_segment:
            for msg in self._current_segment.get_messages():
                all_messages.append((self._current_segment, msg))
        # 取最近 limit 条
        all_messages = all_messages[-limit:]
        return [
            MemoryEntry(
                content=m["content"],
                timestamp=datetime.fromisoformat(m["timestamp"]) if "timestamp" in m else datetime.now(),
                metadata={"role": m["role"], "segment_id": s.segment_id, "topic": s.topic}
            )
            for s, m in all_messages
        ]

    def get_recent(self, limit: int = 5) -> List[MemoryEntry]:
        return self.get(limit)

    def get_conversation_history(self) -> List[Dict[str, str]]:
        """获取 OpenAI 格式的对话历史"""
        return [
            {"role": e.metadata.get("role", "user"), "content": e.content}
            for e in self.get(limit=100)
        ]

    def get_segments(self) -> List[SessionSegment]:
        """获取所有已结束的段（含当前段）"""
        self._finalize_current_segment()
        return list(self._segments) + ([self._current_segment] if self._current_segment else [])

    def force_finalize(self) -> List[SessionSegment]:
        """强制结束当前段，返回所有最终段列表"""
        self._finalize_current_segment()
        return list(self._segments)

    def clear(self) -> None:
        self._segments.clear()
        self._current_segment = None

    def size(self) -> int:
        """消息总数"""
        return sum(s.message_count() for s in self._segments) + (
            self._current_segment.message_count() if self._current_segment else 0
        )

    def segment_count(self) -> int:
        return len(self._segments) + (1 if self._current_segment else 0)

    def estimate_tokens(self) -> int:
        total = sum(s.token_estimate() for s in self._segments)
        if self._current_segment:
            total += self._current_segment.token_estimate()
        return total

    def to_context(self) -> str:
        self._finalize_current_segment()
        if not self._segments and not self._current_segment:
            return ""
        lines = []
        all_segs = list(self._segments)
        if self._current_segment:
            all_segs.append(self._current_segment)
        for seg in all_segs:
            topic_str = f" [{seg.topic}]" if seg.topic else ""
            lines.append(f"--- 会话段 #{seg.segment_id}{topic_str} ---")
            for msg in seg.get_messages():
                role = msg.get("role", "user")
                lines.append(f"{role}: {msg['content']}")
        return "\n".join(lines)
