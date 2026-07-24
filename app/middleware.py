"""PowerAgent API请求上下文与访问日志中间件。"""

from __future__ import annotations

import logging
import re
from collections.abc import (
    Awaitable,
    Callable,
)
from time import perf_counter
from uuid import uuid4

from fastapi import (
    FastAPI,
    Request,
    Response,
)


REQUEST_ID_HEADER = "X-Request-ID"

REQUEST_ID_PATTERN = re.compile(
    r"^[A-Za-z0-9][A-Za-z0-9._-]{7,63}$"
)

RequestHandler = Callable[
    [Request],
    Awaitable[Response],
]


def resolve_request_id(
    header_value: str | None,
) -> str:
    """校验客户端Request ID或生成新的标识。"""

    if header_value is not None:
        candidate = header_value.strip()

        if REQUEST_ID_PATTERN.fullmatch(
            candidate
        ):
            return candidate

    return uuid4().hex


def get_request_id(
    request: Request,
) -> str:
    """从当前请求上下文中读取Request ID。"""

    request_id = getattr(
        request.state,
        "request_id",
        None,
    )

    if (
        isinstance(request_id, str)
        and request_id
    ):
        return request_id

    generated_id = uuid4().hex
    request.state.request_id = generated_id

    return generated_id


def _get_trace_id(
    request: Request,
) -> str | None:
    """从请求上下文读取工作流Trace ID。"""

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


def _get_client_host(
    request: Request,
) -> str | None:
    """安全读取客户端地址。"""

    if request.client is None:
        return None

    return request.client.host


def _get_access_logger(
    request: Request,
) -> logging.Logger:
    """获取API访问日志器。"""

    application_logger = getattr(
        request.app.state,
        "logger",
        None,
    )

    if isinstance(
        application_logger,
        logging.Logger,
    ):
        return application_logger.getChild(
            "api.access"
        )

    return logging.getLogger(
        "poweragent.api.access"
    )


def register_request_context_middleware(
    application: FastAPI,
) -> None:
    """注册请求上下文和访问日志中间件。"""

    @application.middleware("http")
    async def add_request_context(
        request: Request,
        call_next: RequestHandler,
    ) -> Response:
        """建立请求上下文并记录访问日志。"""

        request_id = resolve_request_id(
            request.headers.get(
                REQUEST_ID_HEADER
            )
        )

        request.state.request_id = request_id
        request.state.trace_id = None
        request.state.error_type = None
        request.state.error_code = None

        started_at = perf_counter()

        status_code = 500
        raised_error_type: str | None = None
        raised_error_code: str | None = None

        try:
            response = await call_next(
                request
            )

            status_code = (
                response.status_code
            )

            response.headers[
                REQUEST_ID_HEADER
            ] = request_id

            return response

        except Exception as exc:
            raised_error_type = (
                type(exc).__name__
            )

            exception_code = getattr(
                exc,
                "code",
                None,
            )

            raised_error_code = (
                exception_code
                if isinstance(
                    exception_code,
                    str,
                )
                else "internal_server_error"
            )

            exception_trace_id = getattr(
                exc,
                "trace_id",
                None,
            )

            if (
                isinstance(
                    exception_trace_id,
                    str,
                )
                and exception_trace_id
            ):
                request.state.trace_id = (
                    exception_trace_id
                )

            # 中间件只记录异常上下文，
            # 具体响应仍交给全局异常处理器。
            raise

        finally:
            latency_ms = round(
                (
                    perf_counter()
                    - started_at
                )
                * 1000,
                2,
            )

            state_error_type = getattr(
                request.state,
                "error_type",
                None,
            )

            state_error_code = getattr(
                request.state,
                "error_code",
                None,
            )

            access_logger = (
                _get_access_logger(request)
            )

            access_logger.info(
                "PowerAgent API请求完成",
                extra={
                    "event": (
                        "api_request_completed"
                    ),
                    "method": request.method,
                    "path": request.url.path,
                    "status_code": status_code,
                    "request_id": request_id,
                    "trace_id": (
                        _get_trace_id(
                            request
                        )
                    ),
                    "latency_ms": latency_ms,
                    "client_host": (
                        _get_client_host(
                            request
                        )
                    ),
                    "error_type": (
                        raised_error_type
                        or state_error_type
                    ),
                    "error_code": (
                        raised_error_code
                        or state_error_code
                    ),
                },
            )