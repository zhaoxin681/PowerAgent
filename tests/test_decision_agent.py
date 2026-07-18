"""Decision Agent核心功能测试。
测试 步骤成功继续、最后一步完成、非法参数触发重规划、不可重试错误转人工、
可重试错误的有限次数重试、RAG证据不足时的特殊处理"""

from agent_core.decision_agent import (
    DecisionAgent,
)
from agent_core.state import (
    WorkflowDecision,
    WorkflowError,
    WorkflowNode,
    WorkflowStep,
    WorkflowStepStatus,
)
from agent_core.tool_models import (
    ToolCallingResult,
    ToolCallingStatus,
)
from rag.schemas import RAGAnswer


# 测试计划的工厂函数
def make_plan(
    targets: tuple[str, ...] = (
        "battery_analysis",
        "rag_pipeline",
    ),
) -> list[WorkflowStep]:
    """创建Decision Agent测试计划。"""

    return [
        WorkflowStep(
            step_id=f"step_{index}",
            sequence=index,
            action=f"执行{target}",
            target=target,
            input_keys=["issue"],
            output_key="tool_results",
        )
        for index, target in enumerate(targets)
    ] # DecisionAgent关心的是根据这份计划和当前的执行结果该怎么决策，而不是计划本身初始状态细节


"""
六个测试用例
"""
# 1. 步骤成功->继续下一步，且重试计数归零
def test_successful_step_continues_and_resets_retry(
) -> None:
    """步骤成功后应进入下一步并重置当前步骤重试次数。"""

    result = DecisionAgent().decide(
        plan=make_plan(),
        current_step_index=0,
        retry_count=1,
        replan_count=0,
        max_retries=2,
        tool_result=ToolCallingResult(
            status=ToolCallingStatus.SUCCESS,
            trace_id="trace_001",
            tool_name="battery_analysis",
            output={"risk": "medium"},
        ),
    )

    assert result.decision == WorkflowDecision.CONTINUE
    assert result.next_step_index == 1
    assert result.retry_count == 0

    assert (
        result.updated_plan[0].status
        == WorkflowStepStatus.SUCCESS
    )

    assert (
        result.updated_plan[1].status
        == WorkflowStepStatus.PENDING
    )


# 2. 最后一步成功->计划完成
def test_successful_last_step_finishes_plan() -> None:
    """最后一个步骤成功后应结束业务计划。"""

    result = DecisionAgent().decide(
        plan=make_plan(("battery_analysis",)),
        current_step_index=0,
        retry_count=0,
        replan_count=0,
        max_retries=2,
        tool_result=ToolCallingResult(
            status=ToolCallingStatus.SUCCESS,
            trace_id="trace_002",
            tool_name="battery_analysis",
            output={"risk": "normal"},
        ),
    )

    assert result.decision == WorkflowDecision.FINISH
    assert result.next_step_index == 1

    assert (
        result.updated_plan[0].status
        == WorkflowStepStatus.SUCCESS
    )


# 3. 参数非法->重新规划
def test_invalid_arguments_requests_replan() -> None:
    """非法参数不应重复执行相同调用。"""

    result = DecisionAgent(
        max_replans=1
    ).decide(
        plan=make_plan(),
        current_step_index=0,
        retry_count=0,
        replan_count=0,
        max_retries=2,
        tool_result=ToolCallingResult(
            status=(
                ToolCallingStatus.INVALID_ARGUMENTS
            ),
            trace_id="trace_003",
            tool_name="battery_analysis",
            error_code="invalid_arguments",
            error_message="输入参数不合法",
        ),
    )

    assert result.decision == WorkflowDecision.REPLAN
    assert result.next_step_index == 0
    assert result.replan_count == 1

    assert (
        result.updated_plan[0].status
        == WorkflowStepStatus.FAILED
    )


# 4. LLM最终失败->直接转人工
def test_llm_final_failure_requires_human_review(
) -> None:
    """LLM层重试耗尽后不再叠加工作流级重试。"""

    result = DecisionAgent().decide(
        plan=make_plan(),
        current_step_index=0,
        retry_count=0,
        replan_count=0,
        max_retries=2,
        tool_result=ToolCallingResult(
            status=(
                ToolCallingStatus.LLM_REQUEST_FAILED
            ),
            trace_id="trace_004",
            error_code="llm_request_failed",
            error_message="LLM请求最终失败",
            needs_human_review=True,
        ),
    )

    assert (
        result.decision
        == WorkflowDecision.HUMAN_REVIEW
    )

    assert result.retry_count == 0
    assert result.needs_human_review is True

    assert (
        result.updated_plan[0].status
        == WorkflowStepStatus.FAILED
    )

    assert (
        result.updated_plan[1].status
        == WorkflowStepStatus.SKIPPED
    )


# 5. 可重试的工作流错误->有限次数重试后转人工
def test_retryable_workflow_error_obeys_limit(
) -> None:
    """只有显式可重试错误才进行有限次数重试。"""

    error = WorkflowError(
        node=WorkflowNode.EXECUTOR,
        error_code="temporary_unavailable",
        message="执行服务暂时不可用",
        retryable=True,
        step_id="step_0",
    )

    agent = DecisionAgent()

    retry_result = agent.decide(
        plan=make_plan(),
        current_step_index=0,
        retry_count=0,
        replan_count=0,
        max_retries=1,
        workflow_error=error,
    )

    assert (
        retry_result.decision
        == WorkflowDecision.RETRY
    )
    assert retry_result.retry_count == 1
    assert retry_result.next_step_index == 0

    exhausted_result = agent.decide(
        plan=make_plan(),
        current_step_index=0,
        retry_count=1,
        replan_count=0,
        max_retries=1,
        workflow_error=error,
    )

    assert (
        exhausted_result.decision
        == WorkflowDecision.HUMAN_REVIEW
    )
    assert exhausted_result.needs_human_review is True


# 6. RAG证据不足->当前步骤成功但跳过后续诊断
def test_insufficient_rag_evidence_stops_diagnosis(
) -> None:
    """证据不足时不得继续执行候选诊断步骤。"""

    plan = make_plan(
        (
            "rag_pipeline",
            "diagnosis",
        )
    )

    result = DecisionAgent().decide(
        plan=plan,
        current_step_index=0,
        retry_count=0,
        replan_count=0,
        max_retries=2,
        rag_answer=RAGAnswer(
            question="电池压差增大的原因是什么？",
            answer=(
                "当前知识库没有足够证据"
                "支撑可靠诊断。"
            ),
            citations=[],
            confidence=0.0,
            sufficient_evidence=False,
            missing_information=[
                "需要补充运行数据和故障记录"
            ],
            needs_human_review=True,
        ),
    )

    assert (
        result.decision
        == WorkflowDecision.HUMAN_REVIEW
    )

    # RAG程序正常执行，因此当前步骤成功。
    assert (
        result.updated_plan[0].status
        == WorkflowStepStatus.SUCCESS
    )

    # 没有证据时不能继续生成诊断。
    assert (
        result.updated_plan[1].status
        == WorkflowStepStatus.SKIPPED
    )