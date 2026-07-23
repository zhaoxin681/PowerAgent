"""PowerAgent API层请求、响应和错误数据模型。
基于Pydantic的API数据类型定义文件"""

from __future__ import annotations

from enum import Enum
from typing import Any, Generic, TypeVar

from pydantic import Field, model_validator

from agent_core.schemas import (
    PowerSystemIssue,
    StrictBaseModel,
    TaskType,
)
from agent_core.state import (
    WorkflowError,
    WorkflowTraceEvent,
)
from agent_core.tool_models import ToolCallingResult
from agent_core.workflow_models import (
    FinalWorkflowReport,
    ReviewResult,
)
from rag.schemas import RAGAnswer
from workflows.rnd_models import (
    RndAnalysisRequest,
    RndAnalysisResult,
)
from agent_core.schemas import Subsystem
from rag.schemas import DocumentType

# 不同API业务数据使用的泛型类型。
DataType = TypeVar("DataType")


class ApiResponseStatus(str, Enum):
    """API统一响应状态。"""

    SUCCESS = "success"
    ERROR = "error"


class ApiError(StrictBaseModel):
    """API对外公开的统一错误信息。"""

    code: str = Field(
        min_length=1,
        description="稳定的API错误码",
    )

    message: str = Field(
        min_length=1,
        description="面向调用方的安全错误说明",
    )

    retryable: bool = Field(
        default=False,
        description="客户端是否可以稍后重试",
    )

    details: list[str] = Field(
        default_factory=list,
        description="可选的字段级错误或补充说明",
    )


class ApiResponse(
    StrictBaseModel,
    Generic[DataType],
):
    """PowerAgent所有业务接口的统一响应信封。
    所有接口都返回统一结构，区别只是data的具体类型。"""

    request_id: str = Field(
        min_length=1,
        description="一次HTTP请求的追踪标识",
    )

    trace_id: str | None = Field(
        default=None,
        min_length=1,
        description="一次Agent工作流的追踪标识",
    )

    status: ApiResponseStatus

    data: DataType | None = Field(
        default=None,
        description="接口成功时返回的业务数据",
    )

    error: ApiError | None = Field(
        default=None,
        description="接口失败时返回的错误信息",
    )

    @model_validator(mode="after")
    def validate_response_consistency(
        self,
    ) -> "ApiResponse[DataType]":
        """响应状态必须与data和error保持一致。"""

        if self.status == ApiResponseStatus.SUCCESS:
            if self.data is None:
                raise ValueError(
                    "success响应必须包含data"
                )

            if self.error is not None:
                raise ValueError(
                    "success响应不能包含error"
                )

        if self.status == ApiResponseStatus.ERROR:
            if self.error is None:
                raise ValueError(
                    "error响应必须包含error"
                )

            if self.data is not None:
                raise ValueError(
                    "error响应不能包含data"
                )

        return self


class KnowledgeDocumentUploadData(
    StrictBaseModel
):
    """知识文档上传结果。"""

    document_id: str = Field(
        description="知识文档唯一标识"
    )

    filename: str = Field(
        description="上传文件名称"
    )

    file_type: DocumentType = Field(
        description="文件类型"
    )

    chunk_count: int = Field(
        ge=0,
        description="生成知识块数量"
    )

    upserted_count: int = Field(
        ge=0,
        description="实际写入向量库数量"
    )

    updated: bool = Field(
        description="是否覆盖已有文档"
    )

class KnowledgeDocumentUploadResponse(
    ApiResponse[
        KnowledgeDocumentUploadData
    ]
):
    """知识文档上传接口响应。"""

    pass

# ------------------------------------------------------------------
# 健康检查模型
# ------------------------------------------------------------------


class HealthLiveStatus(str, Enum):
    """服务存活状态。"""

    OK = "ok"


