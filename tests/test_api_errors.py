"""PowerAgent API统一异常响应核心测试。"""

from __future__ import annotations

from pathlib import Path
from typing import cast

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.config import (
    AppSettings,
    RuntimeEnvironment,
)
from app.dependencies import ApplicationServices
from app.main import create_app


def make_settings(
    tmp_path: Path,
) -> AppSettings:
    """构造异常处理测试配置。"""

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
    """构造不访问外部依赖的服务占位。"""

    return cast(
        ApplicationServices,
        object(),
    )


def test_validation_error_uses_api_envelope(
    tmp_path: Path,
) -> None:
    """请求字段校验失败应返回统一422响应。"""

    application = create_app(
        make_settings(tmp_path),
        service_builder=build_stub_services,
    )

    with TestClient(application) as client:
        response = client.post(
            "/api/v1/workflows/analyze",
            json={},
        )

    payload = response.json()

    assert response.status_code == 422
    assert payload["status"] == "error"
    assert payload["data"] is None
    assert (
        payload["error"]["code"]
        == "request_validation_error"
    )
    assert (
        payload["error"]["retryable"]
        is False
    )
    assert payload["error"]["details"]
    assert (
        payload["request_id"]
        == response.headers[
            "X-Request-ID"
        ]
    )


def test_service_unavailable_uses_api_envelope(
    tmp_path: Path,
) -> None:
    """核心服务未初始化应返回统一503响应。"""

    def failed_builder(
        _: AppSettings,
    ) -> ApplicationServices:
        raise RuntimeError(
            "测试依赖初始化失败"
        )

    application = create_app(
        make_settings(tmp_path),
        service_builder=failed_builder,
    )

    with TestClient(application) as client:
        response = client.get(
            "/api/v1/skills"
        )

    payload = response.json()

    assert response.status_code == 503
    assert payload["status"] == "error"
    assert (
        payload["error"]["code"]
        == "service_unavailable"
    )
    assert (
        payload["error"]["retryable"]
        is True
    )
    assert (
        payload["request_id"]
        == response.headers[
            "X-Request-ID"
        ]
    )


def test_unknown_path_uses_api_envelope(
    tmp_path: Path,
) -> None:
    """不存在的接口应返回统一404响应。"""

    application = create_app(
        make_settings(tmp_path),
        service_builder=build_stub_services,
    )

    with TestClient(application) as client:
        response = client.get(
            "/api/v1/not-existing"
        )

    payload = response.json()

    assert response.status_code == 404
    assert payload["status"] == "error"
    assert (
        payload["error"]["code"]
        == "resource_not_found"
    )


def test_unhandled_exception_is_sanitized(
    tmp_path: Path,
) -> None:
    """未知异常不得向客户端暴露内部信息。"""

    application: FastAPI = create_app(
        make_settings(tmp_path),
        service_builder=build_stub_services,
    )

    @application.get(
        "/test/unhandled-error"
    )
    def raise_unhandled_error() -> None:
        raise RuntimeError(
            "内部绝对路径E:/secret和API_KEY"
        )

    with TestClient(
        application,
        raise_server_exceptions=False,
    ) as client:
        response = client.get(
            "/test/unhandled-error"
        )

    payload = response.json()
    response_text = response.text

    assert response.status_code == 500
    assert payload["status"] == "error"
    assert (
        payload["error"]["code"]
        == "internal_server_error"
    )
    assert (
        "E:/secret"
        not in response_text
    )
    assert "API_KEY" not in response_text
    assert (
        payload["request_id"]
        == response.headers[
            "X-Request-ID"
        ]
    )