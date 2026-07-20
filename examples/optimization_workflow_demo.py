"""第五周参数寻优多Agent工作流演示。

使用真实Router、Planner、Decision、Review、Report和业务Skill，
完成数字孪生预测、参数寻优、模拟云端策略生成及报告输出。

本Demo使用固定问题解析器，不调用真实LLM；
参数寻优流程不需要调用RAG。
"""

from __future__ import annotations

from typing import Any

from agent_core.decision_agent import DecisionAgent
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
from agent_core.skill_registry import SkillRegistry
from agent_core.workflow import PowerAgentWorkflow
from rag.schemas import RAGAnswer
from skills import create_default_skills


class FixedOptimizationIssueParser:
    """返回固定参数寻优任务的演示解析器。"""

    def parse(
        self,
        user_input: str,
    ) -> PowerSystemIssue:
        """将演示输入转换为参数寻优结构化问题。"""

        return PowerSystemIssue(
            raw_text=user_input,
            subsystem=Subsystem.CHARGING,
            task_type=TaskType.PARAMETER_OPTIMIZATION,
            symptoms=[],
            operating_conditions=[],
            user_hypotheses=[],
            requested_outputs=[
                "未来状态预测",
                "推荐充电参数",
                "模拟云端策略",
            ],
            missing_information=[],
            severity=Severity.LOW,
            confidence=1.0,
        )


class UnusedRAGPipeline:
    """参数寻优流程中不应被调用的RAG替身。"""

    def __init__(self) -> None:
        self.call_count = 0

    def answer(
        self,
        question: str,
        **_: Any,
    ) -> RAGAnswer:
        """阻止参数寻优流程意外进入RAG。"""

        self.call_count += 1

        raise RuntimeError(
            "参数寻优工作流不应调用RAGPipeline"
        )


def create_registry() -> SkillRegistry:
    """创建包含全部默认Skill的注册表。"""

    registry = SkillRegistry()

    for skill in create_default_skills():
        registry.register(skill)

    return registry


def build_workflow(
    registry: SkillRegistry,
    rag_pipeline: UnusedRAGPipeline,
) -> PowerAgentWorkflow:
    """创建第五周完整LangGraph工作流。"""

    return PowerAgentWorkflow(
        issue_parser=FixedOptimizationIssueParser(),
        router_agent=RouterAgent(),
        planner_agent=PlannerAgent(
            registry=registry,
        ),
        decision_agent=DecisionAgent(
            max_replans=1,
        ),
        review_agent=ReviewAgent(),
        report_agent=ReportAgent(),
        registry=registry,
        rag_pipeline=rag_pipeline,
    )


def build_skill_inputs() -> dict[str, dict[str, Any]]:
    """构造三个业务Skill的输入。"""

    return {
        # 单一基准方案预测
        "digital_twin": {
            "current_soc_pct": 80.0,
            "current_pack_voltage_v": 380.0,
            "current_maximum_temperature_c": 30.0,
            "current_charging_current_a": 20.0,
            "candidate_charging_current_a": 15.0,
            "forecast_minutes": 20.0,
            "cooling_power_w": 0.0,
            "maximum_pack_voltage_v": 400.0,
            "maximum_charging_current_a": 50.0,
        },

        # 多候选参数寻优
        "parameter_optimization": {
            "current_soc_pct": 80.0,
            "current_pack_voltage_v": 380.0,
            "current_maximum_temperature_c": 30.0,
            "current_charging_current_a": 20.0,
            "candidate_charging_currents_a": [
                10.0,
                15.0,
                20.0,
                25.0,
            ],
            "candidate_cooling_powers_w": [
                0.0,
                20.0,
            ],
            "forecast_minutes": 20.0,
            "maximum_pack_voltage_v": 400.0,
            "maximum_charging_current_a": 50.0,
        },

        # 模拟下发层配置
        # optimization_status、recommended_candidate和
        # optimization_reason由Executor从上游自动补充
        "cloud_dispatch": {
            "current_risk_level": "normal",
            "strategy_id": "CHARGE-STRATEGY-DEMO-001",
            "strategy_version": "1.0.0",
            "target_device_id": "PACK-DEMO-001",
            "valid_for_minutes": 30,
            "allow_automatic_dispatch": True,
            "force_manual_review": False,
            "maximum_dispatch_current_a": 30.0,
            "maximum_dispatch_cooling_power_w": 50.0,
        },
    }


def print_plan(state: dict[str, Any]) -> None:
    """打印Planner生成及执行后的步骤状态。"""

    print("\n执行计划：")

    for step in state.get("plan", []):
        print(
            f"  {step.sequence}. "
            f"{step.target} "
            f"[{step.status.value}]"
        )


def print_tool_results(
    state: dict[str, Any],
) -> None:
    """打印三个核心Skill的结构化结果。"""

    print("\nSkill执行结果：")

    for result in state.get(
        "tool_results",
        [],
    ):
        print(
            f"\n--- {result.tool_name} ---"
        )
        print(f"status: {result.status.value}")

        if result.output is not None:
            print(result.output)

        if result.error_code is not None:
            print(
                "error: "
                f"{result.error_code} / "
                f"{result.error_message}"
            )


def print_review_and_report(
    state: dict[str, Any],
) -> None:
    """打印审核结果和最终报告。"""

    review_result = state.get(
        "review_result"
    )

    print("\nReview结果：")

    if review_result is None:
        print("未生成ReviewResult。")
    else:
        print(
            review_result.model_dump_json(
                indent=2,
            )
        )

    final_report = state.get(
        "final_report"
    )

    print("\n最终报告：")

    if final_report is None:
        print("未生成FinalWorkflowReport。")
    else:
        print(
            final_report.model_dump_json(
                indent=2,
            )
        )


def main() -> None:
    """运行第五周参数寻优完整工作流。"""

    registry = create_registry()
    rag_pipeline = UnusedRAGPipeline()

    workflow = build_workflow(
        registry,
        rag_pipeline,
    )

    state = workflow.invoke(
        (
            "根据当前SOC、电压和温度状态，"
            "预测候选充电方案，推荐安全参数，"
            "并生成模拟云端策略。"
        ),
        trace_id="week5_optimization_demo_001",
        skill_inputs=build_skill_inputs(),
    )

    print("第五周参数寻优工作流执行完成。")
    print(f"trace_id: {state['trace_id']}")
    print(
        "route: "
        f"{state.get('route')}"
    )
    print(
        "planner_status: "
        f"{state.get('planner_status')}"
    )
    print(
        "decision: "
        f"{state.get('decision')}"
    )
    print(
        "is_finished: "
        f"{state.get('is_finished')}"
    )
    print(
        "needs_human_review: "
        f"{state.get('needs_human_review')}"
    )
    print(
        "rag_call_count: "
        f"{rag_pipeline.call_count}"
    )

    print_plan(state)
    print_tool_results(state)
    print_review_and_report(state)


if __name__ == "__main__":
    main()