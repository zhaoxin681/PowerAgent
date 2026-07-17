"""PowerAgent RAG知识库统一数据契约。"""

from __future__ import annotations

from enum import Enum
from typing import TypeAlias

from pydantic import Field, model_validator

from agent_core.schemas import StrictBaseModel, Subsystem


# 向量数据库元数据通常只支持简单标量类型。
MetadataValue: TypeAlias = str | int | float | bool | None


class DocumentType(str, Enum):
    """当前RAG知识库支持的文档类型。"""

    MARKDOWN = "markdown"
    TEXT = "text"
    PDF = "pdf"

"""
数据流转的五个核心模型
"""
# 原始文档
class DocumentRecord(StrictBaseModel):
    """文档加载器输出的一份标准化原始文档。"""

    document_id: str = Field(
        min_length=1,
        pattern=r"^[a-z0-9][a-z0-9_-]*$",
        description="文档稳定标识，只允许小写字母、数字、下划线和连字符",
    )
    title: str = Field(
        min_length=1,
        description="文档标题",
    )
    content: str = Field(
        min_length=1,
        description="文档正文内容",
    )
    source_path: str = Field(
        min_length=1,
        description="原始文档相对路径或其他可追溯来源",
    )
    file_type: DocumentType = Field(
        description="原始文件类型",
    )
    subsystem: Subsystem = Field(
        default=Subsystem.UNKNOWN,
        description="文档所属动力系统子系统",
    )
    topic: str | None = Field(
        default=None,
        min_length=1,
        description="文档主题；无法确定时为None",
    )
    version: str = Field(
        default="1.0",
        min_length=1,
        description="知识文档版本",
    )
    page_number: int | None = Field(
        default=None,
        ge=1,
        description="文档页码；Markdown和TXT通常为None",
    )
    metadata: dict[str, MetadataValue] = Field(
        default_factory=dict,
        description="用于过滤、追踪和扩展的文档元数据",
    )

# 切分后的知识块
class DocumentChunk(StrictBaseModel):
    """经过文本切分后进入向量库的知识块。"""

    chunk_id: str = Field(
        min_length=1,
        pattern=r"^[a-z0-9][a-z0-9_:-]*$",
        description="知识块稳定标识",
    )
    document_id: str = Field(
        min_length=1,
        pattern=r"^[a-z0-9][a-z0-9_-]*$",
        description="所属文档标识",
    )
    title: str = Field(
        min_length=1,
        description="所属文档标题",
    )
    content: str = Field(
        min_length=1,
        description="知识块正文",
    )
    chunk_index: int = Field(
        ge=0,
        description="知识块在当前文档中的顺序，从0开始",
    )
    source_path: str = Field(
        min_length=1,
        description="原始文档来源",
    )
    file_type: DocumentType = Field(
        description="原始文件类型",
    )
    section_path: str = Field(
        default="",
        description="知识块所在章节路径；没有标题结构时为空字符串",
    )
    page_number: int | None = Field(
        default=None,
        ge=1,
        description="知识块对应页码；无法确定时为None",
    )
    subsystem: Subsystem = Field(
        default=Subsystem.UNKNOWN,
        description="知识块所属动力系统子系统",
    )
    topic: str | None = Field(
        default=None,
        min_length=1,
        description="知识块主题",
    )
    metadata: dict[str, MetadataValue] = Field(
        default_factory=dict,
        description="从原文档继承的简单元数据",
    )

# 检索结果
class RetrievedChunk(StrictBaseModel):
    """Retriever返回的一条结构化检索结果。"""

    chunk_id: str = Field(
        min_length=1,
        description="检索结果对应的知识块标识",
    )
    document_id: str = Field(
        min_length=1,
        description="检索结果所属文档标识",
    )
    title: str = Field(
        min_length=1,
        description="来源文档标题",
    )
    content: str = Field(
        min_length=1,
        description="检索到的知识块内容",
    )
    score: float = Field(
        ge=0.0,
        le=1.0,
        description="统一相关性分数，数值越大表示越相关",
    )
    rank: int = Field(
        ge=1,
        description="当前检索结果中的排名，从1开始",
    )
    source_path: str = Field(
        min_length=1,
        description="原始文档来源",
    )
    section_path: str = Field(
        default="",
        description="知识块所在章节路径",
    )
    page_number: int | None = Field(
        default=None,
        ge=1,
        description="知识块页码",
    )
    subsystem: Subsystem = Field(
        default=Subsystem.UNKNOWN,
        description="所属动力系统子系统",
    )
    topic: str | None = Field(
        default=None,
        min_length=1,
        description="知识主题",
    )
    metadata: dict[str, MetadataValue] = Field(
        default_factory=dict,
        description="检索结果附带的简单元数据",
    )

# 答案引用
class RAGCitation(StrictBaseModel):
    """RAG回答中用于支撑某项结论的证据引用。"""

    chunk_id: str = Field(
        min_length=1,
        description="被引用知识块的标识",
    )
    document_id: str = Field(
        min_length=1,
        description="被引用文档的标识",
    )
    title: str = Field(
        min_length=1,
        description="被引用文档标题",
    )
    section_path: str = Field(
        default="",
        description="证据所在章节路径",
    )
    page_number: int | None = Field(
        default=None,
        ge=1,
        description="证据所在页码",
    )
    supported_claim: str = Field(
        min_length=1,
        description="该证据所支撑的回答结论",
    )
    evidence_text: str = Field(
        min_length=1,
        description="来自知识块的证据摘要",
    )

# 最终结构化答案
class RAGAnswer(StrictBaseModel):
    """RAG管线返回的最终结构化回答。"""

    question: str = Field(
        min_length=1,
        description="用户原始知识问题",
    )
    answer: str = Field(
        min_length=1,
        description="基于检索证据生成的回答",
    )
    citations: list[RAGCitation] = Field(
        default_factory=list,
        description="支撑回答主要结论的证据引用",
    )
    confidence: float = Field(
        ge=0.0,
        le=1.0,
        description="当前回答的证据置信度",
    )
    sufficient_evidence: bool = Field(
        description="当前知识库证据是否足以支撑回答",
    )
    missing_information: list[str] = Field(
        default_factory=list,
        description="仍然缺少的技术资料、运行数据或上下文",
    )
    needs_human_review: bool = Field(
        description="是否需要动力系统专业人员进一步复核",
    )
    # 关键校验逻辑
    @model_validator(mode="after")
    def validate_evidence_consistency(self) -> "RAGAnswer":
        """证据充分的回答必须至少包含一条引用。"""

        if self.sufficient_evidence and not self.citations:
            raise ValueError(
                "sufficient_evidence为True时，citations至少需要包含一条证据"
            )

        citation_ids = [citation.chunk_id for citation in self.citations]

        if len(citation_ids) != len(set(citation_ids)):
            raise ValueError("citations中不允许重复引用同一个chunk_id")

        return self