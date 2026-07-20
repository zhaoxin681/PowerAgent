"""PowerAgent LangGraph多Agent工作流。
前面所有的Agent(IssueParser Router Planner DecisionAgent ReviewAgent ReportAgent)都是
零件，该代码用LangGraph将其组装成状态图，且为每个Agent包裹一层图节点适配层，负责把PowerAgentState
与各个Agent的方法签名之间做转换、拼接、异常兜底。
整体分为：依赖接口协议、图构建、对外入口、七个节点方法、两个条件路由函数、若干工具方法。"""

from __future__ import annotations

from typing import Any, Protocol

from langgraph.graph import (
    END,
    START,
    StateGraph,
)

from agent_core.decision_agent import DecisionAgent
from agent_core.issue_parser import (
    PowerSystemIssueParser,
)
from agent_core.planner_agent import (
    PlannerAgent,
    PlannerStatus,
)
from agent_core.report_agent import ReportAgent
from agent_core.review_agent import ReviewAgent
from agent_core.router_agent import (
    RouteStatus,
    RouterAgent,
    RouterDecision,
)
from agent_core.schemas import (
    PowerSystemIssue,
    Severity,
    Subsystem,
    TaskType,
)
from agent_core.skill_registry import (
    SkillNotFoundError,
    SkillRegistry,
)
from agent_core.state import (
    PowerAgentState,
    TraceEventStatus,
    WorkflowDecision,
    WorkflowError,
    WorkflowNode,
    WorkflowStep,
    WorkflowStepStatus,
    WorkflowTraceEvent,
    create_initial_state,
)
from agent_core.tool_models import (
    ToolCallingResult,
    ToolCallingStatus,
)
from rag.exceptions import RAGError
from rag.schemas import RAGAnswer
from skills import (
    SkillContext,
    SkillExecutionError,
    SkillInputValidationError,
    SkillOutputValidationError,
)
from skills.battery_analysis_skill import (
    BatteryAnalysisOutput,
)
from skills.charging_analysis_skill import (
    ChargingAnalysisOutput,
)
from skills.diagnosis_skill import DiagnosisOutput
from skills.optimization_skill import (
    OptimizationOutput,
)
from skills.thermal_analysis_skill import (
    ThermalAnalysisOutput,
)

# 一、依赖接口协议
class IssueParserProtocol(Protocol):
    """工作流依赖的最小问题解析接口。"""

    def parse(
        self,
        user_input: str,
    ) -> PowerSystemIssue:
        """将用户输入解析为结构化问题。"""


class RAGPipelineProtocol(Protocol):
    """工作流依赖的最小RAG接口。"""

    def answer(
        self,
        question: str,
        *,
        subsystem: Subsystem | str | None = None,
        topic: str | None = None,
        top_k: int = 4,
        min_score: float | None = None,
    ) -> RAGAnswer:
        """返回证据约束RAG回答。"""


