"""Review与Report阶段共享的工作流数据模型。
通过Pydantic模型自校验，为这两阶段的输出结果定义严格的数据契约。
整体分为：ReviewResult（审核结果）及其状态枚举、FinalWorkflowReport及其状态枚举"""

from __future__ import annotations

from enum import Enum

from pydantic import Field, model_validator

from agent_core.schemas import (
    Severity,
    StrictBaseModel,
)
from skills.report_skill import ReportGenerationOutput
from skills.schemas import RiskLevel


class ReviewStatus(str, Enum):
    """Review Agent统一审核状态。"""

    APPROVED = "approved"      # 完全通过

    APPROVED_WITH_WARNINGS = (
        "approved_with_warnings"
    )  # 通过但有警告

    INSUFFICIENT_EVIDENCE = (
        "insufficient_evidence"
    )  # 证据不足

    EXECUTION_FAILED = "execution_failed"  # 执行失败

    HUMAN_REVIEW_REQUIRED = (
        "human_review_required"
    )  # 需人工复核

# 审核结果模型
class ReviewResult(StrictBaseModel):
    """Review Agent生成的结构化审核结果。"""

    status: ReviewStatus

    approved_for_report: bool = Field(
        description="当前结果是否具备生成结构化报告的最低条件",
    )

    findings: list[str] = Field(
        default_factory=list,
        description="经过审核后允许进入报告的关键发现",
    )

    recommendations: list[str] = Field(
        default_factory=list,
        description="经过审核后允许进入报告的建议动作",
    )

    evidence: list[str] = Field(
        default_factory=list,
        description="来源明确且能够支撑发现的证据",
    )

    unresolved_items: list[str] = Field(
        default_factory=list,
        description="尚未解决、证据不足或需要补充的信息",
    )

    risk_level: RiskLevel = Field(
        description="供Report Skill使用的统一风险等级",
    )

    issue_severity: Severity = Field(
        description="保留问题解析阶段的原始严重程度",
    )

    review_issues: list[str] = Field(
        default_factory=list,
        description="审核过程中发现的可靠性或完整性问题",
    )

    needs_human_review: bool = Field(
        description="是否需要动力系统专业人员复核",
    )

    @model_validator(mode="after")
    def validate_review_consistency(
        self,
    ) -> "ReviewResult":
        """报告许可状态必须与审核内容保持一致。"""

        if self.approved_for_report:
            if not self.findings:
                raise ValueError(
                    "允许生成报告时，findings不能为空"
                )

            if not self.recommendations:
                raise ValueError(
                    "允许生成报告时，recommendations不能为空"
                )

        if (
            self.status == ReviewStatus.APPROVED
            and not self.approved_for_report
        ):
            raise ValueError(
                "approved状态必须允许生成报告"
            )

        if (
            self.status
            in {
                ReviewStatus.INSUFFICIENT_EVIDENCE,
                ReviewStatus.EXECUTION_FAILED,
            }
            and self.approved_for_report
        ):
            raise ValueError(
                "证据不足或执行失败状态不得允许生成正常报告"
            )

        return self


# 报告生成阶段的两种状态
class ReportStatus(str, Enum):
    """Report Agent统一执行状态。"""

    GENERATED = "generated"   # 报告已生成
    BLOCKED = "blocked"       # 报告被阻断，未生成


# 最终报告的顶层包装模型
class FinalWorkflowReport(StrictBaseModel):
    """PowerAgent工作流最终报告包装模型。"""

    status: ReportStatus

    trace_id: str = Field(
        min_length=1,
        description="完整工作流追踪标识",
    )

    review_status: ReviewStatus

    issue_severity: Severity

    needs_human_review: bool

    report: ReportGenerationOutput | None = None

    blocked_reason: str | None = Field(
        default=None,
        min_length=1,
    )

    @model_validator(mode="after")
    def validate_report_consistency(
        self,
    ) -> "FinalWorkflowReport":
        """校验最终报告状态与内容的一致性。"""

        if self.status == ReportStatus.GENERATED:
            if self.report is None:
                raise ValueError(
                    "generated状态必须包含report"
                )

            if self.blocked_reason is not None:
                raise ValueError(
                    "generated状态不能包含blocked_reason"
                )

        if self.status == ReportStatus.BLOCKED:
            if self.report is not None:
                raise ValueError(
                    "blocked状态不能包含report"
                )

            if self.blocked_reason is None:
                raise ValueError(
                    "blocked状态必须说明阻断原因"
                )

        return self