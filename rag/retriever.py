"""PowerAgent动力系统知识检索器。连接底层向量库和上层问答生成之间的业务层"""

from __future__ import annotations

import hashlib
import logging
import re
from dataclasses import dataclass
from typing import Any, Protocol

from agent_core.logging_config import get_logger
from agent_core.schemas import Subsystem
from rag.exceptions import RetrievalError
from rag.schemas import RetrievedChunk


class VectorStoreProtocol(Protocol):
    """Retriever依赖的最小向量库接口。"""

    def search(
        self,
        *,
        query: str,
        top_k: int = 5,
        filters: dict[str, Any] | None = None,
    ) -> list[RetrievedChunk]:
        """检索相关知识块。"""


@dataclass(frozen=True)
class RetrieverConfig:
    """动力系统知识检索配置。"""

    default_top_k: int = 4
    max_top_k: int = 10
    candidate_multiplier: int = 3
    default_min_score: float = 0.25

    def __post_init__(self) -> None:
        if self.default_top_k < 1:
            raise ValueError(
                "default_top_k必须大于0"
            )

        if self.max_top_k < self.default_top_k:
            raise ValueError(
                "max_top_k不能小于default_top_k"
            )

        if self.candidate_multiplier < 1:
            raise ValueError(
                "candidate_multiplier必须大于0"
            )

        if not 0.0 <= self.default_min_score <= 1.0:
            raise ValueError(
                "default_min_score必须位于0到1之间"
            )


