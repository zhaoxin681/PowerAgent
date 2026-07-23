"""知识上传、检索和删除闭环测试。"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.document_service import (
    DocumentIngestionService,
)
from rag.document_loader import DocumentLoader
from rag.embeddings import (
    HashEmbeddingProvider,
)
from rag.rag_pipeline import RAGPipeline
from rag.retriever import Retriever
from rag.schemas import (
    RAGAnswer,
    RAGCitation,
)
from rag.text_splitter import TextSplitter
from rag.vector_store import ChromaVectorStore


class EvidenceEchoLLM:
    """使用检索结果生成固定证据回答。"""

    def __init__(self) -> None:
        self.call_count = 0

    def parse_structured(
        self,
        *,
        developer_prompt: str,
        user_input: str,
        response_model: type[RAGAnswer],
    ) -> RAGAnswer:
        """引用本次检索结果中的第一条知识块。"""

        self.call_count += 1

        assert developer_prompt.strip()
        assert response_model is RAGAnswer

        evidence_text = (
            user_input
            .split(
                "EVIDENCE_JSON_START",
                maxsplit=1,
            )[1]
            .split(
                "EVIDENCE_JSON_END",
                maxsplit=1,
            )[0]
            .strip()
        )

        records: list[dict[str, Any]] = (
            json.loads(evidence_text)
        )

        first = records[0]

        return RAGAnswer(
            question="测试问题",
            answer=(
                "高SOC快充限流需要同时检查"
                "最高温度和单体电压约束。"
            ),
            citations=[
                RAGCitation(
                    chunk_id=first["chunk_id"],
                    document_id="untrusted_id",
                    title="untrusted_title",
                    section_path="",
                    page_number=None,
                    supported_claim=(
                        "高SOC限流与温度及"
                        "单体电压约束有关"
                    ),
                    evidence_text=first["content"],
                )
            ],
            confidence=0.9,
            sufficient_evidence=True,
            missing_information=[],
            needs_human_review=False,
        )


def test_document_ingestion_rag_and_delete_loop(
    tmp_path: Path,
) -> None:
    """新文档应可检索，删除后应无法继续检索。"""

    embedding_provider = (
        HashEmbeddingProvider(
            dimension=256,
        )
    )

    vector_store = ChromaVectorStore(
        persist_directory=(
            tmp_path / "chroma"
        ),
        embedding_provider=(
            embedding_provider
        ),
        collection_name=(
            "knowledge_closed_loop"
        ),
    )

    document_service = (
        DocumentIngestionService(
            loader=DocumentLoader(
                source_root=tmp_path
            ),
            splitter=TextSplitter(
                chunk_size=200,
                chunk_overlap=20,
            ),
            vector_store=vector_store,
        )
    )

    knowledge_file = (
        tmp_path / "charging_limit.txt"
    )

    knowledge_file.write_text(
        (
            "高SOC快充阶段出现充电限流时，"
            "应同时检查最高温度、单体电压上限、"
            "单体压差和热管理冷却能力。"
        ),
        encoding="utf-8",
    )

    ingestion_result = (
        document_service.ingest_file(
            knowledge_file,
            original_filename=(
                "charging_limit.txt"
            ),
            topic="高SOC快充限流",
        )
    )

    assert (
        ingestion_result.upserted_count
        >= 1
    )
    assert vector_store.count() >= 1

    fake_llm = EvidenceEchoLLM()

    pipeline = RAGPipeline(
        retriever=Retriever(
            vector_store=vector_store
        ),
        llm_client=fake_llm,
    )

    answer = pipeline.answer(
        "高SOC快充限流需要检查什么？",
        top_k=2,
        min_score=0.0,
    )

    assert answer.sufficient_evidence is True
    assert len(answer.citations) == 1
    assert (
        answer.citations[0].document_id
        == "charging_limit"
    )
    assert fake_llm.call_count == 1

    deletion_result = (
        document_service.delete_document(
            "charging_limit"
        )
    )

    assert deletion_result.deleted is True
    assert (
        deletion_result.deleted_chunk_count
        >= 1
    )
    assert vector_store.count() == 0

    answer_after_delete = pipeline.answer(
        "高SOC快充限流需要检查什么？",
        top_k=2,
        min_score=0.0,
    )

    assert (
        answer_after_delete
        .sufficient_evidence
        is False
    )
    assert (
        answer_after_delete.citations
        == []
    )

    # 没有检索证据时RAGPipeline确定性拒答，
    # 不再调用LLM。
    assert fake_llm.call_count == 1