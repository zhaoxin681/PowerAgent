"""PowerAgent Request ID中间件核心测试。"""

from __future__ import annotations

import re
from pathlib import Path
from typing import cast

from fastapi import Request
from fastapi.testclient import TestClient

from app.config import (
    AppSettings,
    RuntimeEnvironment,
)
from app.dependencies import ApplicationServices
from app.main import create_app
from app.middleware import (
    REQUEST_ID_HEADER,
    get_request_id,
)


def make_settings(
    tmp_path: Path,
) -> AppSettings:
    """构造Request ID测试配置。"""

    return AppSettings(
        service_name="PowerAgent Test",
        service_version="0.1.0-test",
        environment=RuntimeEnvironment.TEST,
        api_prefix="/api/v1",
        host="127.0.0.1",
        port=8000,
        log_level="INFO",
        log_dir=tmp_path / "logs",
    )


def build_stub_services(
    _: AppSettings,
) -> ApplicationServices:
    """构造不访问真实外部依赖的服务占位。"""

    return cast(
        ApplicationServices,
        object(),
    )


def build_test_app(
    tmp_path: Path,
):
    """创建用于检查请求上下文的应用。"""

    application = create_app(
        make_settings(tmp_path),
        service_builder=build_stub_services,
    )

    @application.get(
        "/test/request-context"
    )
    def read_request_context(
        request: Request,
    ) -> dict[str, str]:
        """返回中间件写入的Request ID。"""

        return {
            "request_id": get_request_id(
                request
            )
        }

    return application


def test_middleware_generates_request_id(
    tmp_path: Path,
) -> None:
    """未传入Request ID时应自动生成。"""

    application = build_test_app(tmp_path)

    with TestClient(application) as client:
        response = client.get(
            "/test/request-context"
        )

    request_id = (
        response.json()["request_id"]
    )

    assert response.status_code == 200
    assert re.fullmatch(
        r"[0-9a-f]{32}",
        request_id,
    )
    assert (
        response.headers[
            REQUEST_ID_HEADER
        ]
        == request_id
    )


def test_middleware_preserves_valid_request_id(
    tmp_path: Path,
) -> None:
    """合法客户端Request ID应被完整保留。"""

    application = build_test_app(tmp_path)

    supplied_id = "client-request_001"

    with TestClient(application) as client:
        response = client.get(
            "/test/request-context",
            headers={
                REQUEST_ID_HEADER: supplied_id,
            },
        )

    assert response.status_code == 200
    assert (
        response.json()["request_id"]
        == supplied_id
    )
    assert (
        response.headers[
            REQUEST_ID_HEADER
        ]
        == supplied_id
    )


def test_middleware_replaces_invalid_request_id(
    tmp_path: Path,
) -> None:
    """非法客户端Request ID不得进入请求上下文。"""

    application = build_test_app(tmp_path)

    invalid_id = "invalid request id"

    with TestClient(application) as client:
        response = client.get(
            "/test/request-context",
            headers={
                REQUEST_ID_HEADER: invalid_id,
            },
        )

    generated_id = (
        response.json()["request_id"]
    )

    assert response.status_code == 200
    assert generated_id != invalid_id
    assert re.fullmatch(
        r"[0-9a-f]{32}",
        generated_id,
    )
    assert (
        response.headers[
            REQUEST_ID_HEADER
        ]
        == generated_id
    )