class Retriever:
    """封装向量检索、元数据过滤和结果整理。"""

    def __init__(
        self,
        *,
        vector_store: VectorStoreProtocol,
        config: RetrieverConfig | None = None,
        logger: logging.Logger | None = None,
    ) -> None:
        self.vector_store = vector_store
        self.config = config or RetrieverConfig()
        self._logger = logger or get_logger(
            "rag.retriever"
        )

    # 参数检索
    def retrieve(
        self,
        query: str,
        *,
        top_k: int | None = None,
        subsystem: Subsystem | str | None = None,
        topic: str | None = None,
        min_score: float | None = None,
    ) -> list[RetrievedChunk]:
        """检索并返回满足业务约束的知识块。"""

        normalized_query = query.strip()

        if not normalized_query:
            raise ValueError("query不能为空")

        resolved_top_k = (
            top_k
            if top_k is not None
            else self.config.default_top_k
        )

        if not 1 <= resolved_top_k <= self.config.max_top_k:
            raise ValueError(
                "top_k必须位于1到"
                f"{self.config.max_top_k}之间"
            )

        resolved_min_score = (
            min_score
            if min_score is not None
            else self.config.default_min_score
        )

        if not 0.0 <= resolved_min_score <= 1.0:
            raise ValueError(
                "min_score必须位于0到1之间"
            )

        resolved_subsystem = self._resolve_subsystem(
            subsystem
        )
        normalized_topic = (
            topic.strip()
            if isinstance(topic, str) and topic.strip()
            else None
        )

        filters = self._build_filters(
            subsystem=resolved_subsystem,
            topic=normalized_topic,
        )

        candidate_count = min(
            self.config.max_top_k
            * self.config.candidate_multiplier,
            resolved_top_k
            * self.config.candidate_multiplier,
        )

        query_fingerprint = hashlib.sha256(
            normalized_query.encode("utf-8")
        ).hexdigest()[:12]  # 查询指纹

        self._logger.info(
            "开始检索动力系统知识。",
            extra={
                "event": "rag_retrieval_started",
                "query_chars": len(normalized_query),
                "query_fingerprint": query_fingerprint,
                "requested_top_k": resolved_top_k,
                "candidate_count": candidate_count,
                "min_score": resolved_min_score,
                "subsystem": (
                    resolved_subsystem.value
                    if resolved_subsystem is not None
                    else None
                ),
                "topic": normalized_topic,
            },
        )

        try:
            candidates = self.vector_store.search(
                query=normalized_query,
                top_k=candidate_count,
                filters=filters,
            )

            selected = self._filter_candidates(
                candidates=candidates,
                subsystem=resolved_subsystem,
                topic=normalized_topic,
                min_score=resolved_min_score,
                top_k=resolved_top_k,
            )

            self._logger.info(
                "动力系统知识检索完成。",
                extra={
                    "event": "rag_retrieval_succeeded",
                    "query_fingerprint": query_fingerprint,
                    "candidate_count": len(candidates),
                    "result_count": len(selected),
                    "top_score": (
                        selected[0].score
                        if selected
                        else None
                    ),
                },
            )

            return selected

        except RetrievalError:
            raise
        except Exception as exc:
            self._logger.error(
                "动力系统知识检索失败。",
                extra={
                    "event": "rag_retrieval_failed",
                    "query_fingerprint": query_fingerprint,
                    "error_type": type(exc).__name__,
                },
            )

            raise RetrievalError(
                (
                    "知识检索失败："
                    f"{type(exc).__name__}: {exc}"
                ),
                component="retriever",
            ) from exc

    # 候选结果精细过滤
    def _filter_candidates(
        self,
        *,
        candidates: list[RetrievedChunk],
        subsystem: Subsystem | None,
        topic: str | None,
        min_score: float,
        top_k: int,
    ) -> list[RetrievedChunk]:
        """过滤低分、重复和元数据不匹配结果。"""

        selected: list[RetrievedChunk] = []
        seen_chunk_ids: set[str] = set()
        seen_content_keys: set[tuple[str, str, str]] = (
            set()
        )

        for candidate in candidates:
            # 分数阈值
            if candidate.score < min_score:
                continue
            # 子系统精准匹配
            if (
                subsystem is not None
                and subsystem != Subsystem.UNKNOWN
                and candidate.subsystem != subsystem
            ):
                continue
            # 主题精准匹配
            if (
                topic is not None
                and candidate.topic != topic
            ):
                continue
            # 按chunk_id去重
            if candidate.chunk_id in seen_chunk_ids:
                continue
            # 按内容语义去重
            content_key = (
                candidate.document_id,
                candidate.section_path,
                self._normalize_content(
                    candidate.content
                ),
            )
            if content_key in seen_content_keys:
                continue

            seen_chunk_ids.add(candidate.chunk_id)
            seen_content_keys.add(content_key)
            selected.append(candidate)

            if len(selected) >= top_k:
                break

        return [
            RetrievedChunk.model_validate(
                {
                    **candidate.model_dump(),
                    "rank": rank,
                }
            )
            for rank, candidate in enumerate(
                selected,
                start=1,
            )
        ]

    @staticmethod
    def _resolve_subsystem(
        subsystem: Subsystem | str | None,
    ) -> Subsystem | None:
        """将字符串转换为统一子系统枚举。"""

        if subsystem is None:
            return None

        if isinstance(subsystem, Subsystem):
            return subsystem

        normalized_value = subsystem.strip()

        if not normalized_value:
            return None

        try:
            return Subsystem(normalized_value)
        except ValueError as exc:
            raise ValueError(
                f"未知动力系统子系统：{subsystem}"
            ) from exc

    @staticmethod
    def _build_filters(
        *,
        subsystem: Subsystem | None,
        topic: str | None,
    ) -> dict[str, Any] | None:
        """构建Chroma元数据过滤条件。"""

        conditions: list[dict[str, Any]] = []

        if (
            subsystem is not None
            and subsystem != Subsystem.UNKNOWN
        ):
            conditions.append(
                {
                    "subsystem": subsystem.value,
                }
            )

        if topic is not None:
            conditions.append(
                {
                    "topic": topic,
                }
            )

        if not conditions:
            return None

        if len(conditions) == 1:
            return conditions[0]

        return {
            "$and": conditions,
        }

    @staticmethod
    def _normalize_content(text: str) -> str:
        """生成用于精确去重的文本形式。"""

        return re.sub(
            r"\s+",
            "",
            text.strip().lower(),
        )