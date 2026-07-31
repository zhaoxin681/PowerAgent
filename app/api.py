"""PowerAgent FastAPI路由(健康检查路由模块)。"""

from pathlib import Path
from typing import Annotated, cast
from uuid import uuid4

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    Path as ApiPath,
    Request,
    Response,
    UploadFile,
    status,
)
from app.exceptions import (
    DocumentConflictError,
    DocumentValidationError,
    RequestTooLargeError,
    ResourceNotFoundError,
    ServiceUnavailableError,
)

from agent_core.schemas import Subsystem
from app.config import AppSettings
from app.dependencies import ApplicationServices
from app.document_service import (
    DuplicateDocumentError,
)
from app.schemas import (
    ApiResponseStatus,
    DependencyCheckStatus,
    DocumentDeleteData,
    DocumentDeleteResponse,
    DocumentIndexStatus,
    DocumentUploadData,
    DocumentUploadResponse,
    HealthLiveResponse,
    HealthLiveStatus,
    HealthReadyResponse,
    HealthReadyStatus,
    KnowledgeBaseStatusData,
    KnowledgeBaseStatusResponse,
    RndAnalysisApiRequest,
    RndAnalysisResponse,
    SkillListData,
    SkillListResponse,
    SkillSummary,
    WorkflowAnalysisRequest,
    WorkflowAnalysisResponse,
)
from rag.exceptions import DocumentLoadError
from app.middleware import get_request_id


def _build_skill_list_data(
    services: ApplicationServices,
) -> SkillListData:
    """将Registry元数据转换为公开Skill列表。"""

    tool_schemas = (
        services.registry.get_tool_schemas()
    )

    input_schemas_by_name = {
        item["function"]["name"]: (
            item["function"]["parameters"]
        )
        for item in tool_schemas
    }

    skills = [
        SkillSummary(
            name=definition.name,
            description=definition.description,
            version=definition.version,
            input_schema=(
                input_schemas_by_name.get(
                    definition.name,
                    {},
                )
            ),
        )
        for definition
        in services.registry.list_skills()
    ]

    return SkillListData(
        count=len(skills),
        skills=skills,
    )


health_router = APIRouter(
    tags=["health"],
)

# 新建业务
api_router = APIRouter(
    tags=["poweragent"],
)

# 定义允许上传的文档类型
ALLOWED_DOCUMENT_SUFFIXES = {
    ".md",
    ".txt",
    ".pdf",
}


def _save_upload_file(
    upload_file: UploadFile,
    *,
    temp_dir: Path,
    max_bytes: int,
) -> Path:
    """
    将上传文件流保存到受控临时目录。
    """

    filename = (
        upload_file.filename
        or ""
    )

    suffix = (
        Path(filename)
        .suffix
        .lower()
    )

    if suffix not in (
        ALLOWED_DOCUMENT_SUFFIXES
    ):
        raise DocumentValidationError(
            "仅支持md/txt/pdf文件"
        )

    temp_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    temp_path = (
        temp_dir
        /
        f"{uuid4().hex}{suffix}"
    )

    total_size = 0

    try:
        with temp_path.open(
            "wb"
        ) as buffer:

            while True:
                chunk = (
                    upload_file.file.read(
                        1024 * 1024
                    )
                )
                if not chunk:
                    break

                total_size += len(chunk)

                if total_size > max_bytes:
                    raise RequestTooLargeError(
                        "上传文件超过大小限制"
                    )
                buffer.write(chunk)

    except Exception:
        if temp_path.exists():

            temp_path.unlink()
        raise

    return temp_path


def _cleanup_temp_file(
    path: Path | None,
) -> None:
    """删除上传临时文件。"""

    if (
        path is not None
        and path.exists()
    ):
        path.unlink()


def _bind_trace_id(
    request: Request,
    requested_trace_id: str | None,
) -> str:
    """为一次工作流HTTP请求绑定Trace ID。"""

    trace_id = (
        requested_trace_id
        if requested_trace_id
        else uuid4().hex
    )

    request.state.trace_id = trace_id

    return trace_id


def _get_settings(
    request: Request,
) -> AppSettings:
    """从FastAPI应用状态中读取配置。"""

    return cast(
        AppSettings,
        request.app.state.settings,
    )  # 应用启动阶段，把配置对象挂到了state上


