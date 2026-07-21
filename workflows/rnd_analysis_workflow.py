"""研发分析工作流适配层。"""

from __future__ import annotations

import hashlib
from typing import Any, Protocol

from agent_core.schemas import (
    PowerSystemIssue,
    Severity,
    Subsystem,
    TaskType,
)
from agent_core.state import (
    PowerAgentState,
    TraceEventStatus,
    WorkflowError,
    WorkflowNode,
    WorkflowTraceEvent,
)
from agent_core.workflow_models import ReviewStatus
from workflows.rnd_models import (
    EvidenceSource,
    KnownFact,
    MissingInformation,
    RndAnalysisContext,
    RndAnalysisRequest,
    RndPriority,
)


class PowerAgentWorkflowProtocol(Protocol):
    """研发适配层依赖的最小通用工作流接口。"""

    def invoke(
        self,
        raw_input: str,
        *,
        trace_id: str | None = None,
        max_retries: int = 2,
        skill_inputs: (
            dict[str, dict[str, Any]] | None
        ) = None,
    ) -> PowerAgentState:
        """运行通用PowerAgent工作流。"""

# 通用Agent输出->领域专用结构化模型的转换枢纽
class RndAnalysisWorkflow:
    """调用通用工作流并构建研发分析上下文。"""

    def __init__(
        self,
        *,
        base_workflow: PowerAgentWorkflowProtocol,
    ) -> None:
        self.base_workflow = base_workflow

    def build_context(
        self,
        request: RndAnalysisRequest,
        *,
        skill_inputs: (
            dict[str, dict[str, Any]] | None
        ) = None,
        max_retries: int = 2,
    ) -> RndAnalysisContext:
        """运行基础工作流并转换为研发分析上下文。"""

        # 调用上游工作流，捕获异常
        try:
            state = self.base_workflow.invoke(
                request.raw_input,
                trace_id=request.trace_id,
                max_retries=max_retries,
                skill_inputs=skill_inputs,
            )
        except Exception as exc:
            return self._build_failed_context(
                request=request,
                error_type=type(exc).__name__,
            )

        # 检验必要产出是否存在
        issue = state.get("issue")

        if issue is None:
            return self._build_failed_context(
                request=request,
                error_type="MissingPowerSystemIssue",
            )

        # 从state中提取各类中间产物
        review_result = state.get("review_result")
        rag_answers = list(
            state.get("rag_answers", [])
        )
        workflow_errors = list(
            state.get("errors", [])
        )

        # 把通用产物“蒸馏”成研发分析专用格式
        known_facts = self._build_known_facts(
            issue=issue,
            review_result=review_result,
        )

        missing_information = (
            self._build_missing_information(
                issue=issue,
                rag_answers=rag_answers,
                review_result=review_result,
            )
        )

        # 综合判断上游是否失败
        upstream_finished = state.get(
            "is_finished",
            False,
        )

        upstream_failed = bool(workflow_errors)

        if (
            review_result is not None
            and review_result.status
            == ReviewStatus.EXECUTION_FAILED
        ):
            upstream_failed = True

        if not upstream_finished:
            upstream_failed = True

        # 生成失败原因
        failure_reason = (
            self._build_failure_reason(
                workflow_errors=workflow_errors,
                upstream_finished=upstream_finished,
            )
            if upstream_failed
            else None
        )

        # 汇总是否需要人工复核
        needs_human_review = bool(
            state.get("needs_human_review", False)
            or (
                review_result is not None
                and review_result.needs_human_review
            )
            or upstream_failed
        )

        return RndAnalysisContext(
            request=request,
            issue=issue,
            tool_results=list(
                state.get("tool_results", [])
            ),
            rag_answers=rag_answers,
            review_result=review_result,
            final_report=state.get("final_report"),
            workflow_errors=workflow_errors,
            execution_trace=list(
                state.get("execution_trace", [])
            ),
            known_facts=known_facts,
            missing_information=missing_information,
            upstream_finished=upstream_finished,
            upstream_failed=upstream_failed,
            needs_human_review=needs_human_review,
            failure_reason=failure_reason,
        )

    # Review发现->研发事实
    @classmethod
    def _build_known_facts(
        cls,
        *,
        issue: PowerSystemIssue,
        review_result: Any,
    ) -> list[KnownFact]:
        """将Review阶段可信发现转换为研发事实。"""

        if review_result is None:
            return []

        facts: list[KnownFact] = []

        for index, finding in enumerate(
            review_result.findings
        ):
            facts.append(
                KnownFact(
                    fact_id=cls._stable_id(
                        prefix="fact",
                        index=index,
                        text=finding,
                    ),
                    description=finding,
                    subsystem=issue.subsystem,
                    source=(
                        EvidenceSource
                        .WORKFLOW_REVIEW
                    ),
                    source_reference=(
                        "review_result"
                    ),
                    is_verified=False,
                    confidence=0.8,
                )
            )

        return facts

    # 三路信息缺口汇总+去重
    @classmethod
    def _build_missing_information(
        cls,
        *,
        issue: PowerSystemIssue,
        rag_answers: list[Any],
        review_result: Any,
    ) -> list[MissingInformation]:
        """汇总Issue、RAG和Review中的缺失信息。"""

        # 问题结构化时发现的缺口
        raw_items: list[tuple[str, RndPriority]] = [
            (item, RndPriority.P1)
            for item in issue.missing_information
        ]

        # 知识检索环节发现的缺口
        for answer in rag_answers:
            raw_items.extend(
                (
                    item,
                    RndPriority.P1,
                )
                for item
                in answer.missing_information
            )

        # 审核阶段未解决的事项
        if review_result is not None:
            raw_items.extend(
                (
                    item,
                    RndPriority.P1,
                )
                for item
                in review_result.unresolved_items
            )

        deduplicated: list[
            tuple[str, RndPriority] 
        ] = [] # 统一收集成(描述，优先级)元组列表
        seen: set[str] = set()

        for description, priority in raw_items:
            normalized = description.strip()

            if (
                not normalized
                or normalized in seen
            ):
                continue

            seen.add(normalized)
            deduplicated.append(
                (normalized, priority)
            ) 

        return [
            MissingInformation(
                item_id=cls._stable_id(
                    prefix="missing",
                    index=index,
                    text=description,
                ),
                description=description,
                impact=(
                    "该信息缺失会降低根因判断和"
                    "验证实验设计的可靠性"
                ),
                priority=priority,
                required_for_confirmation=True,
                related_hypothesis_ids=[],
            )
            for index, (
                description,
                priority,
            ) in enumerate(deduplicated)
        ]

    # 脱敏的失败说明
    @staticmethod
    def _build_failure_reason(
        *,
        workflow_errors: list[WorkflowError],
        upstream_finished: bool,
    ) -> str:
        """构造不暴露内部异常堆栈的失败说明。"""

        reasons = [
            f"{error.error_code}：{error.message}"
            for error in workflow_errors
        ]

        if not upstream_finished:
            reasons.append(
                "上游工作流未正常完成"
            )

        return "；".join(
            dict.fromkeys(reasons)
        ) # 去重

    # 统一的失败态构造器
    @classmethod
    def _build_failed_context(
        cls,
        *,
        request: RndAnalysisRequest,
        error_type: str,
    ) -> RndAnalysisContext:
        """基础工作流抛出异常时构造受限上下文。"""

        message = (
            "通用PowerAgent工作流执行失败："
            f"{error_type}"
        )

        error = WorkflowError(
            node=WorkflowNode.ERROR_HANDLER,
            error_code="rnd_upstream_failed",
            message=message,
            retryable=False,
        )

        issue = PowerSystemIssue(
            raw_text=request.raw_input,
            subsystem=Subsystem.UNKNOWN,
            task_type=TaskType.RND_ANALYSIS,
            symptoms=[],
            operating_conditions=(
                request.operating_conditions
            ),
            user_hypotheses=[],
            requested_outputs=(
                request.requested_deliverables
            ),
            missing_information=[
                "需要重新执行通用工作流"
            ],
            severity=Severity.UNKNOWN,
            confidence=0.0,
        )

        return RndAnalysisContext(
            request=request,
            issue=issue,
            tool_results=[],
            rag_answers=[],
            review_result=None,
            final_report=None,
            workflow_errors=[error],
            execution_trace=[
                WorkflowTraceEvent(
                    node=WorkflowNode.ERROR_HANDLER,
                    status=TraceEventStatus.FAILED,
                    detail=message,
                )
            ],
            known_facts=[],
            missing_information=[
                MissingInformation(
                    item_id=(
                        "missing_upstream_result"
                    ),
                    description=(
                        "缺少通用工作流分析结果"
                    ),
                    impact=(
                        "无法继续自动生成可靠根因"
                        "和验证实验"
                    ),
                    priority=RndPriority.P0,
                    required_for_confirmation=True,
                    related_hypothesis_ids=[],
                )
            ],
            upstream_finished=False,
            upstream_failed=True,
            needs_human_review=True,
            failure_reason=message,
        )

    @staticmethod
    def _stable_id(
        *,
        prefix: str,
        index: int,
        text: str,
    ) -> str:
        """根据内容生成稳定且可测试的对象ID。"""

        fingerprint = hashlib.sha256(
            text.encode("utf-8")
        ).hexdigest()[:10]

        return f"{prefix}_{index}_{fingerprint}"