"""PowerAgent API异常体系核心测试。"""

from app.exceptions import (
    ApiException,
    DocumentConflictError,
    ResourceNotFoundError,
    ServiceUnavailableError,
)


def test_api_exception_uses_safe_defaults(
) -> None:
    """基础异常应提供稳定默认值。"""

    error = ApiException()

    assert error.status_code == 500
    assert (
        error.code
        == "internal_server_error"
    )
    assert error.retryable is False
    assert (
        str(error)
        == "PowerAgent服务处理请求时发生异常"
    )
    assert error.details == []
    assert error.trace_id is None


def test_api_exception_preserves_public_context(
) -> None:
    """异常应保留安全说明和追踪信息。"""

    error = DocumentConflictError(
        "文档battery_note已经存在",
        details=[
            "document_id=battery_note",
        ],
        trace_id="trace_document_001",
    )

    assert error.status_code == 409
    assert error.code == "document_conflict"
    assert error.retryable is False
    assert (
        error.message
        == "文档battery_note已经存在"
    )
    assert error.details == [
        "document_id=battery_note",
    ]
    assert (
        error.trace_id
        == "trace_document_001"
    )


def test_retryability_matches_error_type(
) -> None:
    """依赖故障可重试，资源不存在不可重试。"""

    unavailable_error = (
        ServiceUnavailableError()
    )

    not_found_error = (
        ResourceNotFoundError()
    )

    assert (
        unavailable_error.status_code
        == 503
    )
    assert unavailable_error.retryable is True

    assert not_found_error.status_code == 404
    assert not_found_error.retryable is False