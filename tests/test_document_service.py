"""PowerAgent知识文档入库服务核心测试。"""

from pathlib import Path

import pytest

from app.document_service import (
    DocumentIngestionService,
    DuplicateDocumentError,
)
from rag.document_loader import DocumentLoader
from rag.embeddings import (
    HashEmbeddingProvider,
)
from rag.text_splitter import TextSplitter
from rag.vector_store import ChromaVectorStore


def make_service(
    tmp_path: Path,
) -> DocumentIngestionService:
    """创建隔离的本地知识库服务。"""

    vector_store = ChromaVectorStore(
        persist_directory=(
            tmp_path / "chroma"
        ),
        embedding_provider=(
            HashEmbeddingProvider(
                dimension=256
            )
        ),
        collection_name=(
            "document_service_test"
        ),
    )

    return DocumentIngestionService(
        loader=DocumentLoader(
            source_root=tmp_path
        ),
        splitter=TextSplitter(
            chunk_size=100,
            chunk_overlap=20,
        ),
        vector_store=vector_store,
    )


def test_document_service_indexes_text_file(
    tmp_path: Path,
) -> None:
    """TXT文档应完成加载、切分和入库。"""

    file_path = (
        tmp_path / "battery_note.txt"
    )

    file_path.write_text(
        (
            "动力电池单体压差扩大可能与"
            "电芯一致性、采样误差或连接阻抗有关。"
            "应结合静置电压、温度和历史趋势"
            "进行进一步复核。"
        ),
        encoding="utf-8",
    )

    service = make_service(tmp_path)

    result = service.ingest_file(
        file_path,
        original_filename=(
            "../battery_note.txt"
        ),
        topic="电池一致性",
    )

    assert (
        result.document_id
        == "battery_note"
    )
    assert (
        result.filename
        == "battery_note.txt"
    )
    assert result.chunk_count >= 1
    assert (
        result.upserted_count
        == result.chunk_count
    )
    assert result.updated is False
    assert (
        service.vector_store.count()
        == result.chunk_count
    )


def test_document_service_controls_overwrite(
    tmp_path: Path,
) -> None:
    """重复文档必须显式允许覆盖。"""

    file_path = (
        tmp_path / "charging_rule.txt"
    )

    file_path.write_text(
        "高温快充时应监测最高温度。",
        encoding="utf-8",
    )

    service = make_service(tmp_path)

    service.ingest_file(
        file_path,
        original_filename=(
            "charging_rule.txt"
        ),
    )

    with pytest.raises(
        DuplicateDocumentError
    ):
        service.ingest_file(
            file_path,
            original_filename=(
                "charging_rule.txt"
            ),
        )

    file_path.write_text(
        (
            "高温快充时应同时监测最高温度、"
            "单体电压和充电电流。"
        ),
        encoding="utf-8",
    )

    updated_result = service.ingest_file(
        file_path,
        original_filename=(
            "charging_rule.txt"
        ),
        overwrite=True,
    )

    assert updated_result.updated is True