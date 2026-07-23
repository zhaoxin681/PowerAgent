"""PowerAgent API数据模型核心测试。"""

import pytest
from pydantic import ValidationError

from app.schemas import (
    ApiError,
    ApiResponse,
    ApiResponseStatus,
    SkillListData,
    WorkflowAnalysisRequest,
)


def test_workflow_analysis_request_uses_safe_defaults(
) -> None:
    """通用工作流请求应提供安全默认配置。"""

    request = WorkflowAnalysisRequest(
        raw_input="分析动力电池单体压差扩大问题"
    )

    assert request.max_retries == 2
    assert request.skill_inputs == {}
    assert request.include_trace is False
    assert (
        request.include_intermediate_results
        is False
    )


def test_workflow_analysis_request_rejects_extra_fields(
) -> None:
    """API请求不得接收未定义的额外字段。"""

    with pytest.raises(ValidationError):
        WorkflowAnalysisRequest(
            raw_input="分析动力电池异常",
            delete_database=True,
        )


def test_success_response_must_contain_data(
) -> None:
    """成功响应必须包含业务数据。"""

    with pytest.raises(
        ValidationError,
        match="success响应必须包含data",
    ):
        ApiResponse[dict[str, str]](
            request_id="request_001",
            trace_id="trace_001",
            status=ApiResponseStatus.SUCCESS,
            data=None,
            error=None,
        )


def test_error_response_cannot_contain_data(
) -> None:
    """错误响应不能同时包含业务数据。"""

    with pytest.raises(
        ValidationError,
        match="error响应不能包含data",
    ):
        ApiResponse[dict[str, str]](
            request_id="request_001",
            trace_id=None,
            status=ApiResponseStatus.ERROR,
            data={"result": "unexpected"},
            error=ApiError(
                code="internal_error",
                message="服务执行失败",
                retryable=False,
            ),
        )


def test_skill_count_matches_skill_list(
) -> None:
    """Skill数量必须与列表长度保持一致。"""

    with pytest.raises(
        ValidationError,
        match="count必须等于skills列表长度",
    ):
        SkillListData(
            count=1,
            skills=[],
        )