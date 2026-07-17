"""ChromaVectorStore核心行为测试。"""

from pathlib import Path

from agent_core.schemas import Subsystem
from rag.embeddings import HashEmbeddingProvider
from rag.schemas import (
    DocumentChunk,
    DocumentType,
)
from rag.vector_store import ChromaVectorStore


def make_chunk(
    *,
    chunk_id: str,
    document_id: str,
    content: str,
    subsystem: Subsystem,
    topic: str,
) -> DocumentChunk:
    """构造向量库测试知识块。"""

    return DocumentChunk(
        chunk_id=chunk_id,
        document_id=document_id,
        title=document_id,
        content=content,
        chunk_index=0,
        source_path=f"docs/{document_id}.md",
        file_type=DocumentType.MARKDOWN,
        section_path="测试章节",
        subsystem=subsystem,
        topic=topic,
        metadata={
            "source_type": "test",
        },
    )


def create_store(
    tmp_path: Path,
) -> ChromaVectorStore:
    """创建使用临时目录的测试向量库。"""

    return ChromaVectorStore(
        persist_directory=tmp_path / "chroma",
        embedding_provider=(
            HashEmbeddingProvider(
                dimension=128
            )
        ),
        collection_name="test_knowledge",
    )


def test_vector_store_upserts_and_searches(
    tmp_path: Path,
) -> None:
    """知识块应可重复写入并按内容检索。"""

    store = create_store(tmp_path)

    chunks = [
        make_chunk(
            chunk_id="battery:001",
            document_id="battery_voltage",
            content=(
                "单体电压压差扩大可能与容量和内阻差异有关。"
            ),
            subsystem=Subsystem.BATTERY,
            topic="voltage",
        ),
        make_chunk(
            chunk_id="thermal:001",
            document_id="thermal_fault",
            content=(
                "温度异常需要检查冷却液、泵和风扇状态。"
            ),
            subsystem=Subsystem.THERMAL,
            topic="thermal",
        ),
    ]

    assert store.add_chunks(chunks) == 2
    assert store.count() == 2

    # 重复upsert不应产生重复记录。
    assert store.add_chunks(chunks) == 2
    assert store.count() == 2

    results = store.search(
        query="单体电压压差异常",
        top_k=1,
    )

    assert len(results) == 1
    assert (
        results[0].document_id
        == "battery_voltage"
    )


def test_vector_store_supports_metadata_filter(
    tmp_path: Path,
) -> None:
    """子系统元数据过滤应排除其他知识块。"""

    store = create_store(tmp_path)

    store.add_chunks(
        [
            make_chunk(
                chunk_id="battery:001",
                document_id="battery_voltage",
                content="电池单体电压异常。",
                subsystem=Subsystem.BATTERY,
                topic="voltage",
            ),
            make_chunk(
                chunk_id="thermal:001",
                document_id="thermal_fault",
                content="热管理冷却异常。",
                subsystem=Subsystem.THERMAL,
                topic="thermal",
            ),
        ]
    )

    results = store.search(
        query="异常分析",
        top_k=5,
        filters={
            "subsystem": "thermal",
        },
    )

    assert len(results) == 1
    assert (
        results[0].subsystem
        == Subsystem.THERMAL
    )