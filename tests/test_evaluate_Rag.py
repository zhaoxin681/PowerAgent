"""RAG自动评测核心逻辑测试。"""

from agent_core.schemas import Subsystem
from evaluation.evaluate_rag import (
    evaluate_answer,
    evaluate_retrieval,
)
from evaluation.schemas import (
    RAGExpectation,
)
from rag.schemas import (
    RAGAnswer,
    RAGCitation,
    RetrievedChunk,
)


def make_chunk() -> RetrievedChunk:
    """构造RAG评测使用的真实检索块。"""

    return RetrievedChunk(
        chunk_id=(
            "battery_internal_short_circuit:"
            "test"
        ),
        document_id=(
            "battery_internal_short_circuit"
        ),
        title="锂离子电池内短路候选诊断",
        content=(
            "内短路早期通常需要多源数据联合判断，"
            "不能仅依据单一阈值直接确认。"
        ),
        score=0.9,
        rank=1,
        source_path=(
            "battery/"
            "battery_internal_short_circuit.md"
        ),
        section_path="适用边界",
        subsystem=Subsystem.BATTERY,
        topic="internal_short_circuit",
        metadata={},
    )

def test_evaluate_retrieval_document_hit() -> None:
    """正确文档位于第一名时MRR应为1。"""

    expected = RAGExpectation(
        should_answer=True,
        should_refuse=False,
        expected_document_ids=[
            "battery_internal_short_circuit",
        ],
        expected_sufficient_evidence=True,
    )

    checks, counts = evaluate_retrieval(
        expected,
        [make_chunk()],
    )

    assert checks[
        "document_hit_at_k"
    ]["passed"]

    assert (
        counts["reciprocal_rank_sum"]
        == 1.0
    )



def test_evaluate_answer_accepts_valid_evidence() -> None:
    """合法引用和关键概念应全部通过。"""

    chunk = make_chunk()

    expected = RAGExpectation(
        should_answer=True,
        should_refuse=False,
        expected_document_ids=[
            "battery_internal_short_circuit",
        ],
        expected_sufficient_evidence=True,
        min_citation_count=1,
        required_answer_concepts=[
            [
                "多源数据联合判断",
            ],
            [
                "不能仅依据单一阈值",
            ],
        ],
    )

    answer = RAGAnswer(
        question="如何确认内短路？",
        answer=(
            "内短路通常需要多源数据联合判断，"
            "不能仅依据单一阈值确认。"
        ),
        citations=[
            RAGCitation(
                chunk_id=chunk.chunk_id,
                document_id=(
                    chunk.document_id
                ),
                title=chunk.title,
                section_path=(
                    chunk.section_path
                ),
                supported_claim=(
                    "内短路需要多源判断。"
                ),
                evidence_text=(
                    "内短路早期通常需要"
                    "多源数据联合判断"
                ),
            )
        ],
        confidence=0.9,
        sufficient_evidence=True,
        missing_information=[],
        needs_human_review=True,
    )

    checks, _ = evaluate_answer(
        expected,
        answer,
        [chunk],
        original_question=(
            "如何确认内短路？"
        ),
    )

    assert checks[
        "answer_overall"
    ]["passed"]



def test_evaluate_answer_rejects_forbidden_claim() -> None:
    """拒答样本不能生成无证据固定阈值。"""

    chunk = make_chunk()

    expected = RAGExpectation(
        should_answer=False,
        should_refuse=True,
        expected_document_ids=[
            "battery_internal_short_circuit",
        ],
        expected_sufficient_evidence=False,
        min_citation_count=1,
        forbidden_claims=[
            "统一阈值为5.1kΩ",
        ],
    )

    answer = RAGAnswer(
        question="统一阈值是多少？",
        answer=(
            "统一阈值为5.1kΩ。"
        ),
        citations=[
            RAGCitation(
                chunk_id=chunk.chunk_id,
                document_id=(
                    chunk.document_id
                ),
                title=chunk.title,
                section_path=(
                    chunk.section_path
                ),
                supported_claim="测试结论",
                evidence_text=(
                    "不能仅依据单一阈值"
                ),
            )
        ],
        confidence=0.2,
        sufficient_evidence=False,
        missing_information=[
            "缺少企业规范",
        ],
        needs_human_review=True,
    )

    checks, _ = evaluate_answer(
        expected,
        answer,
        [chunk],
        original_question=(
            "统一阈值是多少？"
        ),
    )

    assert not checks[
        "forbidden_claims"
    ]["passed"]

    assert not checks[
        "answer_overall"
    ]["passed"]