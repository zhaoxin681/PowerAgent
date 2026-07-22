"""第七周统一评测流水线核心测试。"""

from agent_core.router_agent import (
    RouteStatus,
)
from agent_core.schemas import (
    Severity,
    Subsystem,
    TaskType,
)
from evaluation.evaluate_router import (
    evaluate_router_case,
)
from evaluation.schemas import (
    EvaluationCase,
    EvaluatorType,
    RouteExpectation,
    RouterIssueInput,
)


def test_evaluate_router_available_case() -> None:
    """可执行任务应正确通过Router评测。"""

    case = EvaluationCase(
        case_id="router_test_available",
        user_input="分析电池电压。",
        evaluators=[
            EvaluatorType.ROUTER,
        ],
        route_expectation=RouteExpectation(
            issue=RouterIssueInput(
                subsystem=Subsystem.BATTERY,
                task_type=TaskType.DATA_ANALYSIS,
                severity=Severity.LOW,
            ),
            route=TaskType.DATA_ANALYSIS,
            status=RouteStatus.AVAILABLE,
            needs_human_review=False,
        ),
    )

    _, checks, counts = evaluate_router_case(
        case
    )

    assert checks["overall"]["passed"]
    assert counts["route_correct"] == 1
    assert counts["status_correct"] == 1


def test_evaluate_router_unknown_subsystem() -> None:
    """未知子系统应进入unsupported。"""

    required_item = (
        "明确问题涉及的动力系统对象或子系统"
    )

    case = EvaluationCase(
        case_id="router_test_unsupported",
        user_input="分析这个设备。",
        evaluators=[
            EvaluatorType.ROUTER,
        ],
        route_expectation=RouteExpectation(
            issue=RouterIssueInput(
                subsystem=Subsystem.UNKNOWN,
                task_type=TaskType.DATA_ANALYSIS,
                severity=Severity.LOW,
            ),
            route=TaskType.UNKNOWN,
            status=RouteStatus.UNSUPPORTED,
            needs_human_review=False,
            required_missing_information=[
                required_item,
            ],
        ),
    )

    decision, checks, _ = evaluate_router_case(
        case
    )

    assert checks["overall"]["passed"]

    assert (
        required_item
        in decision.missing_information
    )


def test_evaluate_router_critical_review() -> None:
    """critical问题应触发人工复核。"""

    case = EvaluationCase(
        case_id="router_test_critical",
        user_input="动力电池发生严重异常。",
        evaluators=[
            EvaluatorType.ROUTER,
        ],
        route_expectation=RouteExpectation(
            issue=RouterIssueInput(
                subsystem=Subsystem.BATTERY,
                task_type=TaskType.FAULT_DIAGNOSIS,
                severity=Severity.CRITICAL,
            ),
            route=TaskType.FAULT_DIAGNOSIS,
            status=RouteStatus.AVAILABLE,
            needs_human_review=True,
        ),
    )

    _, checks, counts = evaluate_router_case(
        case
    )

    assert checks["human_review"]["passed"]

    assert (
        counts["critical_review_correct"]
        == 1
    )