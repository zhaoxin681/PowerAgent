"""PowerAgent结构化执行计划生成器。承接Router Agent的路由结果，针对不同任务类型
生成具体的、可执行的步骤序列，并在生成计划前/后做出大量的一致性校验和能力校验，确保
交给Executor节点的计划一定是合法且可执行的。"""

from __future__ import annotations

import logging
from enum import Enum
from typing import Protocol

from pydantic import Field, model_validator

from agent_core.logging_config import get_logger
from agent_core.router_agent import (
    RouteStatus,
    RouterDecision,
)
from agent_core.schemas import (
    PowerSystemIssue,
    StrictBaseModel,
    Subsystem,
    TaskType,
)
from agent_core.state import WorkflowStep
from skills.schemas import SkillDefinition


class SkillRegistryProtocol(Protocol):
    """Planner依赖的最小Skill Registry接口。"""

    def list_skills(
        self,
    ) -> tuple[SkillDefinition, ...]:
        """返回系统当前注册的Skill元数据。"""


# 计划的五种状态
class PlannerStatus(str, Enum):
    """Planner Agent统一计划状态。"""

    READY = "ready"
    DEFERRED = "deferred"
    NEEDS_INFORMATION = "needs_information"
    UNSUPPORTED = "unsupported"
    CONFIGURATION_ERROR = "configuration_error"


# 计划结果模型（含自校验逻辑）
class PlannerResult(StrictBaseModel):
    """Planner Agent返回的结构化计划结果。"""

    route: TaskType = Field(
        description="本次计划对应的任务类型",
    )

    status: PlannerStatus = Field(
        description="当前计划是否可以执行",
    )

    steps: list[WorkflowStep] = Field(
        default_factory=list,
        description="按照sequence排序的执行步骤",
    )

    reason: str = Field(
        min_length=1,
        description="计划状态及步骤设计的简要原因",
    )

    missing_information: list[str] = Field(
        default_factory=list,
        description="继续执行仍然缺少的用户信息",
    )

    missing_capabilities: list[str] = Field(
        default_factory=list,
        description="计划需要但系统尚未注册的执行能力",
    )

    needs_human_review: bool = Field(
        default=False,
        description="是否需要动力系统专业人员复核",
    )

    @model_validator(mode="after")
    def validate_plan_consistency(
        self,
    ) -> "PlannerResult":
        """可执行计划必须有步骤，其他状态不得携带步骤。"""
        # READY必须有步骤，非READY绝不能有步骤。
        if (
            self.status == PlannerStatus.READY
            and not self.steps
        ):
            raise ValueError(
                "status为ready时，steps不能为空"
            )

        if (
            self.status != PlannerStatus.READY
            and self.steps
        ):
            raise ValueError(
                "非ready状态不得包含可执行步骤"
            )
        # 步骤序号必须从0开始连续递增
        sequences = [
            step.sequence
            for step in self.steps
        ]

        if sequences != list(range(len(self.steps))):
            raise ValueError(
                "steps的sequence必须从0开始连续递增"
            )
        # step_id不能重复
        step_ids = [
            step.step_id
            for step in self.steps
        ]

        if len(step_ids) != len(set(step_ids)):
            raise ValueError(
                "steps中的step_id不得重复"
            )

        return self