class HealthLiveResponse(StrictBaseModel):
    """服务存活检查响应。"""
    # 服务进程是否还活着，通常只做简单响应。
    status: HealthLiveStatus = HealthLiveStatus.OK

    service: str = Field(
        min_length=1,
        description="服务名称",
    )

    version: str = Field(
        min_length=1,
        description="服务版本",
    )


class DependencyCheckStatus(str, Enum):
    """就绪检查中单项依赖的状态。"""

    OK = "ok"
    FAILED = "failed"


class HealthReadyStatus(str, Enum):
    """服务整体就绪状态。"""

    READY = "ready"
    NOT_READY = "not_ready"


class HealthReadyResponse(StrictBaseModel):
    """服务就绪检查响应。"""
    # 服务是否可以接收流量，会检查数据库、向量库等下游依赖，
    # checks字典记录每个依赖的状态，任何一个FAILED都可能导致
    # 整体NOT_READY。
    status: HealthReadyStatus

    service: str = Field(
        min_length=1,
        description="服务名称",
    )

    version: str = Field(
        min_length=1,
        description="服务版本",
    )

    checks: dict[
        str,
        DependencyCheckStatus,
    ] = Field(
        default_factory=dict,
        description="关键依赖的就绪检查结果",
    )


# ------------------------------------------------------------------
# 通用PowerAgent工作流模型
# ------------------------------------------------------------------


class WorkflowAnalysisRequest(
    StrictBaseModel
):
    """通用PowerAgent工作流请求。"""

    raw_input: str = Field(
        min_length=1,
        description="用户输入的动力系统问题",
    )

    trace_id: str | None = Field(
        default=None,
        min_length=1,
        description="可选调用链追踪标识",
    )

    max_retries: int = Field(
        default=2,
        ge=0,
        le=5,
        description="单个工作流步骤的最大重试次数",
    )

    skill_inputs: dict[
        str,
        dict[str, Any],
    ] | None = Field(
        default=None,
        description="按Skill名称提供的结构化输入",
    )

    include_trace: bool = Field(
        default=False,
        description="是否在响应中返回执行轨迹",
    )

    include_intermediate_results: bool = Field(
        default=False,
        description="是否返回Tool、RAG和错误等中间结果",
    )


class WorkflowIntermediateResults(StrictBaseModel):
    """按需公开的工作流中间结果。"""

    tool_results: list[ToolCallingResult] = Field(
        default_factory=list,
        description="Skill执行结果",
    )

    rag_answers: list[RAGAnswer] = Field(
        default_factory=list,
        description="RAG证据约束回答",
    )

    errors: list[WorkflowError] = Field(
        default_factory=list,
        description="脱敏后的工作流错误记录",
    )


class WorkflowAnalysisData(StrictBaseModel):
    """通用工作流对外公开的业务结果。"""

    issue: PowerSystemIssue

    route: TaskType | None = Field(
        default=None,
        description="Router Agent确定的任务类型",
    )

    route_status: str | None = Field(
        default=None,
        description="Router Agent执行状态",
    )

    route_reason: str | None = Field(
        default=None,
        description="Router Agent路由说明",
    )

    review_result: ReviewResult | None = Field(
        default=None,
        description="Review Agent审核结果",
    )

    final_report: FinalWorkflowReport | None = Field(
        default=None,
        description="Report Agent最终结构化报告",
    )

    needs_human_review: bool = Field(
        description="当前结果是否需要人工复核",
    )

    warnings: list[str] = Field(
        default_factory=list,
        description="需要调用方关注的业务警告",
    )

    execution_trace: (
        list[WorkflowTraceEvent] | None
    ) = Field(
        default=None,
        description="按请求决定是否返回执行轨迹",
    )

    intermediate_results: (
        WorkflowIntermediateResults | None
    ) = Field(
        default=None,
        description="按请求决定是否返回中间结果",
    )


class WorkflowAnalysisResponse(
    ApiResponse[WorkflowAnalysisData]
):
    """通用PowerAgent工作流API响应。"""


# ------------------------------------------------------------------
# 研发分析模型
# ------------------------------------------------------------------


