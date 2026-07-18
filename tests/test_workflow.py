"""PowerAgent LangGraph端到端核心测试。"""

from agent_core.decision_agent import (
    DecisionAgent,
)
from agent_core.planner_agent import PlannerAgent
from agent_core.report_agent import ReportAgent
from agent_core.review_agent import ReviewAgent
from agent_core.router_agent import RouterAgent
from agent_core.schemas import (
    PowerSystemIssue,
    Severity,
    Subsystem,
    TaskType,
)
from agent_core.skill_registry import (
    SkillRegistry,
)
from agent_core.workflow import (
    PowerAgentWorkflow,
)
from agent_core.workflow_models import (
    ReportStatus,
)
from rag.schemas import (
    RAGAnswer,
    RAGCitation,
)
from skills.battery_analysis_skill import (
    BatteryAnalysisSkill,
)
from skills.diagnosis_skill import DiagnosisSkill


class FakeIssueParser:
    """返回固定PowerSystemIssue的测试解析器。"""

    def __init__(
        self,
        issue: PowerSystemIssue,
    ) -> None:
        self.issue = issue

    def parse(
        self,
        user_input: str,
    ) -> PowerSystemIssue:
        return self.issue.model_copy(
            update={"raw_text": user_input}
        )


class FakeRAGPipeline:
    """返回固定RAGAnswer的测试管线。"""

    def __init__(
        self,
        answer: RAGAnswer,
    ) -> None:
        self.answer_result = answer
        self.call_count = 0

    def answer(
        self,
        question: str,
        **_: object,
    ) -> RAGAnswer:
        self.call_count += 1

        return self.answer_result.model_copy(
            update={"question": question}
        )


def make_issue(
    *,
    task_type: TaskType,
    subsystem: Subsystem = Subsystem.BATTERY,
    with_symptom: bool = False,
) -> PowerSystemIssue:
    """创建工作流测试问题。"""

    return PowerSystemIssue(
        raw_text="测试动力系统任务",
        subsystem=subsystem,
        task_type=task_type,
        symptoms=(
            ["单体压差增大"]
            if with_symptom
            else []
        ),
        operating_conditions=[],
        user_hypotheses=[],
        requested_outputs=[],
        missing_information=[],
        severity=Severity.MEDIUM,
        confidence=0.95,
    )


def make_rag_answer() -> RAGAnswer:
    """创建证据充分的RAG回答。"""

    return RAGAnswer(
        question="测试问题",
        answer=(
            "单体压差增大可能反映"
            "电芯状态差异。"
        ),
        citations=[
            RAGCitation(
                chunk_id="battery_chunk_1",
                document_id="battery_doc",
                title="电池一致性知识",
                section_path="电压一致性",
                page_number=None,
                supported_claim=(
                    "压差增大可能反映状态差异"
                ),
                evidence_text=(
                    "单体压差增大可能反映"
                    "电芯状态差异。"
                ),
            )
        ],
        confidence=0.9,
        sufficient_evidence=True,
        missing_information=[],
        needs_human_review=False,
    )


def build_workflow(
    *,
    issue: PowerSystemIssue,
    registry: SkillRegistry,
) -> tuple[
    PowerAgentWorkflow,
    FakeRAGPipeline,
]:
    """创建不访问真实API和向量库的工作流。"""

    rag_pipeline = FakeRAGPipeline(
        make_rag_answer()
    )

    workflow = PowerAgentWorkflow(
        issue_parser=FakeIssueParser(issue),
        router_agent=RouterAgent(),
        planner_agent=PlannerAgent(
            registry=registry
        ),
        decision_agent=DecisionAgent(
            max_replans=1
        ),
        review_agent=ReviewAgent(),
        report_agent=ReportAgent(),
        registry=registry,
        rag_pipeline=rag_pipeline,
    )

    return workflow, rag_pipeline


def test_knowledge_workflow_generates_report(
) -> None:
    """知识问答应完成RAG、审核和报告生成。"""

    workflow, rag_pipeline = build_workflow(
        issue=make_issue(
            task_type=TaskType.KNOWLEDGE_QUERY
        ),
        registry=SkillRegistry(),
    )

    state = workflow.invoke(
        "单体压差增大可能说明什么？",
        trace_id="workflow_knowledge_001",
    )

    assert state["is_finished"] is True
    assert rag_pipeline.call_count == 1

    assert (
        state["final_report"].status
        == ReportStatus.GENERATED
    )

    assert len(state["rag_answers"]) == 1
    assert state["review_result"].findings


def test_battery_analysis_workflow(
) -> None:
    """电池数据分析应调用真实Battery Skill。"""

    registry = SkillRegistry()
    registry.register(
        BatteryAnalysisSkill()
    )

    workflow, rag_pipeline = build_workflow(
        issue=make_issue(
            task_type=TaskType.DATA_ANALYSIS
        ),
        registry=registry,
    )

    state = workflow.invoke(
        "分析这组电池单体电压",
        trace_id="workflow_battery_001",
        skill_inputs={
            "battery_analysis": {
                "cell_voltages_v": [
                    3.55,
                    3.64,
                    3.61,
                ],
                "spread_threshold_v": 0.05,
            }
        },
    )

    assert rag_pipeline.call_count == 0
    assert len(state["tool_results"]) == 1

    assert (
        state["tool_results"][0].tool_name
        == "battery_analysis"
    )

    assert (
        state["tool_results"][0].status.value
        == "success"
    )

    assert (
        state["final_report"].status
        == ReportStatus.GENERATED
    )


def test_diagnosis_workflow_executes_three_steps(
) -> None:
    """故障诊断应执行分析、RAG和Diagnosis。"""

    registry = SkillRegistry()
    registry.register(
        BatteryAnalysisSkill()
    )
    registry.register(
        DiagnosisSkill()
    )

    workflow, rag_pipeline = build_workflow(
        issue=make_issue(
            task_type=TaskType.FAULT_DIAGNOSIS,
            with_symptom=True,
        ),
        registry=registry,
    )

    state = workflow.invoke(
        "电池单体压差增大，请判断可能原因",
        trace_id="workflow_diagnosis_001",
        skill_inputs={
            "battery_analysis": {
                "cell_voltages_v": [
                    3.54,
                    3.63,
                    3.62,
                ],
                "spread_threshold_v": 0.05,
            }
        },
    )

    assert rag_pipeline.call_count == 1
    assert len(state["tool_results"]) == 2
    assert len(state["rag_answers"]) == 1

    assert [
        result.tool_name
        for result in state["tool_results"]
    ] == [
        "battery_analysis",
        "diagnosis",
    ]

    diagnosis_result = state[
        "tool_results"
    ][1]

    assert diagnosis_result.output is not None

    assert (
        diagnosis_result.output[
            "primary_cause"
        ]
        == "电芯电压一致性异常"
    )

    assert (
        state["final_report"].status
        == ReportStatus.GENERATED
    )


def test_deferred_optimization_is_blocked(
) -> None:
    """第五周能力不得在第四周产生虚假结果。"""

    workflow, rag_pipeline = build_workflow(
        issue=make_issue(
            task_type=(
                TaskType.PARAMETER_OPTIMIZATION
            )
        ),
        registry=SkillRegistry(),
    )

    state = workflow.invoke(
        "请优化电池诊断阈值",
        trace_id="workflow_deferred_001",
    )

    assert rag_pipeline.call_count == 0
    assert state["tool_results"] == []
    assert state["rag_answers"] == []

    assert (
        state["final_report"].status
        == ReportStatus.BLOCKED
    )

    assert state["needs_human_review"] is True