class PlannerAgent:
    """根据路由结果生成受约束的结构化执行计划。"""

    # 1. 类级配置
    RAG_TARGET = "rag_pipeline"
    DIGITAL_TWIN_TARGET = "digital_twin"
    OPTIMIZATION_TARGET = "parameter_optimization"
    CLOUD_DISPATCH_TARGET = "cloud_dispatch"

    _ANALYSIS_SKILL_BY_SUBSYSTEM = {
        Subsystem.BATTERY: "battery_analysis",
        Subsystem.THERMAL: "thermal_analysis",
        Subsystem.CHARGING: "charging_analysis",
    }

    # 构造函数（依赖注入）
    def __init__(
        self,
        *,
        registry: SkillRegistryProtocol,
        logger: logging.Logger | None = None,
    ) -> None:
        self.registry = registry
        self._logger = logger or get_logger(
            "planner_agent"
        )

    # 对外入口（日志埋点+调用核心逻辑）
    def plan(
        self,
        issue: PowerSystemIssue,
        router_decision: RouterDecision,
        *,
        trace_id: str | None = None,
    ) -> PlannerResult:
        """根据结构化问题和路由决策生成执行计划。"""

        self._logger.info(
            "开始生成工作流执行计划。",
            extra={
                "event": "workflow_plan_started",
                "trace_id": trace_id,
                "subsystem": issue.subsystem.value,
                "task_type": issue.task_type.value,
                "route": router_decision.route.value,
                "route_status": (
                    router_decision.status.value
                ),
            },
        )

        result = self._build_plan(
            issue=issue,
            router_decision=router_decision,
        )

        self._logger.info(
            "工作流执行计划生成完成。",
            extra={
                "event": "workflow_plan_completed",
                "trace_id": trace_id,
                "planner_status": result.status.value,
                "route": result.route.value,
                "step_count": len(result.steps),
                "missing_capability_count": len(
                    result.missing_capabilities
                ),
                "needs_human_review": (
                    result.needs_human_review
                ),
            },
        )

        return result

    # 核心决策流程（分层判断）
    def _build_plan(
        self,
        *,
        issue: PowerSystemIssue,
        router_decision: RouterDecision,
    ) -> PlannerResult:
        """执行确定性计划生成规则。"""

        # 处理Router给出的非AVAILABLE状态，直接返回
        non_available_result = (
            self._handle_non_available_route(
                router_decision
            )
        )

        # 路由结果与问题任务类型的一致性校验
        if non_available_result is not None:
            return non_available_result

        if router_decision.route != issue.task_type:
            return PlannerResult(
                route=router_decision.route,
                status=(
                    PlannerStatus.CONFIGURATION_ERROR
                ),
                reason=(
                    "Router路由结果与结构化问题中的"
                    "任务类型不一致。"
                ),
                missing_capabilities=[],
                missing_information=[],
                needs_human_review=True,
            )

        # 按任务类型分发到各自的计划构建逻辑
        if issue.task_type == TaskType.KNOWLEDGE_QUERY:
            steps = self._build_knowledge_plan()

        elif issue.task_type == TaskType.DATA_ANALYSIS:
            return self._build_data_analysis_result(
                issue=issue,
                router_decision=router_decision,
            )

        elif issue.task_type == TaskType.FAULT_DIAGNOSIS:
            return self._build_diagnosis_result(
                issue=issue,
                router_decision=router_decision,
            )

        elif issue.task_type == TaskType.PARAMETER_OPTIMIZATION:
            return self._build_parameter_optimization_result(
                issue=issue,
                router_decision=router_decision,
            )

        elif issue.task_type == TaskType.REPORT_GENERATION:
            return self._build_report_generation_result(
                issue=issue,
                router_decision=router_decision,
            )

        else:
            return PlannerResult(
                route=issue.task_type,
                status=PlannerStatus.UNSUPPORTED,
                reason=(
                    "当前Planner没有该任务类型的"
                    "可执行计划模板。"
                ),
                missing_information=list(
                    issue.missing_information
                ),
                needs_human_review=(
                    router_decision.needs_human_review
                ),
            )

        return self._validate_and_build_ready_result(
            issue=issue,
            router_decision=router_decision,
            steps=steps,
        )

    def _handle_non_available_route(
        self,
        router_decision: RouterDecision,
    ) -> PlannerResult | None:
        """将Router的非可执行状态转换为Planner状态。"""

        if router_decision.status == RouteStatus.AVAILABLE:
            return None

        status_mapping = {
            RouteStatus.DEFERRED: (
                PlannerStatus.DEFERRED
            ),
            RouteStatus.NEEDS_INFORMATION: (
                PlannerStatus.NEEDS_INFORMATION
            ),
            RouteStatus.UNSUPPORTED: (
                PlannerStatus.UNSUPPORTED
            ),
        }

        return PlannerResult(
            route=router_decision.route,
            status=status_mapping[
                router_decision.status
            ],
            reason=router_decision.reason,
            missing_information=list(
                router_decision.missing_information
            ),
            needs_human_review=(
                router_decision.needs_human_review
            ),
        )

    # 数据分析任务的计划生成
    def _build_data_analysis_result(
        self,
        *,
        issue: PowerSystemIssue,
        router_decision: RouterDecision,
    ) -> PlannerResult:
        """生成单子系统数据分析计划。"""
        # 多任务->需要更多信息
        if issue.subsystem == Subsystem.MULTI_SYSTEM:
            return PlannerResult(
                route=issue.task_type,
                status=PlannerStatus.NEEDS_INFORMATION,
                reason=(
                    "多系统数据分析需要明确各子系统"
                    "分别提供了哪些测量数据。"
                ),
                missing_information=(
                    self._merge_missing_information(
                        issue.missing_information,
                        (
                            "明确电池、热管理或充电子系统"
                            "对应的数据字段"
                        ),
                    )
                ),
                needs_human_review=(
                    router_decision.needs_human_review
                ),
            )
        # 查表找不到对应Sill->不支持
        skill_name = (
            self._ANALYSIS_SKILL_BY_SUBSYSTEM.get(
                issue.subsystem
            )
        )

        if skill_name is None:
            return PlannerResult(
                route=issue.task_type,
                status=PlannerStatus.UNSUPPORTED,
                reason=(
                    "当前没有与该子系统匹配的"
                    "数据分析Skill。"
                ),
                missing_information=list(
                    issue.missing_information
                ),
                needs_human_review=(
                    router_decision.needs_human_review
                ),
            )
        # 正常情况->生成单步计划
        steps = [
            self._make_step(
                sequence=0,
                action="执行动力系统测量数据分析",
                target=skill_name,
                input_keys=["issue"],
                output_key="tool_results",
            )
        ]

        return self._validate_and_build_ready_result(
            issue=issue,
            router_decision=router_decision,
            steps=steps,
        )

    # 故障诊断任务的计划生成
    def _build_diagnosis_result(
        self,
        *,
        issue: PowerSystemIssue,
        router_decision: RouterDecision,
    ) -> PlannerResult:
        """生成数据分析、知识检索和候选诊断计划。"""
        # 缺乏问题上下文->需要更多信息
        has_problem_context = bool(
            issue.symptoms
            or issue.operating_conditions
            or issue.user_hypotheses
        )

        if not has_problem_context:
            return PlannerResult(
                route=issue.task_type,
                status=PlannerStatus.NEEDS_INFORMATION,
                reason=(
                    "故障诊断缺少异常现象、运行条件"
                    "或用户已有原因假设。"
                ),
                missing_information=(
                    self._merge_missing_information(
                        issue.missing_information,
                        (
                            "补充异常现象、测量数据"
                            "或故障发生时的运行条件"
                        ),
                    )
                ),
                needs_human_review=(
                    router_decision.needs_human_review
                ),
            )
        # 多系统->需要更多信息
        if issue.subsystem == Subsystem.MULTI_SYSTEM:
            return PlannerResult(
                route=issue.task_type,
                status=PlannerStatus.NEEDS_INFORMATION,
                reason=(
                    "多系统故障诊断需要先明确"
                    "各子系统的异常证据。"
                ),
                missing_information=(
                    self._merge_missing_information(
                        issue.missing_information,
                        (
                            "明确各子系统的异常现象、"
                            "测量数据和关联关系"
                        ),
                    )
                ),
                needs_human_review=(
                    router_decision.needs_human_review
                ),
            )
        # 无匹配的分析Skill->不支持
        analysis_skill = (
            self._ANALYSIS_SKILL_BY_SUBSYSTEM.get(
                issue.subsystem
            )
        )

        if analysis_skill is None:
            return PlannerResult(
                route=issue.task_type,
                status=PlannerStatus.UNSUPPORTED,
                reason=(
                    "当前没有与该子系统匹配的"
                    "分析和诊断执行链。"
                ),
                missing_information=list(
                    issue.missing_information
                ),
                needs_human_review=(
                    router_decision.needs_human_review
                ),
            )
        # 正常情况->三步计划：分析数据、检索知识、综合判断
        steps = [
            self._make_step(
                sequence=0,
                action="分析当前子系统的测量数据和风险",
                target=analysis_skill,
                input_keys=["issue"],
                output_key="tool_results",
            ),
            self._make_step(
                sequence=1,
                action="检索与异常现象相关的动力系统知识",
                target=self.RAG_TARGET,
                input_keys=["raw_input", "issue"],
                output_key="rag_answers",
            ),
            self._make_step(
                sequence=2,
                action="结合分析结果和知识证据生成候选诊断",
                target="diagnosis",
                input_keys=[
                    "tool_results",
                    "rag_answers",
                ],
                output_key="tool_results",
            ),
        ]

        return self._validate_and_build_ready_result(
            issue=issue,
            router_decision=router_decision,
            steps=steps,
        )

    def _build_parameter_optimization_result(
        self,
        *,
        issue: PowerSystemIssue,
        router_decision: RouterDecision,
    ) -> PlannerResult:
        """生成预测、参数寻优和模拟策略下发计划。"""

        supported_subsystems = {
            Subsystem.BATTERY,
            Subsystem.THERMAL,
            Subsystem.CHARGING,
            Subsystem.MULTI_SYSTEM,
        }

        if issue.subsystem not in supported_subsystems:
            return PlannerResult(
                route=issue.task_type,
                status=PlannerStatus.UNSUPPORTED,
                reason=(
                    "当前参数寻优工作流只支持电池、"
                    "热管理、充电及其多系统协同任务。"
                ),
                missing_information=list(
                    issue.missing_information
                ),
                needs_human_review=(
                    router_decision.needs_human_review
                ),
            )

        steps = [
            self._make_step(
                sequence=0,
                action=(
                    "预测候选控制参数下的动力系统未来状态"
                ),
                target=self.DIGITAL_TWIN_TARGET,
                input_keys=[
                    "skill_inputs",
                    "issue",
                ],
                output_key="tool_results",
            ),
            self._make_step(
                sequence=1,
                action=(
                    "搜索并排序满足安全约束的参数组合"
                ),
                target=self.OPTIMIZATION_TARGET,
                input_keys=[
                    "skill_inputs",
                    "tool_results",
                ],
                output_key="tool_results",
            ),
            self._make_step(
                sequence=2,
                action=(
                    "将推荐参数转换为可审核的模拟云端策略"
                ),
                target=self.CLOUD_DISPATCH_TARGET,
                input_keys=[
                    "skill_inputs",
                    "tool_results",
                    "issue",
                ],
                output_key="tool_results",
            ),
        ]

        return self._validate_and_build_ready_result(
            issue=issue,
            router_decision=router_decision,
            steps=steps,
        )

    def _build_knowledge_plan(
        self,
    ) -> list[WorkflowStep]:
        """构建证据约束知识问答计划。"""

        return [
            self._make_step(
                sequence=0,
                action="检索知识库并生成证据约束回答",
                target=self.RAG_TARGET,
                input_keys=["raw_input", "issue"],
                output_key="rag_answers",
            )
        ]

    def _build_report_generation_result(
        self,
        *,
        issue: PowerSystemIssue,
        router_decision: RouterDecision,
    ) -> PlannerResult:
        """处理用户直接请求生成报告的场景。"""

        return PlannerResult(
            route=issue.task_type,
            status=PlannerStatus.NEEDS_INFORMATION,
            reason=(
                "Report Agent只能基于已经完成审核的"
                "分析、RAG或候选诊断结果生成报告。"
            ),
            missing_information=(
                self._merge_missing_information(
                    issue.missing_information,
                    (
                        "先提供或完成动力系统分析结果、"
                        "候选诊断、证据和建议动作"
                    ),
                )
            ),
            needs_human_review=(
                router_decision.needs_human_review
            ),
        )

    # 关键的能力白名单校验：所有计划在真正标记为READY之前必须检验
    # 检查计划里每个步骤的target是否真的在系统注册的能力清单（registry.list_skills()）/固定内置的RAG_TARGET中
    def _validate_and_build_ready_result(
        self,
        *,
        issue: PowerSystemIssue,
        router_decision: RouterDecision,
        steps: list[WorkflowStep],
    ) -> PlannerResult:
        """校验计划目标是否属于真实系统能力。"""

        registered_skills = {
            definition.name
            for definition in self.registry.list_skills()
        }

        available_targets = (
            registered_skills
            | {self.RAG_TARGET}
        )

        missing_capabilities = sorted(
            {
                step.target
                for step in steps
                if step.target not in available_targets
            }
        )

        if missing_capabilities:
            return PlannerResult(
                route=issue.task_type,
                status=(
                    PlannerStatus.CONFIGURATION_ERROR
                ),
                reason=(
                    "计划需要的执行能力未在系统中注册。"
                ),
                missing_capabilities=(
                    missing_capabilities
                ),
                missing_information=list(
                    issue.missing_information
                ),
                needs_human_review=True,
            )

        return PlannerResult(
            route=issue.task_type,
            status=PlannerStatus.READY,
            steps=steps,
            reason="已生成通过能力白名单校验的执行计划。",
            missing_information=list(
                issue.missing_information
            ),
            needs_human_review=(
                router_decision.needs_human_review
            ),
        )

    # 步骤构造工具方法
    @staticmethod
    def _make_step(
        *,
        sequence: int,
        action: str,
        target: str,
        input_keys: list[str],
        output_key: str,
    ) -> WorkflowStep:
        """创建编号稳定的计划步骤。"""

        return WorkflowStep(
            step_id=f"step_{sequence}",
            sequence=sequence,
            action=action,
            target=target,
            input_keys=input_keys,
            output_key=output_key,
        )

    @staticmethod
    def _merge_missing_information(
        existing: list[str],
        required_item: str,
    ) -> list[str]:
        """补充缺失信息并避免重复。"""

        merged = list(existing)

        if required_item not in merged:
            merged.append(required_item)

        return merged