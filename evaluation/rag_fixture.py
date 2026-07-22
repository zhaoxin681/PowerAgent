"""PowerAgent RAG评测知识库固定构建配置。"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

from rag.document_loader import DocumentLoader
from rag.embeddings import HashEmbeddingProvider
from rag.retriever import Retriever
from rag.schemas import (
    DocumentChunk,
    DocumentRecord,
)
from rag.text_splitter import TextSplitter
from rag.vector_store import ChromaVectorStore


PROJECT_ROOT = Path(__file__).resolve().parents[1]

KNOWLEDGE_BASE_ROOT = (
    PROJECT_ROOT
    / "docs"
    / "knowledge_base"
)

RAG_EVAL_PERSIST_DIRECTORY = (
    PROJECT_ROOT
    / "data"
    / "evaluation"
    / "rag_chroma_hash"
)

RAG_EVAL_COLLECTION_NAME = (
    "poweragent_rag_eval_hash"
)

RAG_EVAL_CHUNK_SIZE = 600
RAG_EVAL_CHUNK_OVERLAP = 80

RAG_EVAL_DOCUMENT_FILES = (
    "battery_internal_short_circuit.md",
    "charging_communication_faults.md",
    "power_system_safety_terms.md",
    "battery_digital_twin.md",
    "battery_fault_verification.md",
    "battery_thermal_runaway.md",
)

@dataclass(frozen=True)
class RAGEvaluationResources:
    """一次RAG评测知识库构建结果。"""

    document_paths: tuple[Path, ...]

    documents: tuple[DocumentRecord, ...]

    chunks: tuple[DocumentChunk, ...]

    vector_store: ChromaVectorStore

    retriever: Retriever

    embedding_provider_name: str



def resolve_rag_evaluation_documents(
    knowledge_base_root: Path = (
        KNOWLEDGE_BASE_ROOT
    ),
) -> tuple[Path, ...]:
    """查找评测所需的固定知识文档。"""

    if not knowledge_base_root.exists():
        raise ValueError(
            "知识库目录不存在："
            f"{knowledge_base_root}"
        )

    resolved_paths: list[Path] = []

    for filename in RAG_EVAL_DOCUMENT_FILES:
        matches = sorted(
            knowledge_base_root.rglob(filename)
        )

        if not matches:
            raise ValueError(
                "缺少RAG评测知识文档："
                f"{filename}"
            )

        if len(matches) > 1:
            matched_text = ", ".join(
                str(path)
                for path in matches
            )

            raise ValueError(
                "RAG评测知识文档存在多个同名文件："
                f"{filename}；{matched_text}"
            )

        resolved_paths.append(matches[0])

    return tuple(resolved_paths)


def load_rag_evaluation_documents(
    document_paths: tuple[Path, ...],
    *,
    source_root: Path = KNOWLEDGE_BASE_ROOT,
) -> tuple[DocumentRecord, ...]:
    """加载并校验固定RAG评测文档。"""

    loader = DocumentLoader(
        source_root=source_root
    )

    documents: list[DocumentRecord] = []
    seen_document_ids: set[str] = set()

    for path in document_paths:
        loaded = loader.load_file(path)

        for document in loaded:
            if (
                document.document_id
                in seen_document_ids
            ):
                raise ValueError(
                    "RAG评测文档ID重复："
                    f"{document.document_id}"
                )

            seen_document_ids.add(
                document.document_id
            )

            documents.append(document)

    expected_count = len(
        RAG_EVAL_DOCUMENT_FILES
    )

    if len(documents) != expected_count:
        raise ValueError(
            "RAG评测文档数量不符合预期："
            f"expected={expected_count} "
            f"actual={len(documents)}"
        )

    return tuple(documents)



def split_rag_evaluation_documents(
    documents: tuple[DocumentRecord, ...],
) -> tuple[DocumentChunk, ...]:
    """使用固定参数切分评测知识文档。"""

    splitter = TextSplitter(
        chunk_size=RAG_EVAL_CHUNK_SIZE,
        chunk_overlap=(
            RAG_EVAL_CHUNK_OVERLAP
        ),
    )

    chunks = splitter.split_documents(
        list(documents)
    )

    chunk_ids = [
        chunk.chunk_id
        for chunk in chunks
    ]

    if len(chunk_ids) != len(set(chunk_ids)):
        raise ValueError(
            "RAG评测知识块存在重复chunk_id"
        )

    return tuple(chunks)


def build_rag_evaluation_resources(
    *,
    knowledge_base_root: Path = (
        KNOWLEDGE_BASE_ROOT
    ),
    persist_directory: Path = (
        RAG_EVAL_PERSIST_DIRECTORY
    ),
    reset: bool = True,
) -> RAGEvaluationResources:
    """构建独立且可重复的RAG评测知识库。"""

    document_paths = (
        resolve_rag_evaluation_documents(
            knowledge_base_root
        )
    )

    documents = load_rag_evaluation_documents(
        document_paths,
        source_root=knowledge_base_root,
    )

    chunks = split_rag_evaluation_documents(
        documents
    )

    embedding_provider = (
        HashEmbeddingProvider(
            dimension=256,
            min_ngram=1,
            max_ngram=3,
        )
    )

    vector_store = ChromaVectorStore(
        persist_directory=persist_directory,
        embedding_provider=embedding_provider,
        collection_name=(
            RAG_EVAL_COLLECTION_NAME
        ),
    )

    if reset:
        vector_store.reset()

    processed_count = vector_store.add_chunks(
        list(chunks)
    )

    stored_count = vector_store.count()

    if processed_count != len(chunks):
        raise ValueError(
            "写入评测知识块数量不一致："
            f"expected={len(chunks)} "
            f"actual={processed_count}"
        )

    if stored_count != len(chunks):
        raise ValueError(
            "评测向量库总数量不一致："
            f"expected={len(chunks)} "
            f"actual={stored_count}"
        )

    retriever = Retriever(
        vector_store=vector_store
    )

    return RAGEvaluationResources(
        document_paths=document_paths,
        documents=documents,
        chunks=chunks,
        vector_store=vector_store,
        retriever=retriever,
        embedding_provider_name=(
            embedding_provider.name
        ),
    )


def calculate_file_sha256(
    path: Path,
) -> str:
    """计算知识文档内容哈希。"""

    digest = hashlib.sha256()

    with path.open("rb") as file:
        while True:
            block = file.read(8192)

            if not block:
                break

            digest.update(block)

    return digest.hexdigest()