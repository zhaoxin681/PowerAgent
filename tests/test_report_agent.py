"""Report Agent核心功能测试。覆盖：审核通过后正常生成报告、审核未通过时阻断报告、
critical严重程度这类关键溯源信息在整个生成流程中不会丢失。"""

from agent_core.report_agent import ReportAgent
from agent_core.schemas import (
    PowerSystemIssue,
    Severity,
    Subsystem,
    TaskType,
)
from agent_core.workflow_models import (
    ReportStatus,
    ReviewResult,
    ReviewStatus,
)
from skills.schemas import RiskLevel


def make_issue() -> PowerSystemIssue:
    """构造报告测试问题。"""

    return PowerSystemIssue(
        raw_text="分析电池单体压差异常",
        subsystem=Subsystem.BATTERY,
        task_type=TaskType.FAULT_DIAGNOSIS,
        symptoms=["单体压差增大"],
        operating_conditions=[],
        user_hypotheses=[],
        requested_outputs=["异常报告"],
        missing_information=[],
        severity=Severity.MEDIUM,
        confidence=0.95,
    )

# 审核通过->正常调用Skill生成报告
def test_generate_report_from_approved_review(
) -> None:
    """审核通过后应复用Report Skill生成报告。"""

    review_result = ReviewResult(
        status=ReviewStatus.APPROVED,
        approved_for_report=True,
        findings=[
            "单体最大压差为0.09 V。"
        ],
        recommendations=[
            "复核异常单体并开展静置复测。"
        ],
        evidence=[
            "单体最大压差超过设定阈值。"
        ],
        unresolved_items=[],
        risk_level=RiskLevel.MEDIUM,
        issue_severity=Severity.MEDIUM,
        review_issues=[],
        needs_human_review=False,
    )

    result = ReportAgent().generate(
        issue=make_issue(),
        review_result=review_result,
        trace_id="trace_report_001",
    )

    assert result.status == ReportStatus.GENERATED
    assert result.report is not None

    assert result.report.key_findings == [
        "单体最大压差为0.09 V。"
    ]

    assert result.report.recommended_actions == [
        "复核异常单体并开展静置复测。"
    ]

# 审核未通过->阻断报告
def test_block_report_when_review_not_approved(
) -> None:
    """审核结果不足时不得调用正常报告流程。"""

    review_result = ReviewResult(
        status=ReviewStatus.INSUFFICIENT_EVIDENCE,
        approved_for_report=False,
        findings=[],
        recommendations=[],
        evidence=[],
        unresolved_items=[
            "缺少原始运行数据"
        ],
        risk_level=RiskLevel.MEDIUM,
        issue_severity=Severity.MEDIUM,
        review_issues=[
            "知识库证据不足"
        ],
        needs_human_review=True,
    )

    result = ReportAgent().generate(
        issue=make_issue(),
        review_result=review_result,
        trace_id="trace_report_002",
    )

    assert result.status == ReportStatus.BLOCKED
    assert result.report is None
    assert result.blocked_reason is not None

# Critical严重程度不能被RiskLevel覆盖
def test_final_report_preserves_critical_severity(
) -> None:
    """critical严重程度不能被RiskLevel映射覆盖。"""

    critical_issue = make_issue().model_copy(
        update={
            "severity": Severity.CRITICAL,
        }
    )

    review_result = ReviewResult(
        status=(
            ReviewStatus.HUMAN_REVIEW_REQUIRED
        ),
        approved_for_report=True,
        findings=[
            "检测到高风险热状态异常。"
        ],
        recommendations=[
            "立即停止相关操作并开展安全复核。"
        ],
        evidence=[
            "存在温度测点超过最高温度阈值。"
        ],
        unresolved_items=[],
        risk_level=RiskLevel.HIGH,
        issue_severity=Severity.CRITICAL,
        review_issues=[],
        needs_human_review=True,
    )

    result = ReportAgent().generate(
        issue=critical_issue,
        review_result=review_result,
        trace_id="trace_report_003",
    )

    assert result.status == ReportStatus.GENERATED
    assert (
        result.issue_severity
        == Severity.CRITICAL
    )
    assert result.needs_human_review is True
    assert result.report is not None
    assert (
        result.report.risk_level
        == RiskLevel.HIGH
    )