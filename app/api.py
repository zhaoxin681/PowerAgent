"""PowerAgent FastAPI路由(健康检查路由模块)。
实现云原生应用常见的两个探针接口（存活/就绪探针）"""

from __future__ import annotations

from typing import cast

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


health_router = APIRouter(
    tags=["health"],
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