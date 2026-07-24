"""PowerAgent API统一异常响应核心测试。"""

from __future__ import annotations

from pathlib import Path
from typing import cast

import pytest
from fastapi import (
    FastAPI,
    Request,
)
from fastapi.testclient import TestClient

from agent_core.llm_client import (
    LLMRateLimitError,
    LLMTruncatedResponseError,
)
from app.config import (
    AppSettings,
    RuntimeEnvironment,
)
from app.dependencies import ApplicationServices
from app.exceptions import (
    ApiException,
    DocumentConflictError,
    DocumentValidationError,
    RequestTooLargeError,
    ResourceNotFoundError,
    ServiceUnavailableError,
    WorkflowExecutionError,
)
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


def test_llm_rate_limit_returns_retryable_503(
    tmp_path: Path,
) -> None:
    """LLM限流应返回可重试503响应。"""

    application = create_app(
        make_settings(tmp_path),
        service_builder=build_stub_services,
    )

    @application.get(
        "/test/llm-rate-limit"
    )
    def raise_llm_rate_limit(
        request: Request,
    ) -> None:
        request.state.trace_id = (
            "trace_llm_rate_001"
        )

        raise LLMRateLimitError(
            "供应商限流内部说明"
        )

    with TestClient(
        application,
        raise_server_exceptions=False,
    ) as client:
        response = client.get(
            "/test/llm-rate-limit"
        )

    payload = response.json()

    assert response.status_code == 503

    assert (
        payload["error"]["code"]
        == "llm_rate_limited"
    )

    assert (
        payload["error"]["retryable"]
        is True
    )

    assert (
        payload["trace_id"]
        == "trace_llm_rate_001"
    )

    assert (
        "供应商限流内部说明"
        not in response.text
    )


def test_llm_truncated_response_returns_502(
    tmp_path: Path,
) -> None:
    """LLM输出截断应返回不可重试502响应。"""

    application = create_app(
        make_settings(tmp_path),
        service_builder=build_stub_services,
    )

    @application.get(
        "/test/llm-truncated"
    )
    def raise_llm_truncated(
        request: Request,
    ) -> None:
        request.state.trace_id = (
            "trace_llm_truncated_001"
        )

        raise LLMTruncatedResponseError(
            "内部max_tokens和输出内容"
        )

    with TestClient(
        application,
        raise_server_exceptions=False,
    ) as client:
        response = client.get(
            "/test/llm-truncated"
        )

    payload = response.json()

    assert response.status_code == 502

    assert (
        payload["error"]["code"]
        == "llm_response_truncated"
    )

    assert (
        payload["error"]["retryable"]
        is False
    )

    assert (
        payload["trace_id"]
        == "trace_llm_truncated_001"
    )

    assert (
        "max_tokens"
        not in response.text
    )


@pytest.mark.parametrize(
    (
        "error_type",
        "expected_status",
        "expected_code",
        "expected_retryable",
    ),
    [
        (
            DocumentValidationError,
            400,
            "document_validation_error",
            False,
        ),
        (
            ResourceNotFoundError,
            404,
            "resource_not_found",
            False,
        ),
        (
            DocumentConflictError,
            409,
            "document_conflict",
            False,
        ),
        (
            RequestTooLargeError,
            413,
            "request_too_large",
            False,
        ),
        (
            WorkflowExecutionError,
            500,
            "workflow_execution_error",
            False,
        ),
        (
            ServiceUnavailableError,
            503,
            "service_unavailable",
            True,
        ),
    ],
)
def test_api_exception_matrix_uses_stable_contract(
    tmp_path: Path,
    error_type: type[ApiException],
    expected_status: int,
    expected_code: str,
    expected_retryable: bool,
) -> None:
    """API异常应遵守统一状态码和响应契约。"""

    application = create_app(
        make_settings(tmp_path),
        service_builder=build_stub_services,
    )

    route_path = (
        f"/test/error-matrix/"
        f"{expected_code}"
    )

    def raise_matrix_error(
        request: Request,
    ) -> None:
        request.state.trace_id = (
            "trace_error_matrix_001"
        )

        raise error_type(
            trace_id=(
                "trace_error_matrix_001"
            )
        )

    application.add_api_route(
        route_path,
        raise_matrix_error,
        methods=["GET"],
    )

    with TestClient(
        application,
        raise_server_exceptions=False,
    ) as client:
        response = client.get(
            route_path,
            headers={
                "X-Request-ID": (
                    "matrix-request-001"
                ),
            },
        )

    payload = response.json()

    assert (
        response.status_code
        == expected_status
    )

    assert payload["status"] == "error"
    assert payload["data"] is None

    assert (
        payload["error"]["code"]
        == expected_code
    )

    assert (
        payload["error"]["retryable"]
        is expected_retryable
    )

    assert (
        payload["request_id"]
        == "matrix-request-001"
    )

    assert (
        response.headers[
            "X-Request-ID"
        ]
        == "matrix-request-001"
    )

    assert (
        payload["trace_id"]
        == "trace_error_matrix_001"
    )