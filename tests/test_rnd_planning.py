"""研发分析路由与计划核心测试。
验证研发分析任务类型能否被通用Agent框架的路由层和计划层正确识别、接纳并生成执行计划的集成测试"""

from agent_core.planner_agent import (
    PlannerAgent,
    PlannerStatus,
)
from agent_core.router_agent import (
    RouteStatus,
    RouterAgent,
)
from agent_core.schemas import (
    PowerSystemIssue,
    Severity,
    Subsystem,
    TaskType,
)


class EmptyRegistry:
    """研发计划当前只依赖内置RAG能力。"""

    def list_skills(self) -> tuple:
        return ()


# 构造快充限流+温度偏高的场景
def make_rnd_issue() -> PowerSystemIssue:
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
            "团队分工",
        ],
        missing_information=[],
        severity=Severity.MEDIUM,
        confidence=0.9,
    )


# 路由层测试
def test_rnd_analysis_is_available() -> None:
    """研发分析任务应进入可执行路由。"""

    result = RouterAgent().route(
        make_rnd_issue()
    )

    assert result.route == TaskType.RND_ANALYSIS
    assert result.status == RouteStatus.AVAILABLE


# 计划层测试
def test_rnd_analysis_builds_rag_plan() -> None:
    """研发分析底层计划应先获取受约束证据。"""

    issue = make_rnd_issue()
    route = RouterAgent().route(issue)

    result = PlannerAgent(
        registry=EmptyRegistry()
    ).plan(issue, route)

    assert result.status == PlannerStatus.READY
    assert len(result.steps) == 1
    assert result.steps[0].target == "rag_pipeline"