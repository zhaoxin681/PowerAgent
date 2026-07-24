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
from workflows.rnd_models import (
    ExperimentCriterion,
    RndAnalysisStatus,
    RndGenerationOutput,
    RndPriority,
    RootCauseHypothesis,
    RootCauseStatus,
    TeamAssignment,
    TeamName,
    ValidationExperiment,
)
from agent_core.llm_client import (
    LLMTruncatedResponseError,
)


class FakeRndLLM:
    """返回预设研发方案的结构化LLM。"""

    def __init__(
        self,
        result: RndGenerationOutput,
    ) -> None:
        self.result = result

    def parse_structured(
        self,
        *,
        developer_prompt: str,
        user_input: str,
        response_model: type,
    ) -> RndGenerationOutput:
        assert (
            response_model
            is RndGenerationOutput
        )
        assert "known_facts" in user_input
        return self.result


class FakeTruncatedRndLLM:
    """模拟LLM结构化响应被截断。"""

    def parse_structured(
        self,
        *,
        developer_prompt: str,
        user_input: str,
        response_model: type,
    ) -> RndGenerationOutput:
        raise LLMTruncatedResponseError(
            "模拟结构化响应被截断"
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


def test_missing_issue_builds_failed_context() -> None:
    """缺少结构化问题时应返回受控失败上下文。"""

    fake_workflow = FakeBaseWorkflow(
        state={
            "trace_id": "trace-rnd-001",
            "issue": None,
        }
    )

    context = RndAnalysisWorkflow(
        base_workflow=fake_workflow
    ).build_context(make_request())

    assert context.upstream_finished is False
    assert context.upstream_failed is True
    assert context.needs_human_review is True
    assert (
        context.issue.task_type
        == TaskType.RND_ANALYSIS
    )
    assert context.failure_reason is not None
    assert (
        "MissingPowerSystemIssue"
        in context.failure_reason
    )


def test_analyze_builds_full_rnd_result() -> None:
    """研发上下文应生成完整根因、实验和团队任务。"""

    base_workflow = FakeBaseWorkflow(
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

    context_workflow = RndAnalysisWorkflow(
        base_workflow=base_workflow
    )
    context = context_workflow.build_context(
        make_request()
    )

    fact_id = context.known_facts[0].fact_id

    generated = RndGenerationOutput(
        summary="冷却能力不足是优先验证方向",
        hypotheses=[
            RootCauseHypothesis(
                hypothesis_id=(
                    "hyp_cooling_limit"
                ),
                description=(
                    "高SOC阶段冷却能力不足"
                    "可能触发充电限流"
                ),
                subsystem=Subsystem.THERMAL,
                status=RootCauseStatus.SUPPORTED,
                priority=RndPriority.P1,
                supporting_fact_ids=[fact_id],
                contradicting_fact_ids=[],
                reasoning=(
                    "温升与充电限流同步出现"
                ),
                confidence=0.75,
                potential_impact=(
                    "延长充电时间并增加热风险"
                ),
                needs_human_review=False,
            )
        ],
        experiments=[
            ValidationExperiment(
                experiment_id="exp_cooling_ab",
                title="冷却能力A/B对比实验",
                linked_hypothesis_ids=[
                    "hyp_cooling_limit"
                ],
                objective="验证冷却能力与限流关系",
                required_inputs=[
                    "充电电流",
                    "温度",
                ],
                controlled_variables=[
                    "环境温度",
                    "初始SOC",
                ],
                steps=[
                    "固定初始条件",
                    "执行两档冷却能力快充",
                ],
                observed_metrics=[
                    "最高温度",
                    "后段充电电流",
                ],
                expected_observation=(
                    "冷却增强后温度降低且限流减轻"
                ),
                criteria=[
                    ExperimentCriterion(
                        metric="后段充电电流",
                        measurement_method=(
                            "对比两组充电日志"
                        ),
                        pass_condition=(
                            "增强冷却后电流明显提高"
                        ),
                        fail_condition=(
                            "两组结果无明显差异"
                        ),
                    )
                ],
                stop_conditions=[
                    "温度超过安全阈值"
                ],
                safety_requirements=[],
                deliverables=[
                    "实验日志",
                    "对比分析报告",
                ],
                risk_level=RiskLevel.MEDIUM,
                needs_human_approval=False,
            )
        ],
        team_assignments=[
            TeamAssignment(
                assignment_id=(
                    "assign_cooling_test"
                ),
                experiment_ids=[
                    "exp_cooling_ab"
                ],
                owner=TeamName.TEST_VALIDATION,
                collaborators=[
                    TeamName.THERMAL_MANAGEMENT
                ],
                reviewers=[
                    TeamName.FUNCTIONAL_SAFETY
                ],
                task="完成冷却能力A/B快充实验",
                input_dependencies=[
                    "试验车辆和冷却标定"
                ],
                deliverables=[
                    "实验日志",
                    "分析报告",
                ],
                completion_criteria=[
                    "两组数据完整且能够比较"
                ],
                blockers=[],
            )
        ],
        dependencies=[],
        risks=[],
        overall_risk_level=RiskLevel.MEDIUM,
        needs_human_review=False,
        unresolved_items=[],
    )

    workflow = RndAnalysisWorkflow(
        base_workflow=base_workflow,
        llm_client=FakeRndLLM(generated),
    )

    result = workflow.analyze(make_request())

    assert result.status == RndAnalysisStatus.COMPLETED
    assert len(result.hypotheses) == 1
    assert len(result.experiments) == 1
    assert len(result.team_assignments) == 1
    assert (
        result.hypotheses[0]
        .supporting_fact_ids
        == [fact_id]
    )


def test_truncated_llm_response_returns_failed_result() -> None:
    """LLM响应被截断时应返回结构化失败结果。"""

    knowledge_issue = make_issue().model_copy(
        update={
            "task_type": (
                TaskType.KNOWLEDGE_QUERY
            )
        }
    )

    base_workflow = FakeBaseWorkflow(
        state={
            "trace_id": "trace-rnd-001",
            "issue": knowledge_issue,
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
        base_workflow=base_workflow,
        llm_client=FakeTruncatedRndLLM(),
    )

    result = workflow.analyze(make_request())

    assert (
        result.status
        == RndAnalysisStatus.EXECUTION_FAILED
    )
    assert (
            result.trace_id
            == "trace-rnd-001"
        )
    assert (
        result.issue.task_type
        == TaskType.RND_ANALYSIS
    )
    assert result.needs_human_review is True
    assert result.failure_reason is not None
    assert (
        "LLMTruncatedResponseError"
        in result.failure_reason
    )