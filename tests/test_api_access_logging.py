"""PowerAgent API访问日志核心测试。"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import cast

from fastapi import Request
from fastapi.testclient import TestClient

from app.config import (
    AppSettings,
    RuntimeEnvironment,
)
from app.dependencies import ApplicationServices
from app.exceptions import (
    DocumentValidationError,
)
from app.main import create_app
from agent_core.llm_client import (
    LLMRateLimitError,
)

class RecordCaptureHandler(
    logging.Handler
):
    """在内存中收集日志记录。"""

    def __init__(self) -> None:
        super().__init__()
        self.records: list[
            logging.LogRecord
        ] = []

    def emit(
        self,
        record: logging.LogRecord,
    ) -> None:
        self.records.append(record)


def make_settings(
    tmp_path: Path,
) -> AppSettings:
    """构造访问日志测试配置。"""

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


def find_access_record(
    handler: RecordCaptureHandler,
) -> logging.LogRecord:
    """获取最近一条API访问日志。"""

    for record in reversed(
        handler.records
    ):
        if (
            getattr(
                record,
                "event",
                None,
            )
            == "api_request_completed"
        ):
            return record

    raise AssertionError(
        "没有找到API访问日志"
    )


def test_access_log_contains_request_context(
    tmp_path: Path,
) -> None:
    """成功请求应记录ID、状态码和耗时。"""

    application = create_app(
        make_settings(tmp_path),
        service_builder=build_stub_services,
    )

    @application.get(
        "/test/access-success"
    )
    def access_success(
        request: Request,
    ) -> dict[str, bool]:
        request.state.trace_id = (
            "trace_access_001"
        )

        return {
            "success": True,
        }

    capture_handler = (
        RecordCaptureHandler()
    )

    with TestClient(application) as client:
        application.state.logger.addHandler(
            capture_handler
        )

        try:
            response = client.get(
                "/test/access-success",
                headers={
                    "X-Request-ID": (
                        "access-request-001"
                    ),
                },
            )
        finally:
            application.state.logger.removeHandler(
                capture_handler
            )

    record = find_access_record(
        capture_handler
    )

    assert response.status_code == 200

    assert (
        record.method
        == "GET"
    )

    assert (
        record.path
        == "/test/access-success"
    )

    assert record.status_code == 200

    assert (
        record.request_id
        == "access-request-001"
    )

    assert (
        record.trace_id
        == "trace_access_001"
    )

    assert record.latency_ms >= 0

    assert record.client_host

    assert record.error_type is None
    assert record.error_code is None
    assert not hasattr(
        record,
        "request_body",
    )

    assert not hasattr(
        record,
        "raw_input",
    )

    assert not hasattr(
        record,
        "authorization",
    )

    assert not hasattr(
        record,
        "api_key",
    )


def test_access_log_contains_error_context(
    tmp_path: Path,
) -> None:
    """失败请求应记录错误类型和稳定错误码。"""

    application = create_app(
        make_settings(tmp_path),
        service_builder=build_stub_services,
    )

    @application.get(
        "/test/access-error"
    )
    def access_error() -> None:
        raise DocumentValidationError(
            "测试文档无效"
        )

    capture_handler = (
        RecordCaptureHandler()
    )

    with TestClient(application) as client:
        application.state.logger.addHandler(
            capture_handler
        )

        try:
            response = client.get(
                "/test/access-error"
            )
        finally:
            application.state.logger.removeHandler(
                capture_handler
            )

    record = find_access_record(
        capture_handler
    )

    assert response.status_code == 400

    assert record.status_code == 400

    assert (
        record.error_type
        == "DocumentValidationError"
    )

    assert (
        record.error_code
        == "document_validation_error"
    )

    assert (
        record.request_id
        == response.headers[
            "X-Request-ID"
        ]
    )

    assert record.latency_ms >= 0


def test_access_log_correlates_llm_error(
    tmp_path: Path,
) -> None:
    """LLM错误响应和访问日志应共享追踪上下文。"""

    application = create_app(
        make_settings(tmp_path),
        service_builder=build_stub_services,
    )

    @application.get(
        "/test/access-llm-error"
    )
    def access_llm_error(
        request: Request,
    ) -> None:
        request.state.trace_id = (
            "trace_access_llm_001"
        )

        raise LLMRateLimitError(
            "内部供应商限流说明"
        )

    capture_handler = (
        RecordCaptureHandler()
    )

    with TestClient(
        application,
        raise_server_exceptions=False,
    ) as client:
        application.state.logger.addHandler(
            capture_handler
        )

        try:
            response = client.get(
                "/test/access-llm-error",
                headers={
                    "X-Request-ID": (
                        "access-llm-request-001"
                    ),
                },
            )
        finally:
            application.state.logger.removeHandler(
                capture_handler
            )

    payload = response.json()

    record = find_access_record(
        capture_handler
    )

    assert response.status_code == 503

    assert (
        payload["error"]["code"]
        == "llm_rate_limited"
    )

    assert (
        payload["trace_id"]
        == "trace_access_llm_001"
    )

    assert (
        record.request_id
        == "access-llm-request-001"
    )

    assert (
        record.trace_id
        == "trace_access_llm_001"
    )

    assert record.status_code == 503

    assert (
        record.error_type
        == "LLMRateLimitError"
    )

    assert (
        record.error_code
        == "llm_rate_limited"
    )

    assert record.latency_ms >= 0

    assert (
        "内部供应商限流说明"
        not in response.text
    )