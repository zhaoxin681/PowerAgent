"""RAGPipeline核心行为测试。包括引用重建、无证据据答、拒绝虚假引用"""

from typing import Any

import pytest

from agent_core.schemas import Subsystem
from rag.exceptions import (
    CitationValidationError,
)
from rag.rag_pipeline import RAGPipeline
from rag.schemas import (
    RAGAnswer,
    RAGCitation,
    RetrievedChunk,
)


class FakeRetriever:
    """返回预设证据的测试Retriever。"""

    def __init__(
        self,
        results: list[RetrievedChunk],
    ) -> None:
        self.results = results

    def retrieve(
        self,
        query: str,
        **kwargs: Any,
    ) -> list[RetrievedChunk]:
        return self.results


class FakeLLMClient:
    """返回预设结构化回答的测试LLM客户端。"""

    def __init__(
        self,
        answer: RAGAnswer,
    ) -> None:
        self.answer = answer
        self.call_count = 0

    def parse_structured(
        self,
        *,
        developer_prompt: str,
        user_input: str,
        response_model: type[RAGAnswer],
    ) -> RAGAnswer:
        self.call_count += 1
        return self.answer


def make_retrieved_chunk() -> RetrievedChunk:
    """构造真实检索证据。"""

    return RetrievedChunk(
        chunk_id="battery_voltage:001",
        document_id="battery_voltage",
        title="动力电池单体电压不一致问题",
        content=(
            "单体压差扩大可能与容量、"
            "内阻和连接状态差异有关。"
        ),
        score=0.91,
        rank=1,
        source_path=(
            "docs/knowledge_base/battery/"
            "battery_voltage.md"
        ),
        section_path="可能原因",
        subsystem=Subsystem.BATTERY,
        topic="voltage",
        metadata={},
    )


def test_pipeline_rebuilds_citation_from_real_evidence() -> None:
    """引用来源必须以真实Retriever结果为准。"""

    retrieved_chunk = make_retrieved_chunk()

    generated_answer = RAGAnswer(
        question="模型可能改写的问题",
        answer=(
            "应优先检查容量、内阻和连接状态差异。"
        ),
        citations=[
            RAGCitation(
                chunk_id="battery_voltage:001",
                document_id="模型虚构的文档ID",
                title="模型虚构的标题",
                section_path="错误章节",
                supported_claim=(
                    "压差扩大可能与单体差异有关。"
                ),
                evidence_text=(
                    "单体压差扩大可能与容量、"
                    "内阻和连接状态差异有关。"
                ),
            )
        ],
        confidence=0.88,
        sufficient_evidence=True,
        missing_information=[],
        needs_human_review=True,
    )

    fake_llm = FakeLLMClient(
        generated_answer
    )

    pipeline = RAGPipeline(
        retriever=FakeRetriever(
            [retrieved_chunk]
        ),
        llm_client=fake_llm,
    )

    result = pipeline.answer(
        "为什么动力电池单体压差会扩大？"
    )

    citation = result.citations[0]

    assert result.question == (
        "为什么动力电池单体压差会扩大？"
    )
    assert citation.document_id == (
        retrieved_chunk.document_id
    )
    assert citation.title == retrieved_chunk.title
    assert citation.section_path == (
        retrieved_chunk.section_path
    )
    assert fake_llm.call_count == 1


def test_pipeline_does_not_call_llm_without_evidence() -> None:
    """无证据时应直接返回受控拒答。"""

    unused_answer = RAGAnswer(
        question="测试",
        answer="不会被使用",
        citations=[],
        confidence=0.0,
        sufficient_evidence=False,
        missing_information=[],
        needs_human_review=True,
    )

    fake_llm = FakeLLMClient(unused_answer)

    pipeline = RAGPipeline(
        retriever=FakeRetriever([]),
        llm_client=fake_llm,
    )

    result = pipeline.answer(
        "知识库中不存在的问题"
    )

    assert result.sufficient_evidence is False
    assert result.citations == []
    assert result.confidence == 0.0
    assert fake_llm.call_count == 0


def test_pipeline_rejects_unknown_citation() -> None:
    """模型引用不存在的Chunk时必须失败。"""

    generated_answer = RAGAnswer(
        question="测试问题",
        answer="测试回答",
        citations=[
            RAGCitation(
                chunk_id="unknown:999",
                document_id="unknown",
                title="未知文档",
                supported_claim="测试结论",
                evidence_text="测试证据",
            )
        ],
        confidence=0.8,
        sufficient_evidence=True,
        missing_information=[],
        needs_human_review=False,
    )

    pipeline = RAGPipeline(
        retriever=FakeRetriever(
            [make_retrieved_chunk()]
        ),
        llm_client=FakeLLMClient(
            generated_answer
        ),
    )

    with pytest.raises(
        CitationValidationError
    ):
        pipeline.answer("测试问题")