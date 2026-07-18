"""PowerAgent LangGraph工作流共享状态。
整体分为 枚举类型、结构化数据模型Pydantic、TypedDict状态定义、初始状态构造函数。"""

from __future__ import annotations

import operator
from enum import Enum
from typing import Annotated, Any, TypedDict
from uuid import uuid4

from pydantic import Field

from agent_core.schemas import (
    PowerSystemIssue,
    StrictBaseModel,
    TaskType,
)
from agent_core.tool_models import ToolCallingResult
from rag.schemas import RAGAnswer, RetrievedChunk

from agent_core.workflow_models import (
    FinalWorkflowReport,
    ReviewResult,
)

# 一、枚举类型：定义工作流中的合法取值
class WorkflowNode(str, Enum):
    """工作流中的标准节点名称。"""

    START = "start"
    ISSUE_PARSER = "issue_parser"
    ROUTER = "router"
    PLANNER = "planner"
    EXECUTOR = "executor"
    DECISION = "decision"
    REVIEW = "review"
    REPORT = "report"
    ERROR_HANDLER = "error_handler"
    END = "end"


class WorkflowStepStatus(str, Enum):
    """单个计划步骤的执行状态。"""

    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"


class WorkflowDecision(str, Enum):
    """Decision Agent允许返回的控制决策。"""

    CONTINUE = "continue"
    FINISH = "finish"
    RETRY = "retry"
    REPLAN = "replan"
    HUMAN_REVIEW = "human_review"
    ABORT = "abort"


class TraceEventStatus(str, Enum):
    """节点执行轨迹中的事件状态。"""

    STARTED = "started"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"

# 二、结构化数据，继承StrictBaseModel，即严格模式的Pydantic模型
class WorkflowStep(StrictBaseModel):
    """Planner Agent生成的一条结构化执行步骤。本质上是Planner Agent输出的任务卡"""

    step_id: str = Field(
        min_length=1,
        pattern=r"^[a-z0-9][a-z0-9_-]*$",
        description="步骤稳定标识",
    )

    sequence: int = Field(
        ge=0,
        description="步骤执行顺序，从0开始",
    )

    action: str = Field(
        min_length=1,
        description="该步骤需要完成的动作",
    )

    target: str = Field(
        min_length=1,
        description="该步骤调用的Agent、RAG节点或Skill名称",
    )

    input_keys: list[str] = Field(
        default_factory=list,
        description="该步骤从工作流状态读取的字段名称",
    )

    output_key: str | None = Field(
        default=None,
        min_length=1,
        description="该步骤结果写入的状态字段；没有时为None",
    )

    status: WorkflowStepStatus = Field(
        default=WorkflowStepStatus.PENDING,
        description="步骤当前执行状态",
    )


class WorkflowError(StrictBaseModel):
    """工作流节点产生的统一错误记录。"""

    node: WorkflowNode

    error_code: str = Field(
        min_length=1,
        description="稳定的工作流错误码",
    )

    message: str = Field(
        min_length=1,
        description="便于定位问题的错误说明",
    )

    retryable: bool = Field(
        default=False,
        description="该错误是否允许自动重试",
    )

    step_id: str | None = Field(
        default=None,
        min_length=1,
        description="发生错误的计划步骤；不属于步骤时为None",
    )


class WorkflowTraceEvent(StrictBaseModel):
    """工作流节点执行轨迹。"""

    node: WorkflowNode

    status: TraceEventStatus

    detail: str = Field(
        default="",
        description="节点运行情况的简要说明",
    )

    step_id: str | None = Field(
        default=None,
        min_length=1,
        description="关联的执行步骤；没有时为None",
    )


class InitialWorkflowInput(StrictBaseModel):
    """用于校验工作流首次调用的输入。只在创建初始状态时使用"""

    raw_input: str = Field(
        min_length=1,
        description="用户输入的原始动力系统问题",
    )

    trace_id: str = Field(
        default_factory=lambda: uuid4().hex,
        min_length=1,
        description="一次完整工作流的追踪标识",
    ) # 自动生成追踪ID

    max_retries: int = Field(
        default=2,
        ge=0,
        le=5,
        description="单次工作流允许的最大重试次数",
    )

    skill_inputs: dict[
        str,
        dict[str, Any],
    ] = Field(
        default_factory=dict,
        description=(
            "按Skill名称保存的显式业务输入参数"
        ),
    )


# 三、状态定义（TypedDict）-LangGraph真正使用的state
class PowerAgentInputState(TypedDict):
    """启动工作流时必须提供的状态字段。"""

    raw_input: str
    trace_id: str


class PowerAgentState(PowerAgentInputState, total=False):
    """PowerAgent所有LangGraph节点共享的统一状态。"""

    # 结构化问题解析结果
    issue: PowerSystemIssue | None

    # Router Agent产生的任务路由结果
    route: TaskType | None

    # Planner Agent产生的执行计划
    plan: list[WorkflowStep]
    current_step_index: int

    # Tool Calling或Skill执行结果
    tool_results: Annotated[
        list[ToolCallingResult],
        operator.add,
    ]

    # RAG检索及回答结果
    retrieved_chunks: Annotated[
        list[RetrievedChunk],
        operator.add,
    ]
    rag_answers: Annotated[
        list[RAGAnswer],
        operator.add,
    ]

    # Decision、Review和Report阶段结果
    decision: WorkflowDecision | None
    review_result: ReviewResult | None
    final_report: FinalWorkflowReport | None
    
    # 多节点追加型状态
    errors: Annotated[
        list[WorkflowError],
        operator.add,
    ]
    execution_trace: Annotated[
        list[WorkflowTraceEvent],
        operator.add,
    ]

    # 工作流控制字段
    current_node: WorkflowNode
    retry_count: int
    replan_count: int
    max_retries: int
    needs_human_review: bool
    is_finished: bool

    # 用户显式提供的Skill业务参数。
    skill_inputs: dict[
        str,
        dict[str, Any],
    ]

    # Router节点完整控制信息。
    route_status: str | None
    route_reason: str | None

    # Planner节点完整控制信息。
    planner_status: str | None
    planner_reason: str | None
    missing_capabilities: list[str]

    # 当前步骤最近一次执行结果。
    # 与历史追加字段分开，便于Decision节点准确读取。
    latest_tool_result: ToolCallingResult | None
    latest_rag_answer: RAGAnswer | None
    latest_error: WorkflowError | None


# 初始状态
def create_initial_state(
    raw_input: str,
    *,
    trace_id: str | None = None,
    max_retries: int = 2,
    skill_inputs: (
        dict[str, dict[str, Any]] | None
    ) = None,
) -> PowerAgentState:
    """校验用户输入并创建完整、可预测的初始工作流状态。"""

    input_data: dict[str, Any] = {
        "raw_input": raw_input,
        "max_retries": max_retries,
        "skill_inputs": skill_inputs or {},
    }

    if trace_id is not None:
        input_data["trace_id"] = trace_id

    validated = InitialWorkflowInput.model_validate(
        input_data
    )

    return PowerAgentState(
        raw_input=validated.raw_input,
        trace_id=validated.trace_id,
        issue=None,
        route=None,
        plan=[],
        current_step_index=0,
        tool_results=[],
        retrieved_chunks=[],
        rag_answers=[],
        decision=None,
        review_result=None,
        final_report=None,
        errors=[],
        execution_trace=[],
        current_node=WorkflowNode.START,
        retry_count=0,
        replan_count=0,
        max_retries=validated.max_retries,
        needs_human_review=False,
        is_finished=False,
        skill_inputs=validated.skill_inputs,
        route_status=None,
        route_reason=None,
        planner_status=None,
        planner_reason=None,
        missing_capabilities=[],
        latest_tool_result=None,
        latest_rag_answer=None,
        latest_error=None,
    )