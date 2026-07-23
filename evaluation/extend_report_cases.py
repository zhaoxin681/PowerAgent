"""向统一评测集增加Review和Report样本。"""

from __future__ import annotations

from pathlib import Path

from agent_core.schemas import Severity
from agent_core.workflow_models import (
    ReportStatus,
    ReviewStatus,
)
from evaluation.dataset import (
    load_evaluation_cases,
    write_evaluation_cases,
)
from evaluation.schemas import (
    EvaluationCase,
    EvaluatorType,
    ReportExpectation,
    ReviewReportScenario,
)
from skills.schemas import RiskLevel


PROJECT_ROOT = Path(__file__).resolve().parents[1]

CASE_FILE = (
    PROJECT_ROOT
    / "evaluation"
    / "test_cases.jsonl"
)


def build_report_cases() -> list[EvaluationCase]:
    """构建Review与Report核心可靠性样本。"""

    return [
        EvaluationCase(
            case_id="REPORT-001",
            user_input="分析电池单体压差异常",
            evaluators=[
                EvaluatorType.REPORT,
            ],
            tags=[
                "report",
                "approved",
                "battery_analysis",
            ],
            report_expectation=ReportExpectation(
                scenario=(
                    ReviewReportScenario
                    .BATTERY_ANALYSIS_APPROVED
                ),
                should_generate=True,
                expected_review_status=(
                    ReviewStatus.APPROVED
                ),
                expected_report_status=(
                    ReportStatus.GENERATED
                ),
                needs_human_review=False,
                expected_risk_level=RiskLevel.MEDIUM,
                expected_issue_severity=Severity.LOW,
                required_fields=[
                    "title",
                    "summary",
                    "key_findings",
                    "risk_level",
                    "recommended_actions",
                    "evidence",
                    "unresolved_items",
                ],
                required_report_concepts=[
                    ["最大压差为0.090 V"],
                    ["复核异常单体"],
                ],
                required_evidence_concepts=[
                    ["单体最大压差超过设定阈值"],
                ],
            ),
        ),
        EvaluationCase(
            case_id="REPORT-002",
            user_input="分析电池压差并保留缺失信息",
            evaluators=[
                EvaluatorType.REPORT,
            ],
            tags=[
                "report",
                "approved_with_warnings",
                "missing_information",
            ],
            report_expectation=ReportExpectation(
                scenario=(
                    ReviewReportScenario
                    .APPROVED_WITH_MISSING_INFORMATION
                ),
                should_generate=True,
                expected_review_status=(
                    ReviewStatus.APPROVED_WITH_WARNINGS
                ),
                expected_report_status=(
                    ReportStatus.GENERATED
                ),
                needs_human_review=False,
                expected_risk_level=RiskLevel.MEDIUM,
                expected_issue_severity=Severity.LOW,
                required_unresolved_concepts=[
                    ["缺少历史趋势数据"],
                ],
            ),
        ),
        EvaluationCase(
            case_id="REPORT-003",
            user_input="知识库证据不足时生成报告",
            evaluators=[
                EvaluatorType.REPORT,
            ],
            tags=[
                "report",
                "insufficient_evidence",
                "blocked",
            ],
            report_expectation=ReportExpectation(
                scenario=(
                    ReviewReportScenario
                    .RAG_INSUFFICIENT_EVIDENCE
                ),
                should_generate=False,
                expected_review_status=(
                    ReviewStatus.INSUFFICIENT_EVIDENCE
                ),
                expected_report_status=(
                    ReportStatus.BLOCKED
                ),
                needs_human_review=True,
                expected_risk_level=RiskLevel.MEDIUM,
                expected_issue_severity=Severity.MEDIUM,
                required_unresolved_concepts=[
                    ["需要补充原始运行数据"],
                ],
            ),
        ),
        EvaluationCase(
            case_id="REPORT-004",
            user_input="Skill执行失败时生成报告",
            evaluators=[
                EvaluatorType.REPORT,
            ],
            tags=[
                "report",
                "execution_failed",
                "blocked",
            ],
            report_expectation=ReportExpectation(
                scenario=(
                    ReviewReportScenario
                    .SKILL_EXECUTION_FAILED
                ),
                should_generate=False,
                expected_review_status=(
                    ReviewStatus.EXECUTION_FAILED
                ),
                expected_report_status=(
                    ReportStatus.BLOCKED
                ),
                needs_human_review=True,
                expected_risk_level=RiskLevel.MEDIUM,
                expected_issue_severity=Severity.MEDIUM,
                required_review_concepts=[
                    ["skill_execution_error"],
                ],
            ),
        ),
        EvaluationCase(
            case_id="REPORT-005",
            user_input="严重异常候选诊断报告",
            evaluators=[
                EvaluatorType.REPORT,
            ],
            tags=[
                "report",
                "critical",
                "human_review",
            ],
            report_expectation=ReportExpectation(
                scenario=(
                    ReviewReportScenario
                    .CRITICAL_DIAGNOSIS
                ),
                should_generate=True,
                expected_review_status=(
                    ReviewStatus.HUMAN_REVIEW_REQUIRED
                ),
                expected_report_status=(
                    ReportStatus.GENERATED
                ),
                needs_human_review=True,
                expected_risk_level=RiskLevel.HIGH,
                expected_issue_severity=(
                    Severity.CRITICAL
                ),
                required_report_concepts=[
                    ["候选主要原因"],
                    ["立即采取安全处置措施"],
                ],
                required_unresolved_concepts=[
                    ["规则驱动的候选诊断"],
                ],
                forbidden_claims=[
                    "已确认电芯故障",
                ],
            ),
        ),
        EvaluationCase(
            case_id="REPORT-006",
            user_input="诊断占位证据分类",
            evaluators=[
                EvaluatorType.REPORT,
            ],
            tags=[
                "report",
                "placeholder_evidence",
                "evidence_boundary",
            ],
            report_expectation=ReportExpectation(
                scenario=(
                    ReviewReportScenario
                    .DIAGNOSIS_PLACEHOLDER_EVIDENCE
                ),
                should_generate=True,
                expected_review_status=(
                    ReviewStatus.APPROVED_WITH_WARNINGS
                ),
                expected_report_status=(
                    ReportStatus.GENERATED
                ),
                needs_human_review=False,
                expected_risk_level=RiskLevel.MEDIUM,
                expected_issue_severity=Severity.MEDIUM,
                required_unresolved_concepts=[
                    ["缺少量化异常证据"],
                ],
                forbidden_claims=[
                    "已确认电芯电压一致性故障",
                ],
            ),
        ),
        EvaluationCase(
            case_id="REPORT-007",
            user_input="充电参数寻优模拟策略报告",
            evaluators=[
                EvaluatorType.REPORT,
            ],
            tags=[
                "report",
                "optimization",
                "simulation_only",
            ],
            report_expectation=ReportExpectation(
                scenario=(
                    ReviewReportScenario
                    .OPTIMIZATION_READY
                ),
                should_generate=True,
                expected_review_status=(
                    ReviewStatus.APPROVED_WITH_WARNINGS
                ),
                expected_report_status=(
                    ReportStatus.GENERATED
                ),
                needs_human_review=False,
                expected_risk_level=RiskLevel.LOW,
                expected_issue_severity=Severity.LOW,
                required_report_concepts=[
                    ["推荐充电电流为18.00 A"],
                    ["模拟云端策略状态为ready"],
                ],
                required_evidence_concepts=[
                    ["simulation_only=True"],
                ],
                required_unresolved_concepts=[
                    ["简化模型假设"],
                ],
            ),
        ),
        EvaluationCase(
            case_id="REPORT-008",
            user_input="需要人工复核的模拟策略报告",
            evaluators=[
                EvaluatorType.REPORT,
            ],
            tags=[
                "report",
                "dispatch",
                "human_review",
            ],
            report_expectation=ReportExpectation(
                scenario=(
                    ReviewReportScenario
                    .DISPATCH_REQUIRES_REVIEW
                ),
                should_generate=True,
                expected_review_status=(
                    ReviewStatus.HUMAN_REVIEW_REQUIRED
                ),
                expected_report_status=(
                    ReportStatus.GENERATED
                ),
                needs_human_review=True,
                expected_risk_level=RiskLevel.MEDIUM,
                expected_issue_severity=Severity.MEDIUM,
                required_report_concepts=[
                    [
                        "模拟云端策略状态为"
                        "requires_review"
                    ],
                ],
                required_unresolved_concepts=[
                    ["必须经过动力系统专业人员复核"],
                ],
            ),
        ),
        EvaluationCase(
            case_id="REPORT-009",
            user_input="未知工具输出报告",
            evaluators=[
                EvaluatorType.REPORT,
            ],
            tags=[
                "report",
                "unsupported_tool",
                "blocked",
            ],
            report_expectation=ReportExpectation(
                scenario=(
                    ReviewReportScenario
                    .UNSUPPORTED_TOOL_OUTPUT
                ),
                should_generate=False,
                expected_review_status=(
                    ReviewStatus.INSUFFICIENT_EVIDENCE
                ),
                expected_report_status=(
                    ReportStatus.BLOCKED
                ),
                needs_human_review=True,
                expected_risk_level=RiskLevel.MEDIUM,
                expected_issue_severity=Severity.MEDIUM,
                required_unresolved_concepts=[
                    ["暂不支持审核工具unknown_analysis"],
                ],
            ),
        ),
    ]


def main() -> None:
    """向统一评测数据集追加Review和Report样本。"""

    existing_cases = load_evaluation_cases(
        CASE_FILE
    )

    candidate_cases = build_report_cases()

    existing_ids = {
        case.case_id
        for case in existing_cases
    }

    # 只追加当前数据集中不存在的样本。
    new_cases = [
        case
        for case in candidate_cases
        if case.case_id not in existing_ids
    ]

    all_cases = [
        *existing_cases,
        *new_cases,
    ]

    write_evaluation_cases(
        CASE_FILE,
        all_cases,
    )

    print(
        f"原有样本数：{len(existing_cases)}"
    )
    print(
        f"候选Report样本数："
        f"{len(candidate_cases)}"
    )
    print(
        f"本次追加样本数：{len(new_cases)}"
    )
    print(
        f"统一样本总数：{len(all_cases)}"
    )

    if not new_cases:
        print(
            "没有追加新样本："
            "REPORT-001至REPORT-009"
            "可能已经存在于测试集中。"
        )


if __name__ == "__main__":
    main()