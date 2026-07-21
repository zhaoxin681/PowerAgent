"""PowerAgent工作流任务路由。
职责为接收上一步Issue Parser产出的结构化问题PowerSystemIssue，
根据确定性规则（不依赖LLM）判断这个问题应该走向哪个后续工作流、
当前是否可以立即执行，并生成结构化的路由决策RouterDecision。
整体分为 枚举类型、数据模型RouterDecision、RouterAgent路由逻辑类。"""

from __future__ import annotations

import logging
from enum import Enum

from pydantic import Field

from agent_core.logging_config import get_logger
from agent_core.schemas import (
    PowerSystemIssue,
    Severity,
    StrictBaseModel,
    Subsystem,
    TaskType,
)

# 路由可执行性状态，判断这个路由能不能走下去
class RouteStatus(str, Enum):
    """Router Agent对当前任务可执行性的判断。"""

    AVAILABLE = "available"   # 立即执行
    DEFERRED = "deferred"     # 已识别，但功能尚未开发/接入
    NEEDS_INFORMATION = "needs_information"  # 信息不足，无法确定任务
    UNSUPPORTED = "unsupported"   # 完全不支持/无法识别

# 路由结果的结构化模型
class RouterDecision(StrictBaseModel):
    """Router Agent返回的结构化工作流路由结果。"""

    route: TaskType = Field(
        description="工作流后续执行的任务类型",
    )

    status: RouteStatus = Field(
        description="当前路由是否能够立即执行",
    )

    reason: str = Field(
        min_length=1,
        description="选择该路由状态的简要原因",
    )

    missing_information: list[str] = Field(
        default_factory=list,
        description="继续执行当前任务仍然缺少的信息",
    )

    needs_human_review: bool = Field(
        default=False,
        description="是否需要动力系统专业人员优先复核",
    )

# 核心路由逻辑
class RouterAgent:
    """根据结构化动力系统问题选择工作流类型。"""

    # 1. 类级别配置
    _AVAILABLE_TASKS = {
        TaskType.KNOWLEDGE_QUERY,
        TaskType.DATA_ANALYSIS,
        TaskType.FAULT_DIAGNOSIS,
        TaskType.PARAMETER_OPTIMIZATION,
        TaskType.RND_ANALYSIS,
        TaskType.REPORT_GENERATION,
    } # 可以真正执行的任务类型集合

    _DEFERRED_REASONS: dict[
        TaskType,
        str,
    ] = {}

    # 构造函数
    def __init__(
        self,
        logger: logging.Logger | None = None,
    ) -> None:
        self._logger = logger or get_logger(
            "router_agent"
        )

    # 对外的公开入口
    def route(
        self,
        issue: PowerSystemIssue,
        *,
        trace_id: str | None = None,
    ) -> RouterDecision:
        """根据PowerSystemIssue生成确定性的工作流路由结果。"""

        self._logger.info(
            "开始执行工作流任务路由。",
            extra={
                "event": "workflow_route_started",
                "trace_id": trace_id,
                "subsystem": issue.subsystem.value,
                "task_type": issue.task_type.value,
            },
        )

        decision = self._make_decision(issue)

        self._logger.info(
            "工作流任务路由完成。",
            extra={
                "event": "workflow_route_completed",
                "trace_id": trace_id,
                "route": decision.route.value,
                "route_status": decision.status.value,
                "needs_human_review": (
                    decision.needs_human_review
                ),
            },
        )

        return decision

    def _make_decision(
        self,
        issue: PowerSystemIssue,
    ) -> RouterDecision:
        """执行不依赖LLM的确定性路由规则。"""

        needs_human_review = (
            issue.severity == Severity.CRITICAL
        )

        # 无法确认动力系统对象时，不允许进入具体业务工作流。
        if issue.subsystem == Subsystem.UNKNOWN:
            return RouterDecision(
                route=TaskType.UNKNOWN,
                status=RouteStatus.UNSUPPORTED,
                reason=(
                    "无法确认该请求属于当前支持的"
                    "动力系统范围。"
                ),
                missing_information=(
                    self._merge_missing_information(
                        issue.missing_information,
                        "明确问题涉及的动力系统对象或子系统",
                    )
                ),
                needs_human_review=needs_human_review,
            )

        # 已知动力系统对象，但不知道用户希望执行什么任务。
        if issue.task_type == TaskType.UNKNOWN:
            return RouterDecision(
                route=TaskType.UNKNOWN,
                status=RouteStatus.NEEDS_INFORMATION,
                reason=(
                    "动力系统对象已识别，"
                    "但任务目标不明确。"
                ),
                missing_information=(
                    self._merge_missing_information(
                        issue.missing_information,
                        (
                            "明确希望执行知识查询、数据分析、"
                            "故障诊断、参数寻优或报告生成"
                        ),
                    )
                ),
                needs_human_review=needs_human_review,
            )

        # 任务类型属于已上线能力。
        if issue.task_type in self._AVAILABLE_TASKS:
            return RouterDecision(
                route=issue.task_type,
                status=RouteStatus.AVAILABLE,
                reason="当前任务类型已有对应工作流能力。",
                missing_information=list(
                    issue.missing_information
                ),
                needs_human_review=needs_human_review,
            )

        # 已识别，但属于后续周实现范围。
        if issue.task_type in self._DEFERRED_REASONS:
            return RouterDecision(
                route=issue.task_type,
                status=RouteStatus.DEFERRED,
                reason=self._DEFERRED_REASONS[
                    issue.task_type
                ],
                missing_information=list(
                    issue.missing_information
                ),
                needs_human_review=needs_human_review,
            )

        # 防御性兜底，避免新增枚举后意外进入错误工作流。
        return RouterDecision(
            route=TaskType.UNKNOWN,
            status=RouteStatus.UNSUPPORTED,
            reason="当前任务类型没有可用的工作流路由。",
            missing_information=list(
                issue.missing_information
            ),
            needs_human_review=needs_human_review,
        )

    @staticmethod
    def _merge_missing_information(
        existing: list[str],
        required_item: str,
    ) -> list[str]:
        """在保留原顺序的前提下补充缺失信息。"""

        merged = list(existing)

        if required_item not in merged:
            merged.append(required_item)

        return merged