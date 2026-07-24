"""PowerAgent API统一异常体系。"""

from __future__ import annotations

from typing import ClassVar


class ApiException(Exception):
    """所有API层异常的基础类型。"""

    status_code: ClassVar[int] = 500
    code: ClassVar[str] = "internal_server_error"
    default_message: ClassVar[str] = (
        "PowerAgent服务处理请求时发生异常"
    )
    retryable: ClassVar[bool] = False

    def __init__(
        self,
        message: str | None = None,
        *,
        details: list[str] | None = None,
        trace_id: str | None = None,
    ) -> None:
        """初始化可安全返回给调用方的API异常。"""

        self.message = (
            message
            if message is not None
            else self.default_message
        )

        self.details = list(
            details
            if details is not None
            else []
        )

        self.trace_id = trace_id

        super().__init__(self.message)

    def __str__(self) -> str:
        """返回安全、稳定的错误说明。"""

        return self.message


class InvalidRequestError(ApiException):
    """请求内容不符合当前接口要求。"""

    status_code = 400
    code = "invalid_request"
    default_message = "请求内容不符合接口要求"


class DocumentValidationError(ApiException):
    """知识文档格式或内容无效。"""

    status_code = 400
    code = "document_validation_error"
    default_message = "知识文档未通过校验"


class ResourceNotFoundError(ApiException):
    """请求的业务资源不存在。"""

    status_code = 404
    code = "resource_not_found"
    default_message = "请求的资源不存在"


class DocumentConflictError(ApiException):
    """知识库中已经存在冲突文档。"""

    status_code = 409
    code = "document_conflict"
    default_message = "知识库中已经存在同一文档"


class RequestTooLargeError(ApiException):
    """上传内容超过接口允许的大小。"""

    status_code = 413
    code = "request_too_large"
    default_message = "上传内容超过大小限制"


class UpstreamServiceError(ApiException):
    """LLM等上游服务调用失败。"""

    status_code = 502
    code = "upstream_service_error"
    default_message = "上游智能服务调用失败"
    retryable = True


class ServiceUnavailableError(ApiException):
    """PowerAgent关键依赖尚未准备完成。"""

    status_code = 503
    code = "service_unavailable"
    default_message = "PowerAgent核心服务尚未准备完成"
    retryable = True


class WorkflowExecutionError(ApiException):
    """工作流违反服务层输出契约。"""

    status_code = 500
    code = "workflow_execution_error"
    default_message = "PowerAgent工作流执行失败"