"""Planner Agent核心功能测试。
验证 知识问答计划、故障诊断多步计划、DEFERRED路由不生成计划、多系统分析需要更多信息
、以及“能力白名单校验”。"""

from agent_core.planner_agent import (
    PlannerAgent,
    PlannerStatus,
)
from agent_core.router_agent import (
    RouteStatus,
    RouterDecision,
)
from agent_core.schemas import (
    OperatingCondition,
    PowerSystemIssue,
    Severity,
    Subsystem,
    TaskType,
)
from skills.schemas import SkillDefinition


DEFAULT_SKILL_NAMES = (
    "knowledge_lookup",
    "battery_analysis",
    "thermal_analysis",
    "charging_analysis",
    "diagnosis",
    "report_generation",
)

# 测试替身
class FakeRegistry:
    """只实现Planner所需最小接口的测试注册表。"""

    def __init__(
        self,
        skill_names: tuple[str, ...],
    ) -> None:
        self._definitions = tuple(
            SkillDefinition(
                name=name,
                description=f"{name}测试Skill",
                version="1.0.0",
                input_model_name="TestInput",
                output_model_name="TestOutput",
            )
            for name in skill_names
        )

    def list_skills(
        self,
    ) -> tuple[SkillDefinition, ...]:
        return self._definitions

# 结构化问题的测试工厂
def make_issue(
    *,
    subsystem: Subsystem,
    task_type: TaskType,
    with_context: bool = False,
) -> PowerSystemIssue:
    """构造Planner测试需要的结构化问题。"""

    return PowerSystemIssue(
        raw_text="测试动力系统任务",
        subsystem=subsystem,
        task_type=task_type,
        symptoms=(
            ["单体压差增大"]
            if with_context
            else []
        ),
        operating_conditions=(
            [
                OperatingCondition(
                    name="SOC",
                    value="80",
                    unit="%",
                )
            ]
            if with_context
            else []
        ),
        user_hypotheses=[],
        requested_outputs=[],
        missing_information=[],
        severity=Severity.MEDIUM,
        confidence=0.95,
    )

# Router决策的测试工厂
def make_available_decision(
    task_type: TaskType,
) -> RouterDecision:
    """构造可执行Router结果。"""

    return RouterDecision(
        route=task_type,
        status=RouteStatus.AVAILABLE,
        reason="当前任务可执行",
        missing_information=[],
        needs_human_review=False,
    )

"""
五个测试用例
"""
# 1. 知识问答->单步RAG计划
def test_plan_knowledge_query_uses_rag() -> None:
    """知识问答应优先进入证据约束RAG管线。"""

    issue = make_issue(
        subsystem=Subsystem.BATTERY,
        task_type=TaskType.KNOWLEDGE_QUERY,
    )

    result = PlannerAgent(
        registry=FakeRegistry(
            DEFAULT_SKILL_NAMES
        )
    ).plan(
        issue,
        make_available_decision(
            TaskType.KNOWLEDGE_QUERY
        ),
    )

    assert result.status == PlannerStatus.READY
    assert len(result.steps) == 1
    assert result.steps[0].target == "rag_pipeline"
    assert result.steps[0].sequence == 0

# 2. 电池故障诊断->三步有序计划
def test_plan_battery_diagnosis_builds_ordered_steps(
) -> None:
    """电池诊断应组合分析、RAG和候选诊断。"""

    issue = make_issue(
        subsystem=Subsystem.BATTERY,
        task_type=TaskType.FAULT_DIAGNOSIS,
        with_context=True,
    )

    result = PlannerAgent(
        registry=FakeRegistry(
            DEFAULT_SKILL_NAMES
        )
    ).plan(
        issue,
        make_available_decision(
            TaskType.FAULT_DIAGNOSIS
        ),
    )

    assert result.status == PlannerStatus.READY

    assert [
        step.target
        for step in result.steps
    ] == [
        "battery_analysis",
        "rag_pipeline",
        "diagnosis",
    ]

    assert [
        step.sequence
        for step in result.steps
    ] == [0, 1, 2]

    assert [
        step.step_id
        for step in result.steps
    ] == [
        "step_0",
        "step_1",
        "step_2",
    ]

# 3. DEFERRED路由->无步骤
def test_plan_deferred_route_has_no_steps() -> None:
    """后续阶段任务不得生成虚假执行计划。"""

    issue = make_issue(
        subsystem=Subsystem.BATTERY,
        task_type=(
            TaskType.PARAMETER_OPTIMIZATION
        ),
    )

    decision = RouterDecision(
        route=TaskType.PARAMETER_OPTIMIZATION,
        status=RouteStatus.DEFERRED,
        reason="第五周接入参数寻优能力",
        missing_information=[],
        needs_human_review=False,
    )

    result = PlannerAgent(
        registry=FakeRegistry(
            DEFAULT_SKILL_NAMES
        )
    ).plan(
        issue,
        decision,
    )

    assert result.status == PlannerStatus.DEFERRED
    assert result.steps == []

# 4. 多系统数据分析->需要更多信息
def test_plan_multi_system_analysis_needs_information(
) -> None:
    """多系统分析不能在数据边界不明时调用全部Skill。"""

    issue = make_issue(
        subsystem=Subsystem.MULTI_SYSTEM,
        task_type=TaskType.DATA_ANALYSIS,
    )

    result = PlannerAgent(
        registry=FakeRegistry(
            DEFAULT_SKILL_NAMES
        )
    ).plan(
        issue,
        make_available_decision(
            TaskType.DATA_ANALYSIS
        ),
    )

    assert (
        result.status
        == PlannerStatus.NEEDS_INFORMATION
    )
    assert result.steps == []
    assert result.missing_information

# 5. 引用未注册Skill->配置错误
def test_plan_detects_unregistered_skill() -> None:
    """计划引用未注册Skill时应返回配置错误。"""

    registered_without_diagnosis = tuple(
        name
        for name in DEFAULT_SKILL_NAMES
        if name != "diagnosis"
    )

    issue = make_issue(
        subsystem=Subsystem.BATTERY,
        task_type=TaskType.FAULT_DIAGNOSIS,
        with_context=True,
    )

    result = PlannerAgent(
        registry=FakeRegistry(
            registered_without_diagnosis
        )
    ).plan(
        issue,
        make_available_decision(
            TaskType.FAULT_DIAGNOSIS
        ),
    )

    assert (
        result.status
        == PlannerStatus.CONFIGURATION_ERROR
    )
    assert result.steps == []
    assert result.missing_capabilities == [
        "diagnosis"
    ]
    assert result.needs_human_review is True