class RndAnalysisApiRequest(RndAnalysisRequest):
    """研发分析API请求。

    在原有研发请求基础上，增加工作流执行配置。
    """

    max_retries: int = Field(
        default=2,
        ge=0,
        le=5,
        description="基础工作流允许的最大重试次数",
    )

    skill_inputs: dict[
        str,
        dict[str, Any],
    ] = Field(
        default_factory=dict,
        description="基础工作流使用的显式Skill参数",
    )


class RndAnalysisResponse(
    ApiResponse[RndAnalysisResult]
):
    """研发分析API响应。"""


# ------------------------------------------------------------------
# Skill目录模型
# ------------------------------------------------------------------


class SkillSummary(StrictBaseModel):
    """API公开的单个Skill摘要。"""

    name: str = Field(
        min_length=1,
        description="Skill稳定名称",
    )

    description: str = Field(
        min_length=1,
        description="Skill能力说明",
    )

    version: str = Field(
        min_length=1,
        description="Skill版本",
    )

    input_schema: dict[str, Any] = Field(
        default_factory=dict,
        description="Skill输入JSON Schema",
    )


class SkillListData(StrictBaseModel):
    """Skill目录接口业务数据。类似插件市场"""

    count: int = Field(
        ge=0,
        description="已注册Skill数量",
    )

    skills: list[SkillSummary] = Field(
        default_factory=list,
        description="已注册Skill摘要列表",
    )

    @model_validator(mode="after")
    def validate_skill_count(
        self,
    ) -> "SkillListData":
        """Skill数量必须与实际列表长度一致。"""

        if self.count != len(self.skills):
            raise ValueError(
                "count必须等于skills列表长度"
            )

        return self


class SkillListResponse(
    ApiResponse[SkillListData]
):
    """Skill目录API响应。"""


# ------------------------------------------------------------------
# 文档上传模型
# ------------------------------------------------------------------


class DocumentIndexStatus(str, Enum):
    """知识文档入库状态。"""

    INDEXED = "indexed"   # 新增入库
    UPDATED = "updated"   # 已存在，更新覆盖


# 典型的RAG知识库文档摄入流程：上传文档->切块->生成向量并写入向量库
class DocumentUploadData(StrictBaseModel):
    """文档上传并入库后的业务结果。"""

    document_id: str = Field(
        min_length=1,
        description="文档稳定标识",
    )

    filename: str = Field(
        min_length=1,
        description="经过安全处理的文件名",
    )

    format: str = Field(
        min_length=1,
        description="文档格式",
    )

    chunk_count: int = Field(
        ge=0,
        description="文档切分得到的知识块数量",
    )

    upserted_count: int = Field(
        ge=0,
        description="实际写入或更新的知识块数量",
    )

    status: DocumentIndexStatus


class DocumentUploadResponse(
    ApiResponse[DocumentUploadData]
):
    """文档上传API响应。"""


class KnowledgeBaseStatusData(
    StrictBaseModel
):
    """知识库状态数据。"""

    collection_name: str = Field(
        min_length=1,
        description="Chroma知识集合名称",
    )

    chunk_count: int = Field(
        ge=0,
        description="当前知识块总数",
    )

    embedding_provider: str = Field(
        min_length=1,
        description="当前Embedding实现名称",
    )


class KnowledgeBaseStatusResponse(
    ApiResponse[KnowledgeBaseStatusData]
):
    """知识库状态API响应。"""


class DocumentDeleteData(
    StrictBaseModel
):
    """知识文档删除结果。"""

    document_id: str = Field(
        min_length=1,
        description="被删除的文档标识",
    )

    deleted_chunk_count: int = Field(
        ge=0,
        description="实际删除的知识块数量",
    )

    deleted: bool = Field(
        description="是否找到并删除文档",
    )


class DocumentDeleteResponse(
    ApiResponse[DocumentDeleteData]
):
    """知识文档删除API响应。"""