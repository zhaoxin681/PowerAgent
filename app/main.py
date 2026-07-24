"""PowerAgent FastAPI应用入口。真实可运行的FastAPI应用实例"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import (
    AsyncIterator,
    cast,
)

from fastapi import FastAPI

from agent_core.logging_config import (
    configure_logging,
)
from app.api import (
    api_router,
    health_router,
)
from app.config import (
    AppSettings,
    get_settings,
)
from app.schemas import DependencyCheckStatus
from collections.abc import Callable
from app.dependencies import (
    ApplicationServices,
    build_application_services,
)
from app.middleware import (
    register_request_context_middleware,
)
from app.error_handlers import (
    register_exception_handlers,
)

# 测试时可以替换真实依赖构建器，接收AppSettings参数，返回ApplicationServices实例可调用对象
ServiceBuilder = Callable[
    [AppSettings],
    ApplicationServices,
]

@asynccontextmanager
async def lifespan(
    application: FastAPI,
) -> AsyncIterator[None]:
    """管理PowerAgent API启动与停止生命周期。"""
    # 启动阶段
    settings = cast(
        AppSettings,
        application.state.settings,
    )

    readiness_checks = cast(
        dict[str, DependencyCheckStatus],
        application.state.readiness_checks,
    )

    service_builder = cast(
        ServiceBuilder,
        application.state.service_builder,
    )

    logger = configure_logging(
        log_dir=settings.log_dir,
        level=settings.log_level,
    )

    application.state.logger = logger

    readiness_checks["logging"] = (
        DependencyCheckStatus.OK
    )

    core_check_names = (
        "llm_client",
        "skill_registry",
        "vector_store",
        "rag_pipeline",
        "poweragent_workflow",
        "rnd_analysis_workflow",
    )

    try:
        services = service_builder(
            settings
        )

    except Exception as exc:
        application.state.services = None

        for check_name in core_check_names:
            readiness_checks[check_name] = (
                DependencyCheckStatus.FAILED
            )

        logger.error(
            "PowerAgent核心服务初始化失败",
            extra={
                "event": (
                    "api_services_initialization_failed"
                ),
                "error_type": type(exc).__name__,
            },
        )

    else:
        application.state.services = services

        for check_name in core_check_names:
            readiness_checks[check_name] = (
                DependencyCheckStatus.OK
            )

    readiness_checks["application"] = (
            DependencyCheckStatus.OK
        )

    logger.info(
        "PowerAgent API启动完成",
        extra={
            "event": "api_started",
            "service": settings.service_name,
            "version": settings.service_version,
            "environment": (
                settings.environment.value
            ),
            "host": settings.host,
            "port": settings.port,
        },
    )

    # 运行阶段
    try:
        yield  # 之前的代码再应用启动时执行一次，之后的代码在应用关闭时执行一次，控制权给FastAPI

    finally:
        readiness_checks["application"] = (
            DependencyCheckStatus.FAILED
        )

        logger.info(
            "PowerAgent API停止",
            extra={
                "event": "api_stopped",
                "service": settings.service_name,
            },
        )
        application.state.services = None


def create_app(
    settings: AppSettings | None = None,
    *,
    service_builder: ServiceBuilder = (
        build_application_services
    ),
) -> FastAPI:
    """创建并配置PowerAgent FastAPI应用。"""

    resolved_settings = (
        settings
        if settings is not None
        else get_settings()
    )

    application = FastAPI(
        title=resolved_settings.service_name,
        version=resolved_settings.service_version,
        description=(
            "面向动力系统数智化管理的"
            "多Agent工作流平台"
        ),
        docs_url="/docs",
        openapi_url="/openapi.json",
        lifespan=lifespan,  # 将前面定义的生命周期管理器绑定在这个应用实例上
    )

    register_request_context_middleware(
        application
    )

    register_exception_handlers(
        application
    )

    application.state.settings = (
        resolved_settings
    )

    application.state.service_builder = (
        service_builder
    )

    application.state.services = None

    # 初始化就绪检查
    application.state.readiness_checks = {
        "configuration": (
            DependencyCheckStatus.OK
        ),
        "logging": (
            DependencyCheckStatus.FAILED
        ),
        "application": (
            DependencyCheckStatus.FAILED
        ),
        "llm_client": (
            DependencyCheckStatus.FAILED
        ),
        "skill_registry": (
            DependencyCheckStatus.FAILED
        ),
        "vector_store": (
            DependencyCheckStatus.FAILED
        ),
        "rag_pipeline": (
            DependencyCheckStatus.FAILED
        ),
        "poweragent_workflow": (
            DependencyCheckStatus.FAILED
        ),
        "rnd_analysis_workflow": (
            DependencyCheckStatus.FAILED
        ),
    }

    application.include_router(
        health_router
    )

    application.include_router(
        api_router,
        prefix=resolved_settings.api_prefix,
    )

    return application

# 模块级别的app实例
app = create_app()
# 一次完整的请求处理链条：进行启动（创建实例、配置、检查）->Uvicorn触发ASGI lifespan 
# "startup"事件（读取并检查状态，yield进入运行中状态）->请求到达GET /health/ready
# ->进程收到关闭信号（执行finally块）
# 完整数据流：Uvicorn导入app.main:app->create_app()加载AppSettings->创建FastAPI应用
# ->注册成health_router->进入lifespan->初始化结构化日志->更新readliness_checks->
# 服务开始接收请求