def _get_readiness_checks(
    request: Request,
) -> dict[str, DependencyCheckStatus]:
    """从应用状态中读取就绪检查结果。"""

    return cast(
        dict[str, DependencyCheckStatus],
        request.app.state.readiness_checks,
    )  # 应用启动时会执行各种依赖检查，并把结果汇总并挂到state上


def get_application_services(
    request: Request,
) -> ApplicationServices:
    """获取应用启动阶段创建的核心服务。"""

    services = getattr(
        request.app.state,
        "services",
        None,
    )

    if services is None:
        raise ServiceUnavailableError()

    return cast(
        ApplicationServices,
        services,
    )

ApplicationServicesDependency = Annotated[
    ApplicationServices,
    Depends(get_application_services),
]

# 存活探针
@health_router.get(
    "/health/live",
    response_model=HealthLiveResponse,
    status_code=status.HTTP_200_OK,
    summary="服务存活检查",
)
def health_live(
    request: Request,
) -> HealthLiveResponse:
    """检查FastAPI进程是否能够正常响应。"""

    settings = _get_settings(request)

    return HealthLiveResponse(
        status=HealthLiveStatus.OK,
        service=settings.service_name,
        version=settings.service_version,
    )


@health_router.get(
    "/health/ready",
    response_model=HealthReadyResponse,
    status_code=status.HTTP_200_OK,
    responses={
        status.HTTP_503_SERVICE_UNAVAILABLE: {
            "model": HealthReadyResponse,
            "description": "服务尚未准备完成",
        }
    },
    summary="服务就绪检查",
)
def health_ready(
    request: Request,
    response: Response,
) -> HealthReadyResponse:
    """检查应用关键依赖是否完成初始化。"""

    settings = _get_settings(request)

    checks = dict(
        _get_readiness_checks(request)
    )

    is_ready = bool(checks) and all(
        check_status
        == DependencyCheckStatus.OK
        for check_status in checks.values()
    )

    if not is_ready:
        response.status_code = (
            status.HTTP_503_SERVICE_UNAVAILABLE
        )

    return HealthReadyResponse(
        status=(
            HealthReadyStatus.READY
            if is_ready
            else HealthReadyStatus.NOT_READY
        ),
        service=settings.service_name,
        version=settings.service_version,
        checks=checks,
    )

# 把WorkflowService(服务适配层)和ApiResponse统一信封（响应封装层）真正串联起来
@api_router.get(
    "/skills",
    response_model=SkillListResponse,
    status_code=status.HTTP_200_OK,
    summary="查询已注册Skill",
)
def list_skills(
    request: Request,
    services: ApplicationServicesDependency,
) -> SkillListResponse:
    """返回当前注册的动力系统Skill目录。"""

    data = _build_skill_list_data(
        services
    )

    return SkillListResponse(
        request_id=get_request_id(request),
        trace_id=None,
        status=ApiResponseStatus.SUCCESS,
        data=data,
        error=None,
    )


@api_router.post(
    "/knowledge/documents",
    response_model=DocumentUploadResponse,
    status_code=status.HTTP_200_OK,
    summary="上传知识文档",
)
def upload_knowledge_document(
    request: Request,
    services: ApplicationServicesDependency,
    file: UploadFile = File(...),
    topic: str | None = Form(default=None),
    subsystem: Subsystem | None = Form(
        default=None
    ),
    overwrite: bool = Form(default=False),
) -> DocumentUploadResponse:
    """上传动力系统知识文档并更新知识库。"""

    settings = _get_settings(request)
    temp_path: Path | None = None

    try:
        temp_path = _save_upload_file(
            file,
            temp_dir=settings.upload_temp_dir,
            max_bytes=settings.max_upload_bytes,
        )

        result = (
            services.document_service.ingest_file(
                temp_path,
                original_filename=(
                    file.filename
                    or temp_path.name
                ),
                subsystem=subsystem,
                topic=topic,
                overwrite=overwrite,
            )
        )

        return DocumentUploadResponse(
            request_id=get_request_id(request),
            trace_id=None,
            status=ApiResponseStatus.SUCCESS,
            data=DocumentUploadData(
                document_id=result.document_id,
                filename=result.filename,
                format=result.file_type.value,
                chunk_count=result.chunk_count,
                upserted_count=(
                    result.upserted_count
                ),
                status=(
                    DocumentIndexStatus.UPDATED
                    if result.updated
                    else DocumentIndexStatus.INDEXED
                ),
            ),
            error=None,
        )

    except DuplicateDocumentError as exc:
        raise DocumentConflictError(
            "知识库中已经存在同一文档",
            details=[
                str(exc),
            ],
        ) from exc

    except DocumentLoadError as exc:
        raise DocumentValidationError(
            "知识文档无法读取或解析",
            details=(
                [
                    f"document_id={exc.document_id}"
                ]
                if exc.document_id
                else []
            ),
        ) from exc
    finally:
        _cleanup_temp_file(temp_path)


