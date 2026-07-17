"""PowerAgent RAG知识库异常体系。"""

from __future__ import annotations


class RAGError(Exception):
    """所有RAG层异常的基础类。"""

    default_code = "rag_error"

    def __init__(
        self,
        message: str,
        *,
        component: str | None = None,
        document_id: str | None = None,
    ) -> None:
        super().__init__(message)

        self.message = message
        self.component = component
        self.document_id = document_id
        self.code = self.default_code

    def __str__(self) -> str:
        """返回便于日志记录和排错的异常字符串。"""

        context_parts: list[str] = []

        if self.component:
            context_parts.append(f"component={self.component}")

        if self.document_id:
            context_parts.append(f"document_id={self.document_id}")

        context_text = " ".join(context_parts)

        if context_text:
            return f"[{self.code}] {context_text}: {self.message}"

        return f"[{self.code}] {self.message}"


class DocumentLoadError(RAGError):
    """文档读取或基础解析失败。"""

    default_code = "document_load_error"

class UnsupportedDocumentTypeError(DocumentLoadError):
    """输入文件类型不在当前支持范围内。"""

    default_code = "unsupported_document_type"

class EmptyDocumentError(DocumentLoadError):
    """文档不存在有效可索引内容。"""

    default_code = "empty_document"


class TextSplitError(RAGError):
    """文档文本切分失败。"""

    default_code = "text_split_error"


class EmbeddingError(RAGError):
    """文档或查询向量化失败。"""

    default_code = "embedding_error"


class VectorStoreError(RAGError):
    """向量库写入、读取、更新或删除失败。"""

    default_code = "vector_store_error"


class RetrievalError(RAGError):
    """知识检索过程失败。"""

    default_code = "retrieval_error"


class RAGGenerationError(RAGError):
    """基于证据生成结构化回答失败。"""

    default_code = "rag_generation_error"

class CitationValidationError(RAGGenerationError):
    """回答引用了未提供、重复或无法追溯的知识块。"""

    default_code = "citation_validation_error"