"""
记忆压缩器（Memory Compressor）

核心职责：对进入长期记忆的内容做"准入 + 合并 + 覆盖"决策
  - SKIP     : 噪音消息，不入库
  - MERGE    : 与已有记忆合并去重
  - REPLACE  : 覆盖旧记忆（如偏好变更）
  - APPEND   : 追加为新记忆

工程关注点：
  - LLM 合并效果好但慢/贵，本实现用规则+相似度做轻量版
  - 噪音识别不能太激进，避免误删有效短消息
  - 合并/覆盖决策要可追溯
"""
from typing import Dict, Any, List, Optional, Tuple
from enum import Enum
from dataclasses import dataclass
import re
from .vector_memory import VectorMemory


class CompressAction(Enum):
    SKIP = "skip"        # 噪音，不入库
    MERGE = "merge"      # 与已有记忆合并
    REPLACE = "replace"  # 覆盖旧记忆
    APPEND = "append"    # 追加为新记忆


@dataclass
class CompressResult:
    action: CompressAction
    final_content: Optional[str] = None  # 处理后的内容（SKIP 时为 None）
    target_index: Optional[int] = None    # 合并/覆盖的目标条目索引
    reason: str = ""                     # 决策原因


class MemoryCompressor:
    """长期记忆压缩器"""

    # 噪音模式：太短、纯语气词、纯标点
    NOISE_PATTERNS = [
        r"^[嗯哦啊哈嘿]+$",
        r"^(好的|是的|对|行|可以|ok|OK|yes|Yes|No|no)$",
        r"^(谢谢|多谢|感谢|thank|thanks)$",
        r"^[.。，,！!？?~～]+$",
        r"^(哈哈|呵呵|嘿嘿|嘻嘻)+$",
    ]

    # 明确信号词
    REPLACE_SIGNALS = [
        "改吃", "改用", "改成", "换成", "不喜欢", "不爱",
        "其实", "实际上", "更正", "修正", "改为", "不再是",
        "changed to", "instead of", "no longer", "actually",
    ]

    def __init__(self, similarity_threshold: float = 0.6, min_length: int = 4):
        self.similarity_threshold = similarity_threshold
        self.min_length = min_length
        # 用于相似度比较
        self._vector_helper = VectorMemory()

    def compress(
        self,
        new_content: str,
        existing_memories: List[Tuple[int, str]]  # (index, content) 列表
    ) -> CompressResult:
        """
        对新记忆做压缩决策

        参数：
          new_content      : 待入库的新记忆
          existing_memories: 已有的长期记忆列表 [(index, content), ...]

        返回：CompressResult
        """
        content = new_content.strip()

        # 1. 噪音检测
        if self._is_noise(content):
            return CompressResult(
                action=CompressAction.SKIP,
                reason=f"噪音内容: 长度={len(content)}, 模式匹配"
            )

        # 2. 内容太短
        if len(content) < self.min_length:
            return CompressResult(
                action=CompressAction.SKIP,
                reason=f"内容过短: {len(content)} < {self.min_length}"
            )

        # 3. 检测覆盖信号
        for idx, existing in existing_memories:
            if self._has_replace_signal(content, existing):
                return CompressResult(
                    action=CompressAction.REPLACE,
                    final_content=content,
                    target_index=idx,
                    reason=f"检测到覆盖信号，覆盖索引 {idx}"
                )

        # 4. 相似度合并检测
        for idx, existing in existing_memories:
            sim = self._compute_similarity(content, existing)
            if sim >= self.similarity_threshold:
                merged = self._merge_contents(content, existing)
                return CompressResult(
                    action=CompressAction.MERGE,
                    final_content=merged,
                    target_index=idx,
                    reason=f"与索引 {idx} 相似度 {sim:.2f} >= {self.similarity_threshold}, 合并"
                )

        # 5. 默认追加
        return CompressResult(
            action=CompressAction.APPEND,
            final_content=content,
            reason="新记忆，直接追加"
        )

    def _is_noise(self, content: str) -> bool:
        """检测是否噪音"""
        for pattern in self.NOISE_PATTERNS:
            if re.match(pattern, content, re.IGNORECASE):
                return True
        # 全是空白或标点
        if not re.search(r'[\w\u4e00-\u9fa5]', content):
            return True
        return False

    def _has_replace_signal(self, new: str, existing: str) -> bool:
        """检测是否有"覆盖旧记忆"的信号"""
        for signal in self.REPLACE_SIGNALS:
            if signal in new:
                # 进一步检查是否在描述同一主题（关键词重叠）
                new_words = set(self._vector_helper._tokenize(new))
                existing_words = set(self._vector_helper._tokenize(existing))
                if new_words & existing_words:
                    return True
        return False

    def _compute_similarity(self, text1: str, text2: str) -> float:
        """计算两段文本的相似度（复用 VectorMemory 的算法）"""
        vec1 = self._vector_helper._compute_vector(text1)
        vec2 = self._vector_helper._compute_vector(text2)
        cos = self._vector_helper._cosine_similarity(vec1, vec2)
        jac = self._vector_helper._jaccard_similarity(vec1, vec2)
        return 0.6 * cos + 0.4 * jac

    def _merge_contents(self, new: str, existing: str) -> str:
        """
        合并两段相似内容
        简单实现：保留较长的版本作为基础，把另一方的差异信息追加
        进阶实现：可用 LLM 合并（后续可替换）
        """
        # 完全包含
        if new in existing:
            return existing
        if existing in new:
            return new

        # 尝试模式合并 "X川菜" + "X湘菜" → "X川菜和湘菜"
        merged = self._simple_combine(new, existing)
        if merged:
            return merged

        # 退而求其次：拼接（但用 "；" 分隔，更清晰）
        if len(new) > len(existing):
            return f"{new}；{existing}"
        return f"{existing}；{new}"

    def _simple_combine(self, text1: str, text2: str) -> Optional[str]:
        """
        简单合并：检测 "X 和 Y" 模式
        例: "喜欢川菜" + "喜欢湘菜" → "喜欢川菜和湘菜"
        """
        # 寻找共同前缀
        common_prefix = ""
        for i in range(min(len(text1), len(text2))):
            if text1[i] == text2[i]:
                common_prefix += text1[i]
            else:
                break
        # 寻找共同后缀
        common_suffix = ""
        for i in range(1, min(len(text1), len(text2)) + 1):
            if text1[-i] == text2[-i]:
                common_suffix = text1[-i] + common_suffix
            else:
                break
        # 如果有共同前缀和后缀，中间用"和"连接
        if len(common_prefix) >= 2 and len(common_suffix) >= 1:
            mid1 = text1[len(common_prefix):-len(common_suffix)] if common_suffix else text1[len(common_prefix):]
            mid2 = text2[len(common_prefix):-len(common_suffix)] if common_suffix else text2[len(common_prefix):]
            if mid1 and mid2 and mid1 != mid2:
                return f"{common_prefix}{mid1}和{mid2}{common_suffix}"
        return None

    def batch_compress(self, contents: List[str]) -> List[CompressResult]:
        """批量压缩（增量式：后处理的可能与前面的合并）"""
        results = []
        existing = []  # (index, content) 累积

        for content in contents:
            result = self.compress(content, existing)
            results.append(result)
            if result.action in (CompressAction.APPEND, CompressAction.MERGE, CompressAction.REPLACE):
                if result.action == CompressAction.APPEND:
                    new_idx = len(existing)
                    existing.append((new_idx, result.final_content))
                elif result.action in (CompressAction.MERGE, CompressAction.REPLACE):
                    if result.target_index is not None and result.target_index < len(existing):
                        existing[result.target_index] = (result.target_index, result.final_content)
        return results
