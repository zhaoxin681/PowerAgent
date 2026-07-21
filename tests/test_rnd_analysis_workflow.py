"""研发分析上下文适配层核心测试。"""

from typing import Any

from agent_core.schemas import (
    PowerSystemIssue,
    Severity,
    Subsystem,
    TaskType,
)
from agent_core.workflow_models import (
    ReviewResult,
    ReviewStatus,
)
from rag.schemas import RAGAnswer
from skills.schemas import RiskLevel
from workflows.rnd_analysis_workflow import (
    RndAnalysisWorkflow,
)
from workflows.rnd_models import (
    EvidenceSource,
    RndAnalysisRequest,
)


class FakeBaseWorkflow:
    """返回指定状态或异常的假工作流。"""

    def __init__(
        self,
        *,
        state: dict[str, Any] | None = None,
        error: Exception | None = None,
    ) -> None:
        self.state = state
        self.error = error
        self.received_trace_id: str | None = None

    def invoke(
        self,
        raw_input: str,
        *,
        trace_id: str | None = None,
        max_retries: int = 2,
        skill_inputs: (
            dict[str, dict[str, Any]] | None
        ) = None,
    ) -> dict[str, Any]:
        self.received_trace_id = trace_id

        if self.error is not None:
            raise self.error

        assert self.state is not None
        return self.state


def make_request() -> RndAnalysisRequest:
    return RndAnalysisRequest(
        raw_input="快充后段限流且温度偏高",
        trace_id="trace-rnd-001",
        affected_scope=["部分车辆"],
        available_data=["充电日志"],
        operating_conditions=[],
        requested_deliverables=[
            "根因分析",
            "验证实验",
        ],
    )


def make_issue() -> PowerSystemIssue:
    return PowerSystemIssue(
        raw_text="快充后段限流且温度偏高",
        subsystem=Subsystem.MULTI_SYSTEM,
        task_type=TaskType.RND_ANALYSIS,
        symptoms=[
            "充电电流下降",
            "最高温度偏高",
        ],
        operating_conditions=[],
        user_hypotheses=[],
        requested_outputs=[
            "根因分析",
            "验证实验",
        ],
        missing_information=[
            "缺少冷却液流量"
        ],
        severity=Severity.MEDIUM,
        confidence=0.9,
    )


def make_review() -> ReviewResult:
    return ReviewResult(
        status=ReviewStatus.APPROVED_WITH_WARNINGS,
        approved_for_report=True,
        findings=[
            "最高温度达到52℃",
        ],
        recommendations=[
            "复核冷却回路",
        ],
        evidence=[
            "温度分析规则证据",
        ],
        unresolved_items=[
            "缺少水泵转速",
        ],
        risk_level=RiskLevel.MEDIUM,
        issue_severity=Severity.MEDIUM,
        review_issues=[],
        needs_human_review=False,
    )


def test_build_context_from_reviewed_state() -> None:
    """审核发现应转换为研发事实。"""

    fake_workflow = FakeBaseWorkflow(
        state={
            "trace_id": "trace-rnd-001",
            "issue": make_issue(),
            "tool_results": [],
            "rag_answers": [],
            "review_result": make_review(),
            "final_report": None,
            "errors": [],
            "execution_trace": [],
            "needs_human_review": False,
            "is_finished": True,
        }
    )

    workflow = RndAnalysisWorkflow(
        base_workflow=fake_workflow
    )

    context = workflow.build_context(
        make_request()
    )

    assert context.upstream_finished is True
    assert context.upstream_failed is False
    assert len(context.known_facts) == 1
    assert (
        context.known_facts[0].source
        == EvidenceSource.WORKFLOW_REVIEW
    )
    assert (
        fake_workflow.received_trace_id
        == "trace-rnd-001"
    )


def test_missing_information_is_merged() -> None:
    """Issue、RAG和Review缺失信息应合并去重。"""

    rag_answer = RAGAnswer(
        question="为什么快充限流",
        answer="当前证据不足",
        citations=[],
        confidence=0.0,
        sufficient_evidence=False,
        missing_information=[
            "缺少冷却液流量",
            "缺少环境温度",
        ],
        needs_human_review=True,
    )

    fake_workflow = FakeBaseWorkflow(
        state={
            "trace_id": "trace-rnd-001",
            "issue": make_issue(),
            "tool_results": [],
            "rag_answers": [rag_answer],
            "review_result": make_review(),
            "final_report": None,
            "errors": [],
            "execution_trace": [],
            "needs_human_review": True,
            "is_finished": True,
        }
    )

    context = RndAnalysisWorkflow(
        base_workflow=fake_workflow
    ).build_context(make_request())

    descriptions = {
        item.description
        for item in context.missing_information
    }

    assert descriptions == {
        "缺少冷却液流量",
        "缺少环境温度",
        "缺少水泵转速",
    }
    assert context.needs_human_review is True


def test_upstream_exception_builds_failed_context() -> None:
    """上游异常不应直接导致研发流程崩溃。"""

    fake_workflow = FakeBaseWorkflow(
        error=RuntimeError("模拟异常")
    )

    context = RndAnalysisWorkflow(
        base_workflow=fake_workflow
    ).build_context(make_request())

    assert context.upstream_finished is False
    assert context.upstream_failed is True
    assert context.needs_human_review is True
    assert context.failure_reason is not None
    assert context.known_facts == []