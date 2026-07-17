"""Retriever核心行为测试。重点测试两组：过滤/去重/重排逻辑的重要性、参数校验的严格性"""

from typing import Any

import pytest

from agent_core.schemas import Subsystem
from rag.retriever import Retriever
from rag.schemas import RetrievedChunk


class FakeVectorStore:
    """不访问真实Chroma的测试向量库。"""

    def __init__(
        self,
        results: list[RetrievedChunk],
    ) -> None:
        self.results = results
        self.last_filters: (
            dict[str, Any] | None
        ) = None
        self.last_top_k: int | None = None

    def search(
        self,
        *,
        query: str,
        top_k: int = 5,
        filters: dict[str, Any] | None = None,
    ) -> list[RetrievedChunk]:
        self.last_filters = filters
        self.last_top_k = top_k
        return self.results


def make_result(
    *,
    chunk_id: str,
    document_id: str,
    content: str,
    score: float,
    subsystem: Subsystem,
    topic: str,
    rank: int,
) -> RetrievedChunk:
    """构造测试检索结果。"""

    return RetrievedChunk(
        chunk_id=chunk_id,
        document_id=document_id,
        title=document_id,
        content=content,
        score=score,
        rank=rank,
        source_path=f"docs/{document_id}.md",
        section_path="可能原因",
        subsystem=subsystem,
        topic=topic,
        metadata={},
    )


def test_retriever_filters_and_reranks() -> None:
    """Retriever应执行分数、元数据和重复过滤。"""

    battery_result = make_result(
        chunk_id="battery:001",
        document_id="battery_voltage",
        content="压差扩大可能与容量和内阻差异有关。",
        score=0.92,
        subsystem=Subsystem.BATTERY,
        topic="voltage",
        rank=1,
    )

    vector_store = FakeVectorStore(
        [
            battery_result,
            battery_result,
            make_result(
                chunk_id="thermal:001",
                document_id="thermal_fault",
                content="冷却系统异常。",
                score=0.88,
                subsystem=Subsystem.THERMAL,
                topic="thermal",
                rank=3,
            ),
            make_result(
                chunk_id="battery:002",
                document_id="battery_noise",
                content="低相关测试内容。",
                score=0.10,
                subsystem=Subsystem.BATTERY,
                topic="voltage",
                rank=4,
            ),
        ]
    )

    retriever = Retriever(
        vector_store=vector_store
    )

    results = retriever.retrieve(
        "为什么单体压差扩大？",
        top_k=2,
        subsystem=Subsystem.BATTERY,
        topic="voltage",
        min_score=0.5,
    )

    assert len(results) == 1
    assert results[0].chunk_id == "battery:001"
    assert results[0].rank == 1

    assert vector_store.last_filters == {
        "$and": [
            {"subsystem": "battery"},
            {"topic": "voltage"},
        ]
    }


def test_retriever_rejects_invalid_query_parameters() -> None:
    """空查询和越界Top-K应被拒绝。"""

    retriever = Retriever(
        vector_store=FakeVectorStore([])
    )

    with pytest.raises(ValueError):
        retriever.retrieve("   ")

    with pytest.raises(ValueError):
        retriever.retrieve(
            "测试问题",
            top_k=11,
        )