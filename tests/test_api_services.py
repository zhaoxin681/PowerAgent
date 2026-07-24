"""PowerAgent API服务适配层核心测试。"""

from __future__ import annotations

from typing import Any

from agent_core.schemas import (
    PowerSystemIssue,
    Severity,
    Subsystem,
    TaskType,
)
from agent_core.state import (
    TraceEventStatus,
    WorkflowError,
    WorkflowNode,
    WorkflowTraceEvent,
)
from agent_core.workflow_models import (
    FinalWorkflowReport,
    ReportStatus,
    ReviewStatus,
)
from app.schemas import (
    RndAnalysisApiRequest,
    WorkflowAnalysisRequest,
)
from app.services import (
    RndAnalysisService,
    WorkflowService,
)
from skills.schemas import RiskLevel
from workflows.rnd_models import (
    RndAnalysisRequest,
    RndAnalysisResult,
    RndAnalysisStatus,
)
import re
import pytest
from app.exceptions import (
    WorkflowExecutionError,
)

def make_issue(
    *,
    task_type: TaskType = (
        TaskType.FAULT_DIAGNOSIS
    ),
) -> PowerSystemIssue:
    """构造最小合法动力系统问题。"""

    return PowerSystemIssue(
        raw_text="分析动力电池单体压差扩大问题",
        subsystem=Subsystem.BATTERY,
        task_type=task_type,
        symptoms=["单体压差扩大"],
        operating_conditions=[],
        user_hypotheses=[],
        requested_outputs=["分析结果"],
        missing_information=[],
        severity=Severity.MEDIUM,
        confidence=0.95,
    )


def test_workflow_service_hides_optional_results(
) -> None:
    """默认响应不应包含轨迹和中间结果。"""

    class FakeWorkflow:
        def invoke(
            self,
            raw_input: str,
            **_: Any,
        ) -> dict[str, Any]:
            return {
                "trace_id": "trace_service_001",
                "issue": make_issue(),
                "route": TaskType.FAULT_DIAGNOSIS,
                "route_status": "available",
                "route_reason": "任务可以执行",
                "review_result": None,
                "final_report": None,
                "needs_human_review": False,
                "execution_trace": [
                    WorkflowTraceEvent(
                        node=WorkflowNode.ROUTER,
                        status=(
                            TraceEventStatus.COMPLETED
                        ),
                        detail="路由完成",
                    )
                ],
                "tool_results": [],
                "rag_answers": [],
                "errors": [],
            }

    service = WorkflowService(
        workflow=FakeWorkflow()
    )

    result = service.analyze(
        WorkflowAnalysisRequest(
            raw_input="分析动力电池异常"
        )
    )

    assert result.trace_id == "trace_service_001"
    assert (
        result.data.route
        == TaskType.FAULT_DIAGNOSIS
    )
    assert result.data.execution_trace is None
    assert (
        result.data.intermediate_results
        is None
    )
    assert result.data.warnings == []


def test_workflow_service_exposes_requested_details(
) -> None:
    """显式开启时应返回轨迹和中间结果。"""

    workflow_error = WorkflowError(
        node=WorkflowNode.EXECUTOR,
        error_code="demo_error",
        message="演示工作流错误",
        retryable=False,
    )

    blocked_report = FinalWorkflowReport(
        status=ReportStatus.BLOCKED,
        trace_id="trace_service_002",
        review_status=(
            ReviewStatus.INSUFFICIENT_EVIDENCE
        ),
        issue_severity=Severity.MEDIUM,
        needs_human_review=True,
        report=None,
        blocked_reason="证据不足，报告被阻断。",
    )

    class FakeWorkflow:
        def invoke(
            self,
            raw_input: str,
            **_: Any,
        ) -> dict[str, Any]:
            return {
                "trace_id": "trace_service_002",
                "issue": make_issue(),
                "route": TaskType.FAULT_DIAGNOSIS,
                "route_status": "available",
                "route_reason": "任务可以执行",
                "review_result": None,
                "final_report": blocked_report,
                "needs_human_review": True,
                "planner_status": "ready",
                "planner_reason": "计划生成完成",
                "execution_trace": [
                    WorkflowTraceEvent(
                        node=WorkflowNode.REPORT,
                        status=(
                            TraceEventStatus.COMPLETED
                        ),
                        detail="报告被阻断",
                    )
                ],
                "tool_results": [],
                "rag_answers": [],
                "errors": [workflow_error],
            }

    service = WorkflowService(
        workflow=FakeWorkflow()
    )

    result = service.analyze(
        WorkflowAnalysisRequest(
            raw_input="分析动力电池异常",
            include_trace=True,
            include_intermediate_results=True,
        )
    )

    assert (
        result.trace_id
        == "trace_service_002"
    )

    assert (
        result.data.execution_trace
        is not None
    )
    assert len(
        result.data.execution_trace
    ) == 1

    assert (
        result.data.intermediate_results
        is not None
    )
    assert len(
        result.data
        .intermediate_results
        .errors
    ) == 1

    assert (
        result.data.needs_human_review
        is True
    )

    assert (
        "当前结果需要动力系统专业人员复核。"
        in result.data.warnings
    )

    assert (
        "证据不足，报告被阻断。"
        in result.data.warnings
    )



def test_rnd_service_separates_api_options(
) -> None:
    """API执行配置不得进入领域请求模型。"""

    class FakeRndWorkflow:
        def __init__(self) -> None:
            self.received_request: (
                RndAnalysisRequest | None
            ) = None
            self.received_skill_inputs: (
                dict[str, dict[str, Any]]
                | None
            ) = None
            self.received_max_retries: (
                int | None
            ) = None

        def analyze(
            self,
            request: RndAnalysisRequest,
            *,
            skill_inputs: (
                dict[str, dict[str, Any]]
                | None
            ) = None,
            max_retries: int = 2,
        ) -> RndAnalysisResult:
            self.received_request = request
            self.received_skill_inputs = (
                skill_inputs
            )
            self.received_max_retries = (
                max_retries
            )

            return RndAnalysisResult(
                status=(
                    RndAnalysisStatus
                    .EXECUTION_FAILED
                ),
                trace_id=request.trace_id,
                issue=make_issue(
                    task_type=(
                        TaskType.RND_ANALYSIS
                    )
                ),
                summary="研发分析未形成有效方案",
                known_facts=[],
                missing_information=[],
                hypotheses=[],
                experiments=[],
                team_assignments=[],
                dependencies=[],
                risks=[],
                overall_risk_level=(
                    RiskLevel.MEDIUM
                ),
                needs_human_review=True,
                unresolved_items=[],
                failure_reason="演示失败原因",
            )

    workflow = FakeRndWorkflow()

    service = RndAnalysisService(
        workflow=workflow
    )

    result = service.analyze(
        RndAnalysisApiRequest(
            raw_input="分析高温快充异常",
            affected_scope=["高温快充车辆"],
            available_data=["单体电压"],
            requested_deliverables=[
                "候选根因"
            ],
            max_retries=3,
            skill_inputs={
                "battery_analysis": {
                    "cell_voltages_v": [
                        3.5,
                        3.6,
                    ]
                }
            },
        )
    )

    assert (
        result.status
        == RndAnalysisStatus.EXECUTION_FAILED
    )

    assert isinstance(
        workflow.received_request,
        RndAnalysisRequest,
    )

    assert (
        "max_retries"
        not in workflow.received_request
        .model_dump()
    )

    assert (
        "skill_inputs"
        not in workflow.received_request
        .model_dump()
    )

    assert workflow.received_max_retries == 3
    assert (
        workflow.received_skill_inputs
        is not None
    )
    assert (
        workflow.received_request
        is not None
    )

    assert (
        workflow.received_request.trace_id
        is not None
    )

    assert re.fullmatch(
        r"[0-9a-f]{32}",
        workflow.received_request.trace_id,
    )

    assert (
        result.trace_id
        == workflow.received_request.trace_id
    )


def test_workflow_service_contract_error_keeps_trace_id(
) -> None:
    """工作流缺少必要输出时应返回可追踪异常。"""

    class FakeWorkflow:
        def invoke(
            self,
            raw_input: str,
            *,
            trace_id: str | None = None,
            **_: Any,
        ) -> dict[str, Any]:
            return {
                "trace_id": trace_id,
                "issue": None,
            }

    service = WorkflowService(
        workflow=FakeWorkflow()
    )

    with pytest.raises(
        WorkflowExecutionError
    ) as exc_info:
        service.analyze(
            WorkflowAnalysisRequest(
                raw_input="分析动力电池异常",
                trace_id="trace_contract_001",
            )
        )

    assert (
        exc_info.value.code
        == "workflow_execution_error"
    )

    assert (
        exc_info.value.trace_id
        == "trace_contract_001"
    )