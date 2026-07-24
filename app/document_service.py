"""PowerAgent知识文档入库服务。"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from agent_core.schemas import Subsystem
from rag.document_loader import DocumentLoader
from rag.schemas import (
    DocumentRecord,
    DocumentType,
)
from rag.text_splitter import TextSplitter
from rag.vector_store import ChromaVectorStore


class DuplicateDocumentError(RuntimeError):
    """知识库中已经存在同一文档。"""

    def __init__(
        self,
        document_ids: list[str],
    ) -> None:
        self.document_ids = document_ids

        super().__init__(
            "知识库中已经存在文档："
            + "、".join(document_ids)
        )


@dataclass(frozen=True, slots=True)
class DocumentIngestionResult:
    """知识文档入库服务结果。"""

    document_id: str
    filename: str
    file_type: DocumentType
    chunk_count: int
    upserted_count: int
    updated: bool


@dataclass(frozen=True, slots=True)
class DocumentDeletionResult:
    """知识文档删除结果。"""

    document_id: str
    deleted_chunk_count: int
    deleted: bool


@dataclass(frozen=True, slots=True)
class KnowledgeBaseStatusResult:
    """知识库运行状态。"""

    collection_name: str
    chunk_count: int
    embedding_provider: str


class DocumentIngestionService:
    """完成文档加载、切分和向量库写入。"""

    def __init__(
        self,
        *,
        loader: DocumentLoader,
        splitter: TextSplitter,
        vector_store: ChromaVectorStore,
    ) -> None:
        self.loader = loader
        self.splitter = splitter
        self.vector_store = vector_store

    def ingest_file(
        self,
        file_path: str | Path,
        *,
        original_filename: str,
        subsystem: Subsystem | None = None,
        topic: str | None = None,
        overwrite: bool = False,
    ) -> DocumentIngestionResult:
        """将一个受控临时文件写入知识库。"""

        safe_filename = self.sanitize_filename(
            original_filename
        )

        documents = self.loader.load_file(
            file_path
        )

        documents = (
            self._apply_original_file_identity(
                documents,
                temporary_path=Path(file_path),
                original_filename=safe_filename,
            )
        )

        normalized_topic = (
            topic.strip()
            if isinstance(topic, str)
            and topic.strip()
            else None
        )

        documents = [
            self._apply_api_metadata(
                document,
                filename=safe_filename,
                subsystem=subsystem,
                topic=normalized_topic,
            )
            for document in documents
        ]

        existing_document_ids = [
            document.document_id
            for document in documents
            if self.vector_store.document_exists(
                document.document_id
            )
        ]

        if (
            existing_document_ids
            and not overwrite
        ):
            raise DuplicateDocumentError(
                existing_document_ids
            )

        chunks = self.splitter.split_documents(
            documents
        )

        if overwrite:
            for document_id in (
                existing_document_ids
            ):
                self.vector_store.delete_document(
                    document_id
                )

        upserted_count = (
            self.vector_store.add_chunks(
                chunks
            )
        )

        return DocumentIngestionResult(
            document_id=(
                self._resolve_response_document_id(
                    documents
                )
            ),
            filename=safe_filename,
            file_type=documents[0].file_type,
            chunk_count=len(chunks),
            upserted_count=upserted_count,
            updated=bool(
                existing_document_ids
            ),
        )

    @staticmethod
    def sanitize_filename(
        filename: str,
    ) -> str:
        """移除上传文件名中的目录部分。"""

        normalized = filename.replace(
            "\\",
            "/",
        )

        safe_filename = (
            PurePosixPath(normalized)
            .name
            .strip()
        )

        if (
            not safe_filename
            or safe_filename in {".", ".."}
        ):
            raise ValueError(
                "上传文件名不能为空"
            )

        return safe_filename


    @staticmethod
    def _build_document_id(
        filename: str,
    ) -> str:
        """根据安全文件名生成稳定document_id。"""

        normalized_stem = re.sub(
            r"[^a-z0-9_-]+",
            "_",
            Path(filename).stem.lower(),
        ).strip("_-")

        if normalized_stem:
            return normalized_stem

        source_digest = hashlib.sha256(
            filename.encode("utf-8")
        ).hexdigest()[:12]

        return (
            f"document_{source_digest}"
        )
    

    @staticmethod
    def _apply_api_metadata(
        document: DocumentRecord,
        *,
        filename: str,
        subsystem: Subsystem | None,
        topic: str | None,
    ) -> DocumentRecord:
        """使用API参数补充文档元数据。"""

        updates: dict[str, object] = {
            "source_path": filename,
        }

        if subsystem is not None:
            updates["subsystem"] = subsystem

        if topic is not None:
            updates["topic"] = topic

        return document.model_copy(
            update=updates
        )

    @staticmethod
    def _resolve_response_document_id(
        documents: list[DocumentRecord],
    ) -> str:
        """确定对外返回的文档标识。"""

        first_document = documents[0]

        parent_document_id = (
            first_document.metadata.get(
                "parent_document_id"
            )
        )

        if (
            isinstance(
                parent_document_id,
                str,
            )
            and parent_document_id.strip()
        ):
            return parent_document_id

        return first_document.document_id


    def delete_document(
        self,
        document_id: str,
    ) -> DocumentDeletionResult:
        """删除指定文档及其全部知识块。"""

        normalized_id = document_id.strip()

        if not normalized_id:
            raise ValueError(
                "document_id不能为空"
            )

        deleted_count = (
            self.vector_store.delete_document(
                normalized_id
            )
        )

        return DocumentDeletionResult(
            document_id=normalized_id,
            deleted_chunk_count=deleted_count,
            deleted=deleted_count > 0,
        )


    def get_status(
        self,
    ) -> KnowledgeBaseStatusResult:
        """返回当前知识库基本状态。"""

        return KnowledgeBaseStatusResult(
            collection_name=(
                self.vector_store.collection_name
            ),
            chunk_count=(
                self.vector_store.count()
            ),
            embedding_provider=(
                self.vector_store
                .embedding_provider
                .name
            ),
        )


    @classmethod
    def _apply_original_file_identity(
        cls,
        documents: list[DocumentRecord],
        *,
        temporary_path: Path,
        original_filename: str,
    ) -> list[DocumentRecord]:
        """消除随机临时文件名对文档身份的影响。"""

        stable_parent_id = (
            cls._build_document_id(
                original_filename
            )
        )

        temporary_parent_id = (
            cls._build_document_id(
                temporary_path.name
            )
        )

        original_title = (
            Path(original_filename)
            .stem
            .strip()
            or original_filename
        )

        temporary_title = (
            temporary_path.stem
        )

        normalized_documents: list[
            DocumentRecord
        ] = []

        for document in documents:
            document_id = (
                document.document_id
            )

            title = document.title

            metadata = dict(
                document.metadata
            )

            if (
                document.file_type
                == DocumentType.PDF
            ):
                page_number = (
                    document.page_number
                )

                if page_number is None:
                    raise ValueError(
                        "PDF文档页缺少page_number"
                    )

                document_id = (
                    f"{stable_parent_id}_"
                    f"p{page_number:04d}"
                )

                metadata[
                    "parent_document_id"
                ] = stable_parent_id

            elif (
                document.file_type
                == DocumentType.TEXT
                or document.document_id
                == temporary_parent_id
            ):
                # TXT使用原始文件名生成稳定ID。
                # Markdown没有显式document_id时，
                # 其加载结果也会等于临时文件ID。
                document_id = stable_parent_id

            if title == temporary_title:
                title = original_title

            normalized_documents.append(
                document.model_copy(
                    update={
                        "document_id": (
                            document_id
                        ),
                        "title": title,
                        "metadata": metadata,
                    }
                )
            )

        return normalized_documents