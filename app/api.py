"""PowerAgent FastAPI路由(健康检查路由模块)。
实现云原生应用常见的两个探针接口（存活/就绪探针）"""

from __future__ import annotations

from fastapi import (
    APIRouter,
    Request,
    Response,
    status,
)

from app.config import AppSettings
from app.schemas import (
    DependencyCheckStatus,
    HealthLiveResponse,
    HealthLiveStatus,
    HealthReadyResponse,
    HealthReadyStatus,
)
from typing import Annotated, cast
from uuid import uuid4

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Request,
    Response,
    UploadFile,
    status,
)

from app.dependencies import (
    ApplicationServices,
)
from app.schemas import (
    ApiResponseStatus,
    DocumentIndexStatus,
    DocumentUploadData,
    DocumentUploadResponse,
    RndAnalysisApiRequest,
    RndAnalysisResponse,
    SkillListData,
    SkillListResponse,
    SkillSummary,
    WorkflowAnalysisRequest,
    WorkflowAnalysisResponse,
)
from pathlib import Path
import shutil
import uuid
from agent_core.schemas import Subsystem

from app.document_service import (
    DuplicateDocumentError,
)
from rag.exceptions import DocumentLoadError
from app.document_service import (
    DuplicateDocumentError,
)

from rag.exceptions import (
    DocumentLoadError,
)


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
        raise HTTPException(
            status_code=400,
            detail=(
                "仅支持md/txt/pdf文件"
            ),
        )

    temp_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    temp_path = (
        temp_dir
        /
        f"{uuid.uuid4().hex}{suffix}"
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

                    raise HTTPException(
                        status_code=413,
                        detail=(
                            "上传文件超过大小限制"
                        ),
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
        raise HTTPException(
            status_code=(
                status.HTTP_503_SERVICE_UNAVAILABLE
            ),
            detail=(
                "PowerAgent核心服务尚未准备完成"
            ),
        )

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
    services: ApplicationServicesDependency,
) -> SkillListResponse:
    """返回当前注册的动力系统Skill目录。"""

    data = _build_skill_list_data(
        services
    )

    return SkillListResponse(
        request_id=uuid4().hex,
        trace_id=None,
        status=ApiResponseStatus.SUCCESS,
        data=data,
        error=None,
    )


@api_router.post(
    "/workflows/analyze",
    response_model=WorkflowAnalysisResponse,
    status_code=status.HTTP_200_OK,
    summary="执行通用PowerAgent工作流",
)
def analyze_workflow(
    request_data: WorkflowAnalysisRequest,
    services: ApplicationServicesDependency,
) -> WorkflowAnalysisResponse:
    """执行知识查询、分析、诊断或参数寻优。"""

    result = (
        services.workflow_service.analyze(
            request_data
        )
    )

    return WorkflowAnalysisResponse(
        request_id=uuid4().hex,
        trace_id=result.trace_id,
        status=ApiResponseStatus.SUCCESS,
        data=result.data,
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
            request_id=uuid4().hex,
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
        raise HTTPException(
            status_code=(
                status.HTTP_409_CONFLICT
            ),
            detail=str(exc),
        ) from exc

    except DocumentLoadError as exc:
        raise HTTPException(
            status_code=(
                status.HTTP_400_BAD_REQUEST
            ),
            detail=str(exc),
        ) from exc

    finally:
        _cleanup_temp_file(temp_path)


@api_router.post(
    "/rnd/analyze",
    response_model=RndAnalysisResponse,
    status_code=status.HTTP_200_OK,
    summary="执行研发问题分析工作流",
)
def analyze_rnd_issue(
    request_data: RndAnalysisApiRequest,
    services: ApplicationServicesDependency,
) -> RndAnalysisResponse:
    """生成根因假设、验证实验和团队任务。"""

    result = (
        services.rnd_analysis_service
        .analyze(request_data)
    )

    return RndAnalysisResponse(
        request_id=uuid4().hex,
        trace_id=result.trace_id,
        status=ApiResponseStatus.SUCCESS,
        data=result,
        error=None,
    )