"""Review和Report联合评测核心测试。"""

from evaluation.evaluate_report import (
    evaluate_report_case,
)
from evaluation.schemas import (
    EvaluationCase,
    EvaluatorType,
    ReportExpectation,
    ReviewReportScenario,
)
from agent_core.schemas import Severity
from agent_core.workflow_models import (
    ReportStatus,
    ReviewStatus,
)
from skills.schemas import RiskLevel


def test_approved_review_preserves_report_fields() -> None:
    """审核通过后报告应完整保留核心字段。"""

    case = EvaluationCase(
        case_id="report_test_approved",
        user_input="分析电池单体压差异常",
        evaluators=[
            EvaluatorType.REPORT,
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
        ),
    )

    _, _, checks, _ = evaluate_report_case(
        case
    )

    assert checks["overall"]["passed"]

    assert checks[
        "findings_preservation"
    ]["passed"]

    assert checks[
        "evidence_preservation"
    ]["passed"]


def test_insufficient_evidence_blocks_report() -> None:
    """证据不足时应阻断报告。"""

    case = EvaluationCase(
        case_id="report_test_blocked",
        user_input="电池异常原因是什么？",
        evaluators=[
            EvaluatorType.REPORT,
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
        ),
    )

    _, _, checks, _ = evaluate_report_case(
        case
    )

    assert checks["overall"]["passed"]

    assert (
        checks["generation"]["actual"]
        is False
    )


def test_critical_severity_is_preserved() -> None:
    """critical严重程度和人工复核状态不能丢失。"""

    case = EvaluationCase(
        case_id="report_test_critical",
        user_input="严重动力电池异常",
        evaluators=[
            EvaluatorType.REPORT,
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
        ),
    )

    _, _, checks, _ = evaluate_report_case(
        case
    )

    assert checks[
        "severity_preservation"
    ]["passed"]

    assert checks[
        "human_review"
    ]["passed"]