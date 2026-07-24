"""PowerAgent API请求上下文中间件。
用于给每个HTTP请求生成/校验一个统一的Request ID，方便日志追踪和问题排查"""

from __future__ import annotations

import re
from collections.abc import (
    Awaitable,
    Callable,
)
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

    # 防御性兜底：
    # 即使中间件未执行，也保证调用方取得合法ID。
    generated_id = uuid4().hex
    request.state.request_id = generated_id

    return generated_id


def register_request_context_middleware(
    application: FastAPI,
) -> None:
    """为FastAPI应用注册请求上下文中间件。"""

    @application.middleware("http")
    async def add_request_context(
        request: Request,
        call_next: RequestHandler,
    ) -> Response:
        """为每个HTTP请求创建统一追踪上下文。"""

        request_id = resolve_request_id(
            request.headers.get(
                REQUEST_ID_HEADER
            )
        )

        request.state.request_id = request_id

        # 为后续工作流trace_id关联预留位置。
        request.state.trace_id = None

        response = await call_next(request)

        response.headers[
            REQUEST_ID_HEADER
        ] = request_id

        return response