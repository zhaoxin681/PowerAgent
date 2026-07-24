"""PowerAgent API全局异常处理器。
将系统里所有可能抛出的异常（业务、参数校验、HTTP、RAG、未知）
统一翻译成同一响应格式，并记录结构化日志"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import (
    FastAPI,
    Request,
)
from fastapi.exceptions import (
    RequestValidationError,
)
from fastapi.responses import JSONResponse
from starlette.exceptions import (
    HTTPException as StarletteHTTPException,
)

from app.exceptions import (
    ApiException,
    RequestValidationApiError,
)
from app.middleware import (
    REQUEST_ID_HEADER,
    get_request_id,
)
from app.schemas import (
    ApiError,
    ApiResponse,
    ApiResponseStatus,
)
from rag.exceptions import (
    DocumentLoadError,
    EmbeddingError,
    RAGError,
    RAGGenerationError,
    RetrievalError,
    TextSplitError,
    VectorStoreError,
)


def _get_trace_id(
    request: Request,
) -> str | None:
    """从请求上下文读取合法trace_id。"""

    trace_id = getattr(
        request.state,
        "trace_id",
        None,
    )

    if (
        isinstance(trace_id, str)
        and trace_id
    ):
        return trace_id

    return None


def _get_logger(
    request: Request,
) -> logging.Logger:
    """获取应用日志器或安全兜底日志器。"""

    logger = getattr(
        request.app.state,
        "logger",
        None,
    )

    if isinstance(logger, logging.Logger):
        return logger

    return logging.getLogger(
        "poweragent.api"
    )


def _build_error_response(
    request: Request,
    *,
    status_code: int,
    code: str,
    message: str,
    retryable: bool = False,
    details: list[str] | None = None,
    trace_id: str | None = None,
) -> JSONResponse:
    """构造统一API错误响应。"""

    request_id = get_request_id(
        request
    )

    resolved_trace_id = (
        trace_id
        if trace_id is not None
        else _get_trace_id(request)
    )

    payload = ApiResponse[Any](
        request_id=request_id,
        trace_id=resolved_trace_id,
        status=ApiResponseStatus.ERROR,
        data=None,
        error=ApiError(
            code=code,
            message=message,
            retryable=retryable,
            details=list(
                details
                if details is not None
                else []
            ),
        ),
    )

    return JSONResponse(
        status_code=status_code,
        content=payload.model_dump(
            mode="json"
        ),
        headers={
            REQUEST_ID_HEADER: request_id,
        },
    )


def _build_validation_details(
    exc: RequestValidationError,
) -> list[str]:
    """将Pydantic校验错误转换为安全字段说明。"""

    details: list[str] = []

    for error in exc.errors():
        location = ".".join(
            str(part)
            for part in error.get(
                "loc",
                (),
            )
        )

        message = str(
            error.get(
                "msg",
                "字段值无效",
            )
        )

        if location:
            details.append(
                f"{location}: {message}"
            )
        else:
            details.append(message)

    return list(
        dict.fromkeys(details)
    )


def _resolve_http_error(
    status_code: int,
) -> tuple[str, str, bool]:
    """将Starlette HTTP错误映射为稳定错误码。"""

    mappings: dict[
        int,
        tuple[str, str, bool],
    ] = {
        400: (
            "invalid_request",
            "请求内容不符合接口要求",
            False,
        ),
        401: (
            "unauthorized",
            "当前请求未通过身份验证",
            False,
        ),
        403: (
            "forbidden",
            "当前请求没有访问权限",
            False,
        ),
        404: (
            "resource_not_found",
            "请求的接口或资源不存在",
            False,
        ),
        405: (
            "method_not_allowed",
            "当前接口不支持该HTTP方法",
            False,
        ),
        413: (
            "request_too_large",
            "上传内容超过大小限制",
            False,
        ),
        422: (
            "request_validation_error",
            "请求参数未通过校验",
            False,
        ),
        503: (
            "service_unavailable",
            "PowerAgent服务暂时不可用",
            True,
        ),
    }

    return mappings.get(
        status_code,
        (
            "http_error",
            "HTTP请求处理失败",
            status_code >= 500,
        ),
    )


def _resolve_rag_error(
    exc: RAGError,
) -> tuple[int, str, bool]:
    """将RAG异常映射为HTTP状态和安全消息。"""

    if isinstance(
        exc,
        (
            DocumentLoadError,
            TextSplitError,
        ),
    ):
        return (
            400,
            "知识文档无法读取、解析或切分",
            False,
        )

    if isinstance(
        exc,
        RAGGenerationError,
    ):
        return (
            502,
            "知识增强回答生成失败",
            True,
        )

    if isinstance(
        exc,
        (
            EmbeddingError,
            VectorStoreError,
            RetrievalError,
        ),
    ):
        return (
            503,
            "知识库服务暂时不可用",
            True,
        )

    return (
        500,
        "知识库处理过程发生异常",
        False,
    )


async def handle_api_exception(
    request: Request,
    exc: ApiException,
) -> JSONResponse:
    """处理PowerAgent显式API异常。"""

    logger = _get_logger(request)

    log_method = (
        logger.error
        if exc.status_code >= 500
        else logger.warning
    )

    log_method(
        "PowerAgent API业务异常",
        extra={
            "event": "api_exception",
            "request_id": get_request_id(
                request
            ),
            "trace_id": (
                exc.trace_id
                or _get_trace_id(request)
            ),
            "path": request.url.path,
            "status_code": exc.status_code,
            "error_code": exc.code,
            "error_type": (
                type(exc).__name__
            ),
        },
    )

    return _build_error_response(
        request,
        status_code=exc.status_code,
        code=exc.code,
        message=exc.message,
        retryable=exc.retryable,
        details=exc.details,
        trace_id=exc.trace_id,
    )


async def handle_request_validation_error(
    request: Request,
    exc: RequestValidationError,
) -> JSONResponse:
    """处理FastAPI请求参数校验错误。"""

    error = RequestValidationApiError(
        details=(
            _build_validation_details(exc)
        )
    )

    return await handle_api_exception(
        request,
        error,
    )


async def handle_http_exception(
    request: Request,
    exc: StarletteHTTPException,
) -> JSONResponse:
    """处理框架级HTTP异常。"""

    code, message, retryable = (
        _resolve_http_error(
            exc.status_code
        )
    )

    return _build_error_response(
        request,
        status_code=exc.status_code,
        code=code,
        message=message,
        retryable=retryable,
    )


async def handle_rag_error(
    request: Request,
    exc: RAGError,
) -> JSONResponse:
    """处理RAG加载、检索和生成异常。"""

    status_code, message, retryable = (
        _resolve_rag_error(exc)
    )

    logger = _get_logger(request)

    logger.error(
        "PowerAgent RAG请求处理失败",
        extra={
            "event": "api_rag_error",
            "request_id": get_request_id(
                request
            ),
            "trace_id": _get_trace_id(
                request
            ),
            "path": request.url.path,
            "status_code": status_code,
            "error_code": exc.code,
            "error_type": (
                type(exc).__name__
            ),
        },
    )

    details = (
        [
            f"document_id={exc.document_id}"
        ]
        if exc.document_id
        else []
    )

    return _build_error_response(
        request,
        status_code=status_code,
        code=exc.code,
        message=message,
        retryable=retryable,
        details=details,
    )


async def handle_unexpected_exception(
    request: Request,
    exc: Exception,
) -> JSONResponse:
    """处理未被识别的系统异常。"""

    logger = _get_logger(request)

    logger.error(
        "PowerAgent API发生未处理异常",
        extra={
            "event": (
                "api_unhandled_exception"
            ),
            "request_id": get_request_id(
                request
            ),
            "trace_id": _get_trace_id(
                request
            ),
            "path": request.url.path,
            "status_code": 500,
            "error_type": (
                type(exc).__name__
            ),
        },
        exc_info=(
            type(exc),
            exc,
            exc.__traceback__,
        ),
    )

    return _build_error_response(
        request,
        status_code=500,
        code="internal_server_error",
        message=(
            "PowerAgent服务处理请求时发生异常"
        ),
        retryable=False,
    )


def register_exception_handlers(
    application: FastAPI,
) -> None:
    """注册PowerAgent全部全局异常处理器。"""

    application.add_exception_handler(
        ApiException,
        handle_api_exception,
    )

    application.add_exception_handler(
        RequestValidationError,
        handle_request_validation_error,
    )

    application.add_exception_handler(
        StarletteHTTPException,
        handle_http_exception,
    )

    application.add_exception_handler(
        RAGError,
        handle_rag_error,
    )

    application.add_exception_handler(
        Exception,
        handle_unexpected_exception,
    )