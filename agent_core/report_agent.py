"""PowerAgent审核后结构化报告生成。
承接前面ReviewAgent产出的ReviewResult，把审核通过的内容真正转换成一份结构化的最终报告。"""

from __future__ import annotations

import logging

from agent_core.logging_config import get_logger
from agent_core.schemas import PowerSystemIssue
from agent_core.workflow_models import (
    FinalWorkflowReport,
    ReportStatus,
    ReviewResult,
)
from skills.exceptions import SkillError
from skills.report_skill import (
    ReportGenerationInput,
    ReportGenerationSkill,
)
from skills.schemas import SkillContext


class ReportAgent:
    """将通过审核的结果转换为最终结构化报告。"""

    def __init__(
        self,
        *,
        report_skill: (
            ReportGenerationSkill | None
        ) = None,
        logger: logging.Logger | None = None,
    ) -> None:
        self.report_skill = (
            report_skill
            or ReportGenerationSkill()
        )

        self._logger = logger or get_logger(
            "report_agent"
        )

    # 报告生成主流程：前置拦截->调用Skill->异常处理
    def generate(
        self,
        *,
        issue: PowerSystemIssue,
        review_result: ReviewResult,
        trace_id: str,
        device_id: str | None = None,
    ) -> FinalWorkflowReport:
        """根据ReviewResult生成最终报告。"""

        self._logger.info(
            "开始生成工作流最终报告。",
            extra={
                "event": (
                    "workflow_report_started"
                ),
                "trace_id": trace_id,
                "review_status": (
                    review_result.status.value
                ),
                "approved_for_report": (
                    review_result
                    .approved_for_report
                ),
            },
        )

        if not review_result.approved_for_report:
            return self._blocked_report(
                trace_id=trace_id,
                review_result=review_result,
                reason=(
                    "审核结果缺少可靠发现或建议，"
                    "不能生成正常结构化报告。"
                ),
            )

        # 构造Skill的输入参数
        report_input = ReportGenerationInput(
            original_question=issue.raw_text,
            findings=review_result.findings,
            risk_level=review_result.risk_level,
            recommendations=(
                review_result.recommendations
            ),
            evidence=review_result.evidence,
            unresolved_items=(
                review_result.unresolved_items
                + review_result.review_issues
            ),
            device_id=device_id,
        )

        # 调用Skill并捕获异常
        try:
            report_output = self.report_skill.run(
                arguments=report_input,
                context=SkillContext(
                    trace_id=trace_id,
                    source="report_agent",
                    metadata={
                        "review_status": (
                            review_result.status.value
                        ),
                    },
                ),
            )

        except SkillError as exc:
            self._logger.error(
                "结构化报告Skill执行失败。",
                extra={
                    "event": (
                        "workflow_report_failed"
                    ),
                    "trace_id": trace_id,
                    "error_code": exc.code,
                },
            )

            return self._blocked_report(
                trace_id=trace_id,
                review_result=review_result,
                reason=(
                    "ReportGenerationSkill执行失败，"
                    "需要人工生成或复核报告。"
                ),
            )

        # 成功路径：构造最终报告
        result = FinalWorkflowReport(
            status=ReportStatus.GENERATED,
            trace_id=trace_id,
            review_status=review_result.status,
            issue_severity=(
                review_result.issue_severity
            ),
            needs_human_review=(
                review_result.needs_human_review
            ),
            report=report_output,
            blocked_reason=None,
        )

        self._logger.info(
            "工作流最终报告生成完成。",
            extra={
                "event": (
                    "workflow_report_completed"
                ),
                "trace_id": trace_id,
                "report_status": result.status.value,
                "risk_level": (
                    report_output.risk_level.value
                ),
                "needs_human_review": (
                    result.needs_human_review
                ),
            },
        )

        return result

    # 统一的阻断报告构造器
    @staticmethod
    def _blocked_report(
        *,
        trace_id: str,
        review_result: ReviewResult,
        reason: str,
    ) -> FinalWorkflowReport:
        """构造受限报告结果。"""

        return FinalWorkflowReport(
            status=ReportStatus.BLOCKED,
            trace_id=trace_id,
            review_status=review_result.status,
            issue_severity=(
                review_result.issue_severity
            ),
            needs_human_review=True,
            report=None,
            blocked_reason=reason,
        )