@api_router.delete(
    "/knowledge/documents/{document_id}",
    response_model=DocumentDeleteResponse,
    status_code=status.HTTP_200_OK,
    summary="删除知识文档",
)
def delete_knowledge_document(
    request: Request,
    services: ApplicationServicesDependency,
    document_id: Annotated[
        str,
        ApiPath(
            min_length=1,
            pattern=(
                r"^[a-z0-9]"
                r"[a-z0-9_-]*$"
            ),
            description="需要删除的文档标识",
        ),
    ],
) -> DocumentDeleteResponse:
    """删除文档对应的全部向量知识块。"""

    result = (
        services.document_service
        .delete_document(document_id)
    )

    if not result.deleted:
        raise ResourceNotFoundError(
            (
                "知识库中不存在指定文档："
                f"{document_id}"
            ),
            details=[
                f"document_id={document_id}",
            ],
        )

    return DocumentDeleteResponse(
        request_id=get_request_id(request),
        trace_id=None,
        status=ApiResponseStatus.SUCCESS,
        data=DocumentDeleteData(
            document_id=result.document_id,
            deleted_chunk_count=(
                result.deleted_chunk_count
            ),
            deleted=result.deleted,
        ),
        error=None,
    )


@api_router.get(
    "/knowledge/status",
    response_model=KnowledgeBaseStatusResponse,
    status_code=status.HTTP_200_OK,
    summary="查询知识库状态",
)
def get_knowledge_base_status(
    request: Request,
    services: ApplicationServicesDependency,
) -> KnowledgeBaseStatusResponse:
    """返回当前知识库集合和知识块数量。"""

    result = (
        services.document_service
        .get_status()
    )

    return KnowledgeBaseStatusResponse(
        request_id=get_request_id(request),
        trace_id=None,
        status=ApiResponseStatus.SUCCESS,
        data=KnowledgeBaseStatusData(
            collection_name=(
                result.collection_name
            ),
            chunk_count=result.chunk_count,
            embedding_provider=(
                result.embedding_provider
            ),
        ),
        error=None,
    )


@api_router.post(
    "/workflows/analyze",
    response_model=WorkflowAnalysisResponse,
    status_code=status.HTTP_200_OK,
    summary="执行通用PowerAgent工作流",
)
def analyze_workflow(
    request: Request,
    request_data: WorkflowAnalysisRequest,
    services: ApplicationServicesDependency,
) -> WorkflowAnalysisResponse:
    """执行知识查询、分析、诊断或参数寻优。"""

    trace_id = _bind_trace_id(
        request,
        request_data.trace_id,
    )

    normalized_request = (
        request_data.model_copy(
            update={
                "trace_id": trace_id,
            }
        )
    )

    result = (
        services.workflow_service.analyze(
            normalized_request
        )
    )

    request.state.trace_id = result.trace_id

    return WorkflowAnalysisResponse(
        request_id=get_request_id(request),
        trace_id=result.trace_id,
        status=ApiResponseStatus.SUCCESS,
        data=result.data,
        error=None,
    )



@api_router.post(
    "/rnd/analyze",
    response_model=RndAnalysisResponse,
    status_code=status.HTTP_200_OK,
    summary="执行研发问题分析工作流",
)
def analyze_rnd_issue(
    request: Request,
    request_data: RndAnalysisApiRequest,
    services: ApplicationServicesDependency,
) -> RndAnalysisResponse:
    """生成根因假设、验证实验和团队任务。"""

    trace_id = _bind_trace_id(
        request,
        request_data.trace_id,
    )

    normalized_request = (
        request_data.model_copy(
            update={
                "trace_id": trace_id,
            }
        )
    )

    result = (
        services.rnd_analysis_service
        .analyze(normalized_request)
    )

    request.state.trace_id = (
        result.trace_id
        or trace_id
    )

    return RndAnalysisResponse(
        request_id=get_request_id(request),
        trace_id=(
            result.trace_id
            or trace_id
        ),
        status=ApiResponseStatus.SUCCESS,
        data=result,
        error=None,
    )