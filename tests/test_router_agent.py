"""Router Agent核心功能测试。"""

import pytest

from agent_core.router_agent import (
    RouteStatus,
    RouterAgent,
)
from agent_core.schemas import (
    PowerSystemIssue,
    Severity,
    Subsystem,
    TaskType,
)


def make_issue(
    *,
    subsystem: Subsystem = Subsystem.BATTERY,
    task_type: TaskType,
    severity: Severity = Severity.LOW,
) -> PowerSystemIssue:
    """创建Router测试所需的最小合法问题。"""

    return PowerSystemIssue(
        raw_text="测试动力系统任务",
        subsystem=subsystem,
        task_type=task_type,
        symptoms=[],
        operating_conditions=[],
        user_hypotheses=[],
        requested_outputs=[],
        missing_information=[],
        severity=severity,
        confidence=0.95,
    )


@pytest.mark.parametrize(
    "task_type",
    [
        TaskType.KNOWLEDGE_QUERY,
        TaskType.DATA_ANALYSIS,
        TaskType.FAULT_DIAGNOSIS,
        TaskType.PARAMETER_OPTIMIZATION,
        TaskType.RND_ANALYSIS,
        TaskType.REPORT_GENERATION,
    ],
)
def test_route_available_tasks(
    task_type: TaskType,
) -> None:
    """已经接入工作流的任务应进入可执行路由。"""

    decision = RouterAgent().route(
        make_issue(task_type=task_type)
    )

    assert decision.route == task_type
    assert decision.status == RouteStatus.AVAILABLE

# 测试任务类型未知
def test_route_unknown_task_needs_information() -> None:
    """已识别子系统但任务目标不清时应要求补充信息。"""

    decision = RouterAgent().route(
        make_issue(task_type=TaskType.UNKNOWN)
    )

    assert decision.route == TaskType.UNKNOWN
    assert (
        decision.status
        == RouteStatus.NEEDS_INFORMATION
    )
    assert decision.missing_information


def test_route_critical_issue_requires_human_review() -> None:
    """严重程度为critical时必须要求人工复核。"""

    decision = RouterAgent().route(
        make_issue(
            task_type=TaskType.FAULT_DIAGNOSIS,
            severity=Severity.CRITICAL,
        )
    )

    assert decision.status == RouteStatus.AVAILABLE
    assert decision.needs_human_review