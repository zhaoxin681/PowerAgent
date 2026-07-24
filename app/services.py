"""PowerAgent API服务适配层。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import (
    Any,
    Protocol,
)
from uuid import uuid4

from agent_core.state import PowerAgentState
from app.exceptions import (
    WorkflowExecutionError,
)
from app.schemas import (
    RndAnalysisApiRequest,
    WorkflowAnalysisData,
    WorkflowAnalysisRequest,
    WorkflowIntermediateResults,
)
from workflows.rnd_models import (
    RndAnalysisRequest,
    RndAnalysisResult,
)

class PowerAgentWorkflowProtocol(Protocol):
    """通用工作流服务依赖的最小接口。"""

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
        """执行通用PowerAgent工作流。"""


class RndAnalysisWorkflowProtocol(Protocol):
    """研发分析服务依赖的最小接口。"""

    def analyze(
        self,
        request: RndAnalysisRequest,
        *,
        skill_inputs: (
            dict[str, dict[str, Any]] | None
        ) = None,
        max_retries: int = 2,
    ) -> RndAnalysisResult:
        """执行完整研发分析工作流。"""


class WorkflowService:
    """将通用工作流结果转换为公开API数据。"""

    def __init__(
        self,
        *,
        workflow: PowerAgentWorkflowProtocol,
    ) -> None:
        self.workflow = workflow

    def analyze(
        self,
        request: WorkflowAnalysisRequest,
    ) -> WorkflowServiceResult:
        """执行通用工作流并生成公开结果。"""

        resolved_trace_id = (
            request.trace_id
            or uuid4().hex
        )

        state = self.workflow.invoke(
            request.raw_input,
            trace_id=resolved_trace_id,
            max_retries=request.max_retries,
            skill_inputs=request.skill_inputs,
        )

        issue = state.get("issue")

        if issue is None:
            raise WorkflowExecutionError(
                "通用工作流没有返回结构化问题",
                trace_id=resolved_trace_id,
            )

        state_trace_id = state.get(
            "trace_id"
        )

        if not state_trace_id:
            raise WorkflowExecutionError(
                "通用工作流没有返回追踪标识",
                trace_id=resolved_trace_id,
            )

        trace_id = str(state_trace_id)

        execution_trace = (
            list(
                state.get(
                    "execution_trace",
                    [],
                )
            )
            if request.include_trace
            else None
        )

        intermediate_results = (
            WorkflowIntermediateResults(
                tool_results=list(
                    state.get(
                        "tool_results",
                        [],
                    )
                ),
                rag_answers=list(
                    state.get(
                        "rag_answers",
                        [],
                    )
                ),
                errors=list(
                    state.get(
                        "errors",
                        [],
                    )
                ),
            )
            if request.include_intermediate_results
            else None
        )

        data = WorkflowAnalysisData(
            issue=issue,
            route=state.get("route"),
            route_status=state.get(
                "route_status"
            ),
            route_reason=state.get(
                "route_reason"
            ),
            review_result=state.get(
                "review_result"
            ),
            final_report=state.get(
                "final_report"
            ),
            needs_human_review=bool(
                state.get(
                    "needs_human_review",
                    False,
                )
            ),
            warnings=self._build_warnings(
                state
            ),
            execution_trace=execution_trace,
            intermediate_results=(
                intermediate_results
            ),
        )

        return WorkflowServiceResult(
            trace_id=trace_id,
            data=data,
        )

    @classmethod
    def _build_warnings(
        cls,
        state: PowerAgentState,
    ) -> list[str]:
        """根据工作流状态生成公开业务警告。"""

        warnings: list[str] = []

        if state.get(
            "needs_human_review",
            False,
        ):
            warnings.append(
                "当前结果需要动力系统专业人员复核。"
            )

        review_result = state.get(
            "review_result"
        )

        if review_result is not None:
            warnings.extend(
                review_result.review_issues
            )

            warnings.extend(
                review_result.unresolved_items
            )

        final_report = state.get(
            "final_report"
        )

        if (
            final_report is not None
            and final_report.blocked_reason
            is not None
        ):
            warnings.append(
                final_report.blocked_reason
            )

        planner_status = state.get(
            "planner_status"
        )

        planner_reason = state.get(
            "planner_reason"
        )

        if (
            planner_status is not None
            and planner_status != "ready"
            and planner_reason
        ):
            warnings.append(
                planner_reason
            )

        return cls._deduplicate(warnings)

    @staticmethod
    def _deduplicate(
        items: list[str],
    ) -> list[str]:
        """保留原顺序并删除重复警告。"""

        return list(dict.fromkeys(items))



class RndAnalysisService:
    """研发分析API与领域工作流之间的适配器。"""

    def __init__(
        self,
        *,
        workflow: RndAnalysisWorkflowProtocol,
    ) -> None:
        self.workflow = workflow

    def analyze(
        self,
        request: RndAnalysisApiRequest,
    ) -> RndAnalysisResult:
        """执行研发分析并返回领域结果。"""

        resolved_trace_id = (
            request.trace_id
            or uuid4().hex
        )

        request_payload = (
            request.model_dump(
                exclude={
                    "max_retries",
                    "skill_inputs",
                }
            )
        )

        request_payload["trace_id"] = (
            resolved_trace_id
        )

        domain_request = (
            RndAnalysisRequest.model_validate(
                request_payload
            )
        )

        result = self.workflow.analyze(
            domain_request,
            skill_inputs=request.skill_inputs,
            max_retries=request.max_retries,
        )

        if not result.trace_id:
            raise WorkflowExecutionError(
                "研发分析工作流没有返回追踪标识",
                trace_id=resolved_trace_id,
            )

        return result


@dataclass(frozen=True, slots=True)
class WorkflowServiceResult:
    """通用工作流服务的内部返回结果。"""

    trace_id: str
    data: WorkflowAnalysisData