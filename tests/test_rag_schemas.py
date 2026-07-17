"""RAG统一数据模型与异常体系的核心测试。"""

import pytest
from pydantic import ValidationError

from agent_core.schemas import Subsystem
from rag.exceptions import EmptyDocumentError
from rag.schemas import (
    DocumentRecord,
    DocumentType,
    RAGAnswer,
    RAGCitation,
)


def make_document() -> DocumentRecord:
    """构造测试使用的标准文档。"""

    return DocumentRecord(
        document_id="battery_voltage_inconsistency",
        title="动力电池单体电压不一致问题",
        content="单体电压不一致可能与容量、内阻及连接状态差异有关。",
        source_path="docs/knowledge_base/battery/"
        "battery_voltage_inconsistency.md",
        file_type=DocumentType.MARKDOWN,
        subsystem=Subsystem.BATTERY,
        topic="voltage_inconsistency",
    )


# 正向用例，覆盖完整数据流：DocumentRecord->RAGCitation->RAGAnswer
def test_rag_models_accept_valid_data() -> None:
    """合法文档和带引用的RAG回答应通过校验。"""

    document = make_document()

    citation = RAGCitation(
        chunk_id="battery_voltage_0001",
        document_id=document.document_id,
        title=document.title,
        section_path="可能原因",
        supported_claim="单体差异可能导致电压一致性风险。",
        evidence_text="容量、内阻及连接状态差异可能引起电压不一致。",
    )

    answer = RAGAnswer(
        question="单体压差为什么会扩大？",
        answer="现有证据表明，应优先检查容量、内阻和连接状态差异。",
        citations=[citation],
        confidence=0.82,
        sufficient_evidence=True,
        missing_information=["缺少各单体历史电压和内阻数据"],
        needs_human_review=True,
    )

    assert document.subsystem == Subsystem.BATTERY
    assert answer.citations[0].chunk_id == "battery_voltage_0001"


def test_rag_models_reject_unknown_fields() -> None:
    """RAG模型应拒绝未声明的额外字段。"""

    with pytest.raises(ValidationError):
        DocumentRecord(
            document_id="battery_test",
            title="测试文档",
            content="测试正文",
            source_path="docs/test.md",
            file_type=DocumentType.MARKDOWN,
            unexpected_field="不允许的字段",
        )


def test_sufficient_answer_requires_citation() -> None:
    """证据充分的回答必须至少包含一条可追溯引用。"""

    with pytest.raises(ValidationError):
        RAGAnswer(
            question="什么是电池热失控？",
            answer="这是一个测试回答。",
            citations=[],
            confidence=0.8,
            sufficient_evidence=True,
            missing_information=[],
            needs_human_review=False,
        )


def test_rag_exception_contains_stable_context() -> None:
    """RAG异常应包含稳定错误码和排错上下文。"""

    error = EmptyDocumentError(
        "文档没有有效正文",
        component="document_loader",
        document_id="battery_test",
    )

    assert error.code == "empty_document"
    assert "component=document_loader" in str(error)
    assert "document_id=battery_test" in str(error)