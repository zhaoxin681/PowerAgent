"""PowerAgent多Agent工作流Mock演示。"""

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
from rag.schemas import (
    RAGAnswer,
    RAGCitation,
)
from skills.battery_analysis_skill import (
    BatteryAnalysisSkill,
)
from skills.diagnosis_skill import DiagnosisSkill


class DemoIssueParser:
    """演示用固定问题解析器。"""

    def parse(
        self,
        user_input: str,
    ) -> PowerSystemIssue:
        return PowerSystemIssue(
            raw_text=user_input,
            subsystem=Subsystem.BATTERY,
            task_type=TaskType.FAULT_DIAGNOSIS,
            symptoms=["单体压差增大"],
            operating_conditions=[],
            user_hypotheses=[],
            requested_outputs=[
                "候选原因",
                "结构化报告",
            ],
            missing_information=[],
            severity=Severity.MEDIUM,
            confidence=0.95,
        )


class DemoRAGPipeline:
    """演示用证据约束RAG管线。"""

    def answer(
        self,
        question: str,
        **_: object,
    ) -> RAGAnswer:
        return RAGAnswer(
            question=question,
            answer=(
                "单体压差增大可能反映"
                "电芯状态或测量链路差异。"
            ),
            citations=[
                RAGCitation(
                    chunk_id="demo_chunk_1",
                    document_id="demo_battery_doc",
                    title="电池一致性诊断知识",
                    section_path="电压差异",
                    page_number=None,
                    supported_claim=(
                        "压差增大可能反映状态差异"
                    ),
                    evidence_text=(
                        "单体压差增大可能反映"
                        "电芯状态或测量链路差异。"
                    ),
                )
            ],
            confidence=0.9,
            sufficient_evidence=True,
            missing_information=[],
            needs_human_review=False,
        )


def main() -> None:
    """运行完整Mock工作流。"""

    registry = SkillRegistry()
    registry.register(
        BatteryAnalysisSkill()
    )
    registry.register(
        DiagnosisSkill()
    )

    workflow = PowerAgentWorkflow(
        issue_parser=DemoIssueParser(),
        router_agent=RouterAgent(),
        planner_agent=PlannerAgent(
            registry=registry
        ),
        decision_agent=DecisionAgent(),
        review_agent=ReviewAgent(),
        report_agent=ReportAgent(),
        registry=registry,
        rag_pipeline=DemoRAGPipeline(),
    )

    state = workflow.invoke(
        "电池单体压差增大，请分析可能原因",
        trace_id="workflow_demo_001",
        skill_inputs={
            "battery_analysis": {
                "cell_voltages_v": [
                    3.54,
                    3.63,
                    3.62,
                    3.61,
                ],
                "spread_threshold_v": 0.05,
            }
        },
    )

    print(
        state["final_report"]
        .model_dump_json(indent=2)
    )

    print("\n工作流执行轨迹：")

    for event in state["execution_trace"]:
        print(
            f"- {event.node.value}: "
            f"{event.status.value} | "
            f"{event.detail}"
        )


if __name__ == "__main__":
    main()