class PowerAgentWorkflow:
    """组装并运行PowerAgent多Agent工作流。"""

    RAG_TARGET = "rag_pipeline"

    # 二、依赖注入所有Agent
    def __init__(
        self,
        *,
        issue_parser: IssueParserProtocol,
        router_agent: RouterAgent,
        planner_agent: PlannerAgent,
        decision_agent: DecisionAgent,
        review_agent: ReviewAgent,
        report_agent: ReportAgent,
        registry: SkillRegistry,
        rag_pipeline: RAGPipelineProtocol,
    ) -> None:
        self.issue_parser = issue_parser
        self.router_agent = router_agent
        self.planner_agent = planner_agent
        self.decision_agent = decision_agent
        self.review_agent = review_agent
        self.report_agent = report_agent
        self.registry = registry
        self.rag_pipeline = rag_pipeline

        self.graph = self._build_graph() # 编译出可执行图

    # 三、用LangGraph声明状态图结构
    def _build_graph(self) -> Any:
        """构建并编译LangGraph状态图。
        七个节点每个节点对应一个包装方法，共享一个PowerAgentState"""

        builder = StateGraph(PowerAgentState)

        builder.add_node(
            "parse_issue",
            self._parse_issue_node,
        )
        builder.add_node(
            "router",
            self._router_node,
        )
        builder.add_node(
            "planner",
            self._planner_node,
        )
        builder.add_node(
            "execute_step",
            self._execute_step_node,
        )
        builder.add_node(
            "decision",
            self._decision_node,
        )
        builder.add_node(
            "review",
            self._review_node,
        )
        builder.add_node(
            "report",
            self._report_node,
        )
        # 固定边（无条件跳转）
        builder.add_edge(
            START,
            "parse_issue",
        )
        builder.add_edge(
            "parse_issue",
            "router",
        )
        builder.add_edge(
            "router",
            "planner",
        )
        # 条件边（根据状态动态选择下一个节点）
        builder.add_conditional_edges(
            "planner",
            self._route_after_planner,
            {
                "execute_step": "execute_step",
                "review": "review",
            },
        )

        builder.add_edge(
            "execute_step",
            "decision",
        )

        builder.add_conditional_edges(
            "decision",
            self._route_after_decision,
            {
                "execute_step": "execute_step",
                "planner": "planner",
                "review": "review",
            },
        )

        builder.add_edge(
            "review",
            "report",
        )
        builder.add_edge(
            "report",
            END,
        )

        return builder.compile()

    # 四、对外的统一入口
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
        """创建初始状态并执行完整工作流。"""

        initial_state = create_initial_state(
            raw_input,
            trace_id=trace_id,
            max_retries=max_retries,
            skill_inputs=skill_inputs,
        )

        return self.graph.invoke(initial_state)

    # 五、七个节点方法详解，都遵循模式：1）从state里提取需要字段；2）调用对应的Agent；3）用try/except
    # 兜底捕获异常（保证Agent内部的意外崩溃不会导致整个LangGraph执行中断）；4）返回一个部分状态更新字典
    # （LangGraph的节点函数约定：返回值是要合并进State的增量字典，而不是完整状态）

    # 问题解析节点
    def _parse_issue_node(
        self,
        state: PowerAgentState,
    ) -> dict[str, Any]:
        """执行结构化问题解析。"""

        try:
            issue = self.issue_parser.parse(
                state["raw_input"]
            )

            return {
                "issue": issue,
                "current_node": (
                    WorkflowNode.ISSUE_PARSER
                ),
                "execution_trace": [
                    WorkflowTraceEvent(
                        node=WorkflowNode.ISSUE_PARSER,
                        status=(
                            TraceEventStatus.COMPLETED
                        ),
                        detail="动力系统问题解析完成",
                    )
                ],
            }

        except Exception:
            error = WorkflowError(
                node=WorkflowNode.ISSUE_PARSER,
                error_code="issue_parser_failed",
                message=(
                    "动力系统问题结构化解析失败。"
                ),
                retryable=False,
            )

            # 使用明确的未知状态继续进入受限工作流，
            # 不伪造解析结果。
            fallback_issue = PowerSystemIssue(
                raw_text=state["raw_input"],
                subsystem=Subsystem.UNKNOWN,
                task_type=TaskType.UNKNOWN,
                symptoms=[],
                operating_conditions=[],
                user_hypotheses=[],
                requested_outputs=[],
                missing_information=[
                    "需要重新解析用户任务"
                ],
                severity=Severity.UNKNOWN,
                confidence=0.0,
            )

            return {
                "issue": fallback_issue,
                "latest_error": error,
                "errors": [error],
                "needs_human_review": True,
                "current_node": (
                    WorkflowNode.ISSUE_PARSER
                ),
                "execution_trace": [
                    WorkflowTraceEvent(
                        node=WorkflowNode.ISSUE_PARSER,
                        status=TraceEventStatus.FAILED,
                        detail="动力系统问题解析失败",
                    )
                ],
            }

    # 路由节点
    def _router_node(
        self,
        state: PowerAgentState,
    ) -> dict[str, Any]:
        """执行工作流任务路由。"""

        issue = self._require_issue(state)

        try:
            decision = self.router_agent.route(
                issue,
                trace_id=state["trace_id"],
            )

        except Exception:
            decision = RouterDecision(
                route=TaskType.UNKNOWN,
                status=RouteStatus.UNSUPPORTED,
                reason="Router Agent执行失败。",
                missing_information=[
                    "需要人工确认任务类型"
                ],
                needs_human_review=True,
            )

            error = WorkflowError(
                node=WorkflowNode.ROUTER,
                error_code="router_failed",
                message="工作流任务路由失败。",
                retryable=False,
            )

            error_updates: dict[str, Any] = {
                "errors": [error],
                "latest_error": error,
            }
        else:
            error_updates = {}

        updated_issue = issue.model_copy(
            update={
                "missing_information": (
                    self._deduplicate(
                        issue.missing_information
                        + decision.missing_information
                    )
                )
            }
        )

        return {
            "issue": updated_issue,
            "route": decision.route,
            "route_status": (
                decision.status.value
            ),
            "route_reason": decision.reason,
            "needs_human_review": (
                state["needs_human_review"]
                or decision.needs_human_review
            ),
            "current_node": WorkflowNode.ROUTER,
            "execution_trace": [
                WorkflowTraceEvent(
                    node=WorkflowNode.ROUTER,
                    status=TraceEventStatus.COMPLETED,
                    detail=(
                        "任务路由："
                        f"{decision.route.value} / "
                        f"{decision.status.value}"
                    ),
                )
            ],
            **error_updates,
        }

    # 计划生成节点
    def _planner_node(
        self,
        state: PowerAgentState,
    ) -> dict[str, Any]:
        """生成并校验结构化执行计划。"""

        issue = self._require_issue(state)

        route = (
            state.get("route")
            or TaskType.UNKNOWN
        )

        route_status = RouteStatus(
            state.get("route_status")
            or RouteStatus.UNSUPPORTED.value
        )

        # 需要重组RouterDecision进而输入PlannerAgent.plan()
        router_decision = RouterDecision(
            route=route,
            status=route_status,
            reason=(
                state.get("route_reason")
                or "没有有效路由说明"
            ),
            missing_information=list(
                issue.missing_information
            ),
            needs_human_review=(
                state["needs_human_review"]
            ),
        )

        try:
            result = self.planner_agent.plan(
                issue,
                router_decision,
                trace_id=state["trace_id"],
            )

        except Exception:
            error = WorkflowError(
                node=WorkflowNode.PLANNER,
                error_code="planner_failed",
                message="工作流执行计划生成失败。",
                retryable=False,
            )

            return {
                "plan": [],
                "planner_status": (
                    PlannerStatus
                    .CONFIGURATION_ERROR
                    .value
                ),
                "planner_reason": error.message,
                "missing_capabilities": [],
                "latest_error": error,
                "errors": [error],
                "needs_human_review": True,
                "current_node": WorkflowNode.PLANNER,
                "execution_trace": [
                    WorkflowTraceEvent(
                        node=WorkflowNode.PLANNER,
                        status=TraceEventStatus.FAILED,
                        detail="执行计划生成失败",
                    )
                ],
            }

        additional_missing = list(
            result.missing_information
        )

        additional_missing.extend(
            (
                f"系统缺少执行能力：{item}"
                for item in result.missing_capabilities
            )
        )

        if (
            result.status != PlannerStatus.READY
            and result.reason
        ):
            additional_missing.append(
                result.reason
            )

        updated_issue = issue.model_copy(
            update={
                "missing_information": (
                    self._deduplicate(
                        issue.missing_information
                        + additional_missing
                    )
                )
            }
        )

        updates: dict[str, Any] = {
            "issue": updated_issue,
            "plan": result.steps,
            "planner_status": result.status.value,
            "planner_reason": result.reason,
            "missing_capabilities": (
                result.missing_capabilities
            ),
            "current_step_index": 0,
            "latest_tool_result": None,
            "latest_rag_answer": None,
            "latest_error": None,
            "needs_human_review": (
                state["needs_human_review"]
                or result.needs_human_review
            ),
            "current_node": WorkflowNode.PLANNER,
            "execution_trace": [
                WorkflowTraceEvent(
                    node=WorkflowNode.PLANNER,
                    status=(
                        TraceEventStatus.COMPLETED
                    ),
                    detail=(
                        f"计划状态：{result.status.value}，"
                        f"步骤数量：{len(result.steps)}"
                    ),
                )
            ],
        }

        if (
            result.status
            == PlannerStatus.CONFIGURATION_ERROR
        ):
            error = WorkflowError(
                node=WorkflowNode.PLANNER,
                error_code=(
                    "planner_configuration_error"
                ),
                message=result.reason,
                retryable=False,
            )

            updates.update(
                {
                    "latest_error": error,
                    "errors": [error],
                    "needs_human_review": True,
                }
            )

        return updates

    # 条件路由函数
    def _route_after_planner(
        self,
        state: PowerAgentState,
    ) -> str:
        """根据Planner状态选择执行或审核。"""

        if (
            state.get("planner_status")
            == PlannerStatus.READY.value
        ):
            return "execute_step"

        return "review"

    # 执行步骤节点
    def _execute_step_node(
        self,
        state: PowerAgentState,
    ) -> dict[str, Any]:
        """执行当前计划步骤。"""

        plan = state.get("plan", [])
        step_index = state.get(
            "current_step_index",
            0,
        )

        if (
            not plan
            or step_index < 0
            or step_index >= len(plan)
        ):
            error = WorkflowError(
                node=WorkflowNode.EXECUTOR,
                error_code="invalid_step_index",
                message="当前工作流步骤索引无效。",
                retryable=False,
            )

            return {
                "latest_error": error,
                "errors": [error],
                "latest_tool_result": None,
                "latest_rag_answer": None,
                "current_node": WorkflowNode.EXECUTOR,
                "execution_trace": [
                    WorkflowTraceEvent(
                        node=WorkflowNode.EXECUTOR,
                        status=TraceEventStatus.FAILED,
                        detail="当前执行步骤无效",
                    )
                ],
            }

        step = plan[step_index]

        running_plan = self._replace_step_status(
            plan,
            step_index,
            WorkflowStepStatus.RUNNING,
        )

        if step.target == self.RAG_TARGET:
            execution_updates = self._execute_rag(
                state=state,
                step=step,
            )
        else:
            execution_updates = self._execute_skill(
                state=state,
                step=step,
            )

        return {
            "plan": running_plan,
            "current_node": WorkflowNode.EXECUTOR,
            "execution_trace": [
                WorkflowTraceEvent(
                    node=WorkflowNode.EXECUTOR,
                    status=(
                        TraceEventStatus.COMPLETED
                    ),
                    detail=f"执行目标：{step.target}",
                    step_id=step.step_id,
                )
            ],
            **execution_updates,
        }

    # 调用Skill的具体执行逻辑
    def _execute_skill(
        self,
        *,
        state: PowerAgentState,
        step: WorkflowStep,
    ) -> dict[str, Any]:
        """通过Registry直接执行Planner指定的Skill。"""

        call_id = (
            f"{state['trace_id']}:"
            f"{step.step_id}:"
            f"{state['retry_count']}"
        )

        if step.target == "diagnosis":
            arguments = (
                self._build_diagnosis_arguments(
                    state
                )
            )
        elif step.target == "cloud_dispatch":
            arguments = (
                self._build_cloud_dispatch_arguments(
                    state
                )
            )
        else:
            arguments = state.get(
                "skill_inputs",
                {},
            ).get(step.target)

        if arguments is None:
            result = ToolCallingResult(
                status=(
                    ToolCallingStatus.INVALID_ARGUMENTS
                ),
                trace_id=state["trace_id"],
                tool_name=step.target,
                call_id=call_id,
                error_code="missing_skill_input",
                error_message=(
                    "当前工作流没有获得该Skill"
                    "所需的显式业务参数。"
                ),
            )

            return {
                "tool_results": [result],
                "latest_tool_result": result,
                "latest_rag_answer": None,
                "latest_error": None,
            }

        context = SkillContext(
            trace_id=state["trace_id"],
            source="langgraph_workflow",
            metadata={
                "step_id": step.step_id,
                "step_sequence": step.sequence,
            },
        )

        try:
            output = self.registry.invoke(
                step.target,
                arguments,
                context=context,
            )

        except SkillNotFoundError:
            result = ToolCallingResult(
                status=ToolCallingStatus.UNKNOWN_TOOL,
                trace_id=state["trace_id"],
                tool_name=step.target,
                call_id=call_id,
                arguments=arguments,
                error_code="unknown_tool",
                error_message="计划引用了未注册Skill。",
            )

        except SkillInputValidationError as exc:
            result = ToolCallingResult(
                status=(
                    ToolCallingStatus.INVALID_ARGUMENTS
                ),
                trace_id=state["trace_id"],
                tool_name=step.target,
                call_id=call_id,
                arguments=arguments,
                error_code=exc.code,
                error_message=str(exc),
            )

        except SkillOutputValidationError as exc:
            result = ToolCallingResult(
                status=(
                    ToolCallingStatus
                    .INVALID_SKILL_OUTPUT
                ),
                trace_id=state["trace_id"],
                tool_name=step.target,
                call_id=call_id,
                arguments=arguments,
                error_code=exc.code,
                error_message=str(exc),
                needs_human_review=True,
            )

        except SkillExecutionError as exc:
            result = ToolCallingResult(
                status=(
                    ToolCallingStatus
                    .SKILL_EXECUTION_FAILED
                ),
                trace_id=state["trace_id"],
                tool_name=step.target,
                call_id=call_id,
                arguments=arguments,
                error_code=exc.code,
                error_message=str(exc),
                needs_human_review=True,
            )

        except Exception:
            result = ToolCallingResult(
                status=(
                    ToolCallingStatus
                    .SKILL_EXECUTION_FAILED
                ),
                trace_id=state["trace_id"],
                tool_name=step.target,
                call_id=call_id,
                arguments=arguments,
                error_code="unexpected_skill_error",
                error_message=(
                    "Skill执行过程中发生未预期错误。"
                ),
                needs_human_review=True,
            )

        else:
            result = ToolCallingResult(
                status=ToolCallingStatus.SUCCESS,
                trace_id=state["trace_id"],
                tool_name=step.target,
                call_id=call_id,
                arguments=arguments,
                output=output.model_dump(
                    mode="json"
                ),
            )

        return {
            "tool_results": [result],
            "latest_tool_result": result,
            "latest_rag_answer": None,
            "latest_error": None,
        }

    # 执行RAG检索的具体逻辑
    def _execute_rag(
        self,
        *,
        state: PowerAgentState,
        step: WorkflowStep,
    ) -> dict[str, Any]:
        """执行证据约束RAG步骤。"""

        issue = self._require_issue(state)

        try:
            answer = self.rag_pipeline.answer(
                state["raw_input"],
                subsystem=issue.subsystem,
            )

        except RAGError as exc:
            error = WorkflowError(
                node=WorkflowNode.EXECUTOR,
                error_code=exc.code,
                message="RAG执行失败。",
                retryable=False,
                step_id=step.step_id,
            )

            return {
                "latest_error": error,
                "errors": [error],
                "latest_tool_result": None,
                "latest_rag_answer": None,
            }

        except Exception:
            error = WorkflowError(
                node=WorkflowNode.EXECUTOR,
                error_code="unexpected_rag_error",
                message=(
                    "RAG执行过程中发生未预期错误。"
                ),
                retryable=False,
                step_id=step.step_id,
            )

            return {
                "latest_error": error,
                "errors": [error],
                "latest_tool_result": None,
                "latest_rag_answer": None,
            }

        return {
            "rag_answers": [answer],
            "latest_rag_answer": answer,
            "latest_tool_result": None,
            "latest_error": None,
        }

    # 决策节点：把三种可能的输入组装好，喂给DecisionAgent
    def _decision_node(
        self,
        state: PowerAgentState,
    ) -> dict[str, Any]:
        """根据当前步骤结果生成流程控制决策。"""

        plan = state.get("plan", [])
        step_index = state.get(
            "current_step_index",
            0,
        )

        kwargs: dict[str, Any] = {
            "plan": plan,
            "current_step_index": step_index,
            "retry_count": state["retry_count"],
            "replan_count": state["replan_count"],
            "max_retries": state["max_retries"],
            "trace_id": state["trace_id"],
        }

        latest_error = state.get("latest_error")

        if latest_error is not None:
            kwargs["workflow_error"] = latest_error  # 检查错误

        elif (
            plan
            and 0 <= step_index < len(plan)
            and plan[step_index].target
            == self.RAG_TARGET
        ):
            kwargs["rag_answer"] = state.get(
                "latest_rag_answer"
            )  # 看当前步骤的target是不是RAG，从而决定是传rag_answer还是tool_result

        else:
            kwargs["tool_result"] = state.get(
                "latest_tool_result"
            )

        result = self.decision_agent.decide(
            **kwargs
        )

        return {
            "decision": result.decision,
            "plan": result.updated_plan,
            "current_step_index": (
                result.next_step_index
            ),
            "retry_count": result.retry_count,
            "replan_count": result.replan_count,
            "needs_human_review": (
                state["needs_human_review"]
                or result.needs_human_review
            ),
            "latest_tool_result": None,
            "latest_rag_answer": None,
            "latest_error": None,
            "current_node": WorkflowNode.DECISION,
            "execution_trace": [
                WorkflowTraceEvent(
                    node=WorkflowNode.DECISION,
                    status=TraceEventStatus.COMPLETED,
                    detail=(
                        "工作流决策："
                        f"{result.decision.value}"
                    ),
                )
            ],
        }

    # 决策后的条件路由
    def _route_after_decision(
        self,
        state: PowerAgentState,
    ) -> str:
        """根据Decision结果选择后续节点。"""

        decision = state.get("decision")

        if decision in {
            WorkflowDecision.CONTINUE,
            WorkflowDecision.RETRY,
        }:
            return "execute_step"

        if decision == WorkflowDecision.REPLAN:
            return "planner"

        return "review"

    # 收尾两节点
    def _review_node(
        self,
        state: PowerAgentState,
    ) -> dict[str, Any]:
        """审核工作流执行结果。"""

        result = self.review_agent.review(
            issue=self._require_issue(state),
            plan=state.get("plan", []),
            tool_results=state.get(
                "tool_results",
                [],
            ),
            rag_answers=state.get(
                "rag_answers",
                [],
            ),
            errors=state.get("errors", []),
            decision=state.get("decision"),
            trace_id=state["trace_id"],
        )

        return {
            "review_result": result,
            "needs_human_review": (
                state["needs_human_review"]
                or result.needs_human_review
            ),
            "current_node": WorkflowNode.REVIEW,
            "execution_trace": [
                WorkflowTraceEvent(
                    node=WorkflowNode.REVIEW,
                    status=TraceEventStatus.COMPLETED,
                    detail=(
                        "审核状态："
                        f"{result.status.value}"
                    ),
                )
            ],
        }

    def _report_node(
        self,
        state: PowerAgentState,
    ) -> dict[str, Any]:
        """生成或阻断最终结构化报告。"""

        review_result = state.get(
            "review_result"
        )

        if review_result is None:
            raise RuntimeError(
                "Report节点缺少ReviewResult"
            )

        report = self.report_agent.generate(
            issue=self._require_issue(state),
            review_result=review_result,
            trace_id=state["trace_id"],
        )

        return {
            "final_report": report,
            "current_node": WorkflowNode.END,
            "is_finished": True,
            "needs_human_review": (
                state["needs_human_review"]
                or report.needs_human_review
            ),
            "execution_trace": [
                WorkflowTraceEvent(
                    node=WorkflowNode.REPORT,
                    status=TraceEventStatus.COMPLETED,
                    detail=(
                        "报告状态："
                        f"{report.status.value}"
                    ),
                )
            ],
        }

    # 自动组装诊断参数
    @staticmethod
    def _build_diagnosis_arguments(
        state: PowerAgentState,
    ) -> dict[str, Any]:
        """根据前序分析结果构造Diagnosis输入。"""

        battery_risk = False
        thermal_risk = False
        charging_risk = False

        abnormal_cells: list[int] = []
        abnormal_sensors: list[int] = []
        violated_constraints: list[str] = []

        for result in state.get(
            "tool_results",
            [],
        ):
            if (
                result.status
                != ToolCallingStatus.SUCCESS
                or result.output is None
            ):
                continue

            if result.tool_name == "battery_analysis":
                output = (
                    BatteryAnalysisOutput
                    .model_validate(result.output)
                )

                battery_risk = (
                    output.consistency_risk
                    or bool(
                        output
                        .out_of_range_cell_numbers
                    )
                )

                abnormal_cells.extend(
                    output.out_of_range_cell_numbers
                )

            elif result.tool_name == "thermal_analysis":
                output = (
                    ThermalAnalysisOutput
                    .model_validate(result.output)
                )

                thermal_risk = (
                    output
                    .temperature_inconsistency_risk
                    or bool(
                        output
                        .overtemperature_sensor_numbers
                    )
                )

                abnormal_sensors.extend(
                    output
                    .overtemperature_sensor_numbers
                )

            elif result.tool_name == "charging_analysis":
                output = (
                    ChargingAnalysisOutput
                    .model_validate(result.output)
                )

                charging_risk = output.has_risk

                violated_constraints.extend(
                    output.violated_constraints
                )

        issue = state.get("issue")

        issue_summary = (
            issue.raw_text
            if issue is not None
            else state["raw_input"]
        )

        return {
            "issue_summary": issue_summary,
            "battery_risk": battery_risk,
            "thermal_risk": thermal_risk,
            "charging_risk": charging_risk,
            "abnormal_cell_numbers": (
                list(dict.fromkeys(abnormal_cells))
            ),
            "abnormal_sensor_numbers": (
                list(
                    dict.fromkeys(
                        abnormal_sensors
                    )
                )
            ),
            "violated_constraints": (
                list(
                    dict.fromkeys(
                        violated_constraints
                    )
                )
            ),
        }
    
    @classmethod
    def _build_cloud_dispatch_arguments(
        cls,
        state: PowerAgentState,
    ) -> dict[str, Any] | None:
        """根据显式配置和参数寻优结果构造下发输入。"""

        dispatch_inputs = state.get(
            "skill_inputs",
            {},
        ).get("cloud_dispatch")

        if dispatch_inputs is None:
            return None

        optimization_result = (
            cls._find_latest_successful_tool_result(
                state=state,
                tool_name="parameter_optimization",
            )
        )

        if (
            optimization_result is None
            or optimization_result.output is None
        ):
            return None

        optimization_output = (
            OptimizationOutput.model_validate(
                optimization_result.output
            )
        )

        arguments = dict(dispatch_inputs)

        # 上游真实执行结果覆盖外部同名字段，
        # 防止调用方伪造参数寻优状态或推荐方案。
        arguments.update(
            {
                "optimization_status": (
                    optimization_output.status
                ),
                "recommended_candidate": (
                    optimization_output
                    .recommended_candidate
                    .model_dump(mode="json")
                    if (
                        optimization_output
                        .recommended_candidate
                        is not None
                    )
                    else None
                ),
                "optimization_reason": (
                    optimization_output
                    .selection_reason
                ),
            }
        )

        return arguments

    @staticmethod
    def _replace_step_status(
        plan: list[WorkflowStep],
        step_index: int,
        status: WorkflowStepStatus,
    ) -> list[WorkflowStep]:
        """复制计划并更新指定步骤状态。"""

        return [
            (
                step.model_copy(
                    update={"status": status}
                )
                if index == step_index
                else step
            )
            for index, step in enumerate(plan)
        ]

    
    @staticmethod
    def _require_issue(
        state: PowerAgentState,
    ) -> PowerSystemIssue:
        """返回工作流结构化问题。"""

        issue = state.get("issue")

        if issue is None:
            raise RuntimeError(
                "工作流状态中缺少PowerSystemIssue"
            )

        return issue

    @staticmethod
    def _deduplicate(
        items: list[str],
    ) -> list[str]:
        """保留顺序并去除重复字符串。"""

        return list(dict.fromkeys(items))
    
    @staticmethod
    def _find_latest_successful_tool_result(
        *,
        state: PowerAgentState,
        tool_name: str,
    ) -> ToolCallingResult | None:
        """查找指定Skill最近一次成功执行结果。"""

        for result in reversed(
            state.get(
                "tool_results",
                [],
            )
        ):
            if (
                result.tool_name == tool_name
                and result.status
                == ToolCallingStatus.SUCCESS
            ):
                return result

        return None