"""PowerAgent工作流级决策控制。"""

from __future__ import annotations

import logging
from enum import Enum

from pydantic import Field, model_validator

from agent_core.logging_config import get_logger
from agent_core.schemas import StrictBaseModel
from agent_core.state import (
    WorkflowDecision,
    WorkflowError,
    WorkflowStep,
    WorkflowStepStatus,
)
from agent_core.tool_models import (
    ToolCallingResult,
    ToolCallingStatus,
)
from rag.schemas import RAGAnswer

# 决策原因码
class DecisionReason(str, Enum):
    """Decision Agent使用的稳定原因码。"""

    STEP_SUCCEEDED = "step_succeeded"                   # 步骤成功
    PLAN_COMPLETED = "plan_completed"                   # 整个计划完成
    RETRYABLE_ERROR = "retryable_error"                 # 可重试错误
    REPLAN_REQUIRED = "replan_required"                 # 需要重新规划
    HUMAN_REVIEW_REQUIRED = "human_review_required"     # 需要人工审核
    INVALID_WORKFLOW_STATE = "invalid_workflow_state"   # 工作流状态非法
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"     # 证据不足


# 决策结果模型
class DecisionResult(StrictBaseModel):
    """Decision Agent返回的结构化控制结果。"""

    decision: WorkflowDecision

    reason_code: DecisionReason

    reason: str = Field(
        min_length=1,
        description="生成当前决策的原因",
    )

    updated_plan: list[WorkflowStep] = Field(
        description="更新步骤状态后的执行计划",
    )

    current_step_index: int = Field(
        ge=0,
        description="本次被判断的步骤索引",
    )

    next_step_index: int = Field(
        ge=0,
        description="后续工作流应使用的步骤索引",
    )

    retry_count: int = Field(
        ge=0,
        description="当前步骤已经执行的工作流级重试次数",
    )

    replan_count: int = Field(
        ge=0,
        description="本次工作流已经重新规划的次数",
    )

    needs_human_review: bool = Field(
        default=False,
        description="是否需要动力系统专业人员复核",
    )

    @model_validator(mode="after")
    def validate_control_consistency(
        self,
    ) -> "DecisionResult":
        """校验决策与步骤索引是否一致。"""

        if self.decision == WorkflowDecision.CONTINUE:
            if not self.updated_plan:
                raise ValueError(
                    "continue决策必须包含执行计划"
                )

            if (
                self.next_step_index
                != self.current_step_index + 1
            ):
                raise ValueError(
                    "continue决策必须进入下一步骤"
                )

            if self.next_step_index >= len(
                self.updated_plan
            ):
                raise ValueError(
                    "continue决策的下一步骤越界"
                )

        if self.decision == WorkflowDecision.FINISH:
            if self.next_step_index != len(
                self.updated_plan
            ):
                raise ValueError(
                    "finish决策必须指向计划末尾之后"
                )

        if self.decision == WorkflowDecision.RETRY:
            if (
                self.next_step_index
                != self.current_step_index
            ):
                raise ValueError(
                    "retry决策必须停留在当前步骤"
                )

        if self.decision == WorkflowDecision.REPLAN:
            if self.next_step_index != 0:
                raise ValueError(
                    "replan决策必须从新计划第0步开始"
                )

        return self


class DecisionAgent:
    """根据步骤执行结果控制工作流后续走向。"""

    # 重新执行相同调用没有意义，需要回到Planner调整计划。
    _REPLAN_TOOL_STATUSES = {
        ToolCallingStatus.NO_TOOL_SELECTED,
        ToolCallingStatus.UNKNOWN_TOOL,
        ToolCallingStatus.INVALID_ARGUMENTS,
        (
            ToolCallingStatus
            .MULTIPLE_TOOLS_NOT_SUPPORTED
        ),
    }

    def __init__(
        self,
        *,
        max_replans: int = 1,
        logger: logging.Logger | None = None,
    ) -> None:
        if max_replans < 0:
            raise ValueError(
                "max_replans不能小于0"
            )

        self.max_replans = max_replans
        self._logger = logger or get_logger(
            "decision_agent"
        )

    def decide(
        self,
        *,
        plan: list[WorkflowStep],
        current_step_index: int,
        retry_count: int,
        replan_count: int,
        max_retries: int,
        tool_result: ToolCallingResult | None = None,
        rag_answer: RAGAnswer | None = None,
        workflow_error: WorkflowError | None = None,
        trace_id: str | None = None,
    ) -> DecisionResult:
        """根据当前步骤唯一执行结果生成工作流决策。"""

        self._logger.info(
            "开始执行工作流决策。",
            extra={
                "event": "workflow_decision_started",
                "trace_id": trace_id,
                "current_step_index": (
                    current_step_index
                ),
                "retry_count": retry_count,
                "replan_count": replan_count,
            },
        )

        result_sources = [
            tool_result is not None,
            rag_answer is not None,
            workflow_error is not None,
        ]

        invalid_state = (
            not plan
            or current_step_index < 0
            or current_step_index >= len(plan)
            or retry_count < 0
            or replan_count < 0
            or max_retries < 0
            or sum(result_sources) != 1
        )

        if invalid_state:
            result = self._abort(
                plan=plan,
                current_step_index=max(
                    current_step_index,
                    0,
                ),
                retry_count=max(retry_count, 0),
                replan_count=max(replan_count, 0),
            )

        elif workflow_error is not None:
            result = self._from_workflow_error(
                plan=plan,
                current_step_index=(
                    current_step_index
                ),
                retry_count=retry_count,
                replan_count=replan_count,
                max_retries=max_retries,
                workflow_error=workflow_error,
            )

        elif tool_result is not None:
            result = self._from_tool_result(
                plan=plan,
                current_step_index=(
                    current_step_index
                ),
                retry_count=retry_count,
                replan_count=replan_count,
                tool_result=tool_result,
            )

        else:
            assert rag_answer is not None

            result = self._from_rag_answer(
                plan=plan,
                current_step_index=(
                    current_step_index
                ),
                retry_count=retry_count,
                replan_count=replan_count,
                rag_answer=rag_answer,
            )

        self._logger.info(
            "工作流决策完成。",
            extra={
                "event": "workflow_decision_completed",
                "trace_id": trace_id,
                "decision": result.decision.value,
                "reason_code": (
                    result.reason_code.value
                ),
                "next_step_index": (
                    result.next_step_index
                ),
                "retry_count": result.retry_count,
                "replan_count": result.replan_count,
                "needs_human_review": (
                    result.needs_human_review
                ),
            },
        )

        return result

    # 工具调用结果的三分支处理
    def _from_tool_result(
        self,
        *,
        plan: list[WorkflowStep],
        current_step_index: int,
        retry_count: int,
        replan_count: int,
        tool_result: ToolCallingResult,
    ) -> DecisionResult:
        """将Tool Calling结局映射为工作流决策。"""

        if tool_result.status == ToolCallingStatus.SUCCESS:
            return self._step_succeeded(
                plan=plan,
                current_step_index=(
                    current_step_index
                ),
                replan_count=replan_count,
                needs_human_review=(
                    tool_result.needs_human_review
                ),
            )

        if (
            tool_result.status
            in self._REPLAN_TOOL_STATUSES
        ):
            return self._replan_or_review(
                plan=plan,
                current_step_index=(
                    current_step_index
                ),
                retry_count=retry_count,
                replan_count=replan_count,
                reason=(
                    "当前工具选择或参数不能完成"
                    "计划步骤，需要重新规划。"
                ),
            )

        # LLM最终失败、Skill执行失败和输出非法等
        # 默认不进行工作流级自动重试。
        return self._human_review(
            plan=plan,
            current_step_index=current_step_index,
            retry_count=retry_count,
            replan_count=replan_count,
            reason=(
                "工具执行结果无法通过自动重试"
                "或重新规划可靠恢复。"
            ),
        )

    # RAG结果的证据充分性判断
    def _from_rag_answer(
        self,
        *,
        plan: list[WorkflowStep],
        current_step_index: int,
        retry_count: int,
        replan_count: int,
        rag_answer: RAGAnswer,
    ) -> DecisionResult:
        """根据RAG证据充分性控制后续步骤。"""

        if rag_answer.sufficient_evidence:
            return self._step_succeeded(
                plan=plan,
                current_step_index=(
                    current_step_index
                ),
                replan_count=replan_count,
                needs_human_review=(
                    rag_answer.needs_human_review
                ),
            )

        # RAG管线执行成功，但业务证据不足。
        # 当前步骤记为成功，后续诊断步骤跳过。
        updated_plan = self._update_plan(
            plan=plan,
            current_step_index=(
                current_step_index
            ),
            current_status=(
                WorkflowStepStatus.SUCCESS
            ),
            skip_remaining=True,
        )

        return DecisionResult(
            decision=WorkflowDecision.HUMAN_REVIEW,
            reason_code=(
                DecisionReason.INSUFFICIENT_EVIDENCE
            ),
            reason=(
                "RAG管线已正常完成，但当前知识库"
                "证据不足，不能继续生成可靠诊断。"
            ),
            updated_plan=updated_plan,
            current_step_index=current_step_index,
            next_step_index=current_step_index,
            retry_count=retry_count,
            replan_count=replan_count,
            needs_human_review=True,
        )

    # 系统级错误的重试判断
    def _from_workflow_error(
        self,
        *,
        plan: list[WorkflowStep],
        current_step_index: int,
        retry_count: int,
        replan_count: int,
        max_retries: int,
        workflow_error: WorkflowError,
    ) -> DecisionResult:
        """根据工作流错误的retryable标志决策。"""

        if (
            workflow_error.retryable
            and retry_count < max_retries
        ):
            updated_plan = self._update_plan(
                plan=plan,
                current_step_index=(
                    current_step_index
                ),
                current_status=(
                    WorkflowStepStatus.PENDING
                ),
            )

            return DecisionResult(
                decision=WorkflowDecision.RETRY,
                reason_code=(
                    DecisionReason.RETRYABLE_ERROR
                ),
                reason=(
                    "当前错误被标记为可恢复，"
                    "将在工作流级执行有限次数重试。"
                ),
                updated_plan=updated_plan,
                current_step_index=(
                    current_step_index
                ),
                next_step_index=current_step_index,
                retry_count=retry_count + 1,
                replan_count=replan_count,
                needs_human_review=False,
            )

        return self._human_review(
            plan=plan,
            current_step_index=current_step_index,
            retry_count=retry_count,
            replan_count=replan_count,
            reason=(
                "错误不可自动恢复，或已经达到"
                "工作流级最大重试次数。"
            ),
        )

    # 步骤成功后的继续或完成判断
    def _step_succeeded(
        self,
        *,
        plan: list[WorkflowStep],
        current_step_index: int,
        replan_count: int,
        needs_human_review: bool,
    ) -> DecisionResult:
        """标记步骤成功并继续或结束计划。"""

        updated_plan = self._update_plan(
            plan=plan,
            current_step_index=current_step_index,
            current_status=WorkflowStepStatus.SUCCESS,
        )

        next_step_index = current_step_index + 1

        # 当前步骤后仍有业务步骤。
        if next_step_index < len(updated_plan):
            return DecisionResult(
                decision=WorkflowDecision.CONTINUE,
                reason_code=(
                    DecisionReason.STEP_SUCCEEDED
                ),
                reason=(
                    "当前步骤执行成功，"
                    "继续执行下一计划步骤。"
                ),
                updated_plan=updated_plan,
                current_step_index=(
                    current_step_index
                ),
                next_step_index=next_step_index,
                retry_count=0,
                replan_count=replan_count,
                needs_human_review=(
                    needs_human_review
                ),
            )

        # 当前步骤已经是最后一个业务步骤。
        return DecisionResult(
            decision=WorkflowDecision.FINISH,
            reason_code=DecisionReason.PLAN_COMPLETED,
            reason="全部计划步骤执行完成。",
            updated_plan=updated_plan,
            current_step_index=current_step_index,
            next_step_index=len(updated_plan),
            retry_count=0,
            replan_count=replan_count,
            needs_human_review=needs_human_review,
        )

    # 重新规划的额度判断
    def _replan_or_review(
        self,
        *,
        plan: list[WorkflowStep],
        current_step_index: int,
        retry_count: int,
        replan_count: int,
        reason: str,
    ) -> DecisionResult:
        """在重新规划次数未耗尽时返回replan。"""

        if replan_count < self.max_replans:
            updated_plan = self._update_plan(
                plan=plan,
                current_step_index=(
                    current_step_index
                ),
                current_status=(
                    WorkflowStepStatus.FAILED
                ),
            )

            return DecisionResult(
                decision=WorkflowDecision.REPLAN,
                reason_code=(
                    DecisionReason.REPLAN_REQUIRED
                ),
                reason=reason,
                updated_plan=updated_plan,
                current_step_index=(
                    current_step_index
                ),
                next_step_index=0,
                retry_count=0,
                replan_count=replan_count + 1,
                needs_human_review=False,
            )

        return self._human_review(
            plan=plan,
            current_step_index=current_step_index,
            retry_count=retry_count,
            replan_count=replan_count,
            reason=(
                f"{reason}"
                "重新规划次数已经达到上限。"
            ),
        )

    # 统一的人工审核终止逻辑
    def _human_review(
        self,
        *,
        plan: list[WorkflowStep],
        current_step_index: int,
        retry_count: int,
        replan_count: int,
        reason: str,
    ) -> DecisionResult:
        """停止自动执行并转入人工复核。"""

        updated_plan = self._update_plan(
            plan=plan,
            current_step_index=current_step_index,
            current_status=WorkflowStepStatus.FAILED,
            skip_remaining=True,
        )

        return DecisionResult(
            decision=WorkflowDecision.HUMAN_REVIEW,
            reason_code=(
                DecisionReason.HUMAN_REVIEW_REQUIRED
            ),
            reason=reason,
            updated_plan=updated_plan,
            current_step_index=current_step_index,
            next_step_index=current_step_index,
            retry_count=retry_count,
            replan_count=replan_count,
            needs_human_review=True,
        )

    # 工作流状态非法时的终止
    @staticmethod
    def _abort(
        *,
        plan: list[WorkflowStep],
        current_step_index: int,
        retry_count: int,
        replan_count: int,
    ) -> DecisionResult:
        """工作流状态本身不合法时终止自动控制。"""

        return DecisionResult(
            decision=WorkflowDecision.ABORT,
            reason_code=(
                DecisionReason.INVALID_WORKFLOW_STATE
            ),
            reason=(
                "执行计划、当前步骤索引或步骤结果"
                "不符合工作流决策要求。"
            ),
            updated_plan=list(plan),
            current_step_index=current_step_index,
            next_step_index=current_step_index,
            retry_count=retry_count,
            replan_count=replan_count,
            needs_human_review=True,
        )

    # 计划步骤状态更新的核心工具方法
    @staticmethod
    def _update_plan(
        *,
        plan: list[WorkflowStep],
        current_step_index: int,
        current_status: WorkflowStepStatus,
        skip_remaining: bool = False,
    ) -> list[WorkflowStep]:
        """复制计划并更新当前及后续步骤状态。"""

        updated_plan: list[WorkflowStep] = []

        for index, step in enumerate(plan):
            if index == current_step_index:
                updated_plan.append(
                    step.model_copy(
                        update={
                            "status": current_status,
                        } # 生成一份新副本，只更新status字段
                    )
                )
                continue

            if (
                skip_remaining
                and index > current_step_index
                and step.status
                in {
                    WorkflowStepStatus.PENDING,
                    WorkflowStepStatus.RUNNING,
                }
            ):
                updated_plan.append(
                    step.model_copy(
                        update={
                            "status": (
                                WorkflowStepStatus.SKIPPED
                            )
                        }
                    )
                )
                continue

            updated_plan.append(step)

        return updated_plan