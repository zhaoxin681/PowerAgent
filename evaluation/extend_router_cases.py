"""向统一评测集增加Router确定性评测样本。"""

from __future__ import annotations

from pathlib import Path

from agent_core.router_agent import RouteStatus
from agent_core.schemas import (
    Severity,
    Subsystem,
    TaskType,
)
from evaluation.dataset import (
    load_evaluation_cases,
    write_evaluation_cases,
)
from evaluation.schemas import (
    EvaluationCase,
    EvaluatorType,
    RouteExpectation,
    RouterIssueInput,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]

CASE_FILE = (
    PROJECT_ROOT
    / "evaluation"
    / "test_cases.jsonl"
)


def build_router_cases() -> list[EvaluationCase]:
    """构建Router四类核心决策分支样本。"""

    return [
        EvaluationCase(
            case_id="ROUTER-001",
            user_input="查询动力电池SOC的定义。",
            evaluators=[
                EvaluatorType.ROUTER,
            ],
            tags=[
                "router",
                "available",
                "knowledge_query",
            ],
            route_expectation=RouteExpectation(
                issue=RouterIssueInput(
                    subsystem=Subsystem.BATTERY,
                    task_type=TaskType.KNOWLEDGE_QUERY,
                    severity=Severity.LOW,
                ),
                route=TaskType.KNOWLEDGE_QUERY,
                status=RouteStatus.AVAILABLE,
                needs_human_review=False,
            ),
        ),
        EvaluationCase(
            case_id="ROUTER-002",
            user_input="分析一组电池单体电压。",
            evaluators=[
                EvaluatorType.ROUTER,
            ],
            tags=[
                "router",
                "available",
                "data_analysis",
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
        ),
        EvaluationCase(
            case_id="ROUTER-003",
            user_input="冷却液严重超温，请进行故障诊断。",
            evaluators=[
                EvaluatorType.ROUTER,
            ],
            tags=[
                "router",
                "available",
                "critical",
                "human_review",
            ],
            route_expectation=RouteExpectation(
                issue=RouterIssueInput(
                    subsystem=Subsystem.THERMAL,
                    task_type=TaskType.FAULT_DIAGNOSIS,
                    severity=Severity.CRITICAL,
                ),
                route=TaskType.FAULT_DIAGNOSIS,
                status=RouteStatus.AVAILABLE,
                needs_human_review=True,
            ),
        ),
        EvaluationCase(
            case_id="ROUTER-004",
            user_input="优化快充电流和冷却功率。",
            evaluators=[
                EvaluatorType.ROUTER,
            ],
            tags=[
                "router",
                "available",
                "parameter_optimization",
            ],
            route_expectation=RouteExpectation(
                issue=RouterIssueInput(
                    subsystem=Subsystem.CHARGING,
                    task_type=(
                        TaskType.PARAMETER_OPTIMIZATION
                    ),
                    severity=Severity.MEDIUM,
                ),
                route=TaskType.PARAMETER_OPTIMIZATION,
                status=RouteStatus.AVAILABLE,
                needs_human_review=False,
            ),
        ),
        EvaluationCase(
            case_id="ROUTER-005",
            user_input="制定跨团队研发验证方案。",
            evaluators=[
                EvaluatorType.ROUTER,
            ],
            tags=[
                "router",
                "available",
                "rnd_analysis",
            ],
            route_expectation=RouteExpectation(
                issue=RouterIssueInput(
                    subsystem=Subsystem.MULTI_SYSTEM,
                    task_type=TaskType.RND_ANALYSIS,
                    severity=Severity.HIGH,
                ),
                route=TaskType.RND_ANALYSIS,
                status=RouteStatus.AVAILABLE,
                needs_human_review=False,
            ),
            notes=(
                "Router当前只对critical直接触发人工复核，"
                "high将在后续业务层继续判断。"
            ),
        ),
        EvaluationCase(
            case_id="ROUTER-006",
            user_input="生成一份动力系统分析报告。",
            evaluators=[
                EvaluatorType.ROUTER,
            ],
            tags=[
                "router",
                "available",
                "report_generation",
            ],
            route_expectation=RouteExpectation(
                issue=RouterIssueInput(
                    subsystem=Subsystem.MULTI_SYSTEM,
                    task_type=TaskType.REPORT_GENERATION,
                    severity=Severity.MEDIUM,
                ),
                route=TaskType.REPORT_GENERATION,
                status=RouteStatus.AVAILABLE,
                needs_human_review=False,
            ),
        ),
        EvaluationCase(
            case_id="ROUTER-007",
            user_input="请查询这个系统的工作原理。",
            evaluators=[
                EvaluatorType.ROUTER,
            ],
            tags=[
                "router",
                "unsupported",
                "unknown_subsystem",
            ],
            route_expectation=RouteExpectation(
                issue=RouterIssueInput(
                    subsystem=Subsystem.UNKNOWN,
                    task_type=TaskType.KNOWLEDGE_QUERY,
                    severity=Severity.LOW,
                ),
                route=TaskType.UNKNOWN,
                status=RouteStatus.UNSUPPORTED,
                needs_human_review=False,
                required_missing_information=[
                    "明确问题涉及的动力系统对象或子系统",
                ],
            ),
        ),
        EvaluationCase(
            case_id="ROUTER-008",
            user_input="电池最近表现异常。",
            evaluators=[
                EvaluatorType.ROUTER,
            ],
            tags=[
                "router",
                "needs_information",
                "unknown_task",
            ],
            route_expectation=RouteExpectation(
                issue=RouterIssueInput(
                    subsystem=Subsystem.BATTERY,
                    task_type=TaskType.UNKNOWN,
                    severity=Severity.MEDIUM,
                ),
                route=TaskType.UNKNOWN,
                status=RouteStatus.NEEDS_INFORMATION,
                needs_human_review=False,
                required_missing_information=[
                    (
                        "明确希望执行知识查询、数据分析、"
                        "故障诊断、参数寻优或报告生成"
                    ),
                ],
            ),
        ),
        EvaluationCase(
            case_id="ROUTER-009",
            user_input="未知动力设备发生严重安全问题。",
            evaluators=[
                EvaluatorType.ROUTER,
            ],
            tags=[
                "router",
                "unsupported",
                "critical",
                "human_review",
            ],
            route_expectation=RouteExpectation(
                issue=RouterIssueInput(
                    subsystem=Subsystem.UNKNOWN,
                    task_type=TaskType.FAULT_DIAGNOSIS,
                    severity=Severity.CRITICAL,
                ),
                route=TaskType.UNKNOWN,
                status=RouteStatus.UNSUPPORTED,
                needs_human_review=True,
                required_missing_information=[
                    "明确问题涉及的动力系统对象或子系统",
                ],
            ),
        ),
        EvaluationCase(
            case_id="ROUTER-010",
            user_input="分析电池单体电压，但尚未上传数据。",
            evaluators=[
                EvaluatorType.ROUTER,
            ],
            tags=[
                "router",
                "available",
                "missing_information",
            ],
            route_expectation=RouteExpectation(
                issue=RouterIssueInput(
                    subsystem=Subsystem.BATTERY,
                    task_type=TaskType.DATA_ANALYSIS,
                    severity=Severity.LOW,
                    missing_information=[
                        "上传原始单体电压数据",
                    ],
                ),
                route=TaskType.DATA_ANALYSIS,
                status=RouteStatus.AVAILABLE,
                needs_human_review=False,
                required_missing_information=[
                    "上传原始单体电压数据",
                ],
            ),
            notes=(
                "Router当前保留缺失信息，但不会因为业务参数"
                "缺失而阻断已识别的任务类型。"
            ),
        ),
    ]


def main() -> None:
    """将Router样本追加到统一测试集。"""

    existing_cases = load_evaluation_cases(
        CASE_FILE
    )

    new_cases = build_router_cases()

    existing_ids = {
        case.case_id
        for case in existing_cases
    }

    duplicate_ids = sorted(
        case.case_id
        for case in new_cases
        if case.case_id in existing_ids
    )

    if duplicate_ids:
        raise ValueError(
            "以下Router样本已经存在："
            + ", ".join(duplicate_ids)
        )

    all_cases = [
        *existing_cases,
        *new_cases,
    ]

    write_evaluation_cases(
        CASE_FILE,
        all_cases,
    )

    print(f"原有样本：{len(existing_cases)}")
    print(f"新增Router样本：{len(new_cases)}")
    print(f"统一样本总数：{len(all_cases)}")


if __name__ == "__main__":
    main()