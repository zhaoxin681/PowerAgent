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
    HTTPException,
    Request,
    Response,
    status,
)

from app.dependencies import (
    ApplicationServices,
)
from app.schemas import (
    ApiResponseStatus,
    RndAnalysisApiRequest,
    RndAnalysisResponse,
    SkillListData,
    SkillListResponse,
    SkillSummary,
    WorkflowAnalysisRequest,
    WorkflowAnalysisResponse,
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