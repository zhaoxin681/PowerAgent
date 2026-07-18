"""统一工作流状态的核心测试。"""

import pytest
from langgraph.graph import END, START, StateGraph
from pydantic import ValidationError

from agent_core.state import (
    PowerAgentState,
    TraceEventStatus,
    WorkflowError,
    WorkflowNode,
    WorkflowTraceEvent,
    create_initial_state,
)


def test_create_initial_state() -> None:
    """初始状态应包含稳定默认值和唯一追踪标识。"""

    state = create_initial_state(
        "分析电池组单体压差异常"
    )

    assert (
        state["raw_input"]
        == "分析电池组单体压差异常"
    )
    assert state["trace_id"]
    assert state["current_node"] == WorkflowNode.START
    assert state["plan"] == []
    assert state["tool_results"] == []
    assert state["rag_answers"] == []
    assert state["errors"] == []
    assert state["retry_count"] == 0
    assert state["is_finished"] is False


def test_list_reducers_append_node_updates() -> None:
    """带reducer的列表字段应保留多个节点产生的记录。"""

    def router_node(
        _: PowerAgentState,
    ) -> dict[str, object]:
        return {
            "current_node": WorkflowNode.ROUTER,
            "execution_trace": [
                WorkflowTraceEvent(
                    node=WorkflowNode.ROUTER,
                    status=TraceEventStatus.COMPLETED,
                    detail="任务路由完成",
                )
            ],
        }

    def planner_node(
        _: PowerAgentState,
    ) -> dict[str, object]:
        return {
            "current_node": WorkflowNode.PLANNER,
            "execution_trace": [
                WorkflowTraceEvent(
                    node=WorkflowNode.PLANNER,
                    status=TraceEventStatus.FAILED,
                    detail="计划生成失败",
                )
            ],
            "errors": [
                WorkflowError(
                    node=WorkflowNode.PLANNER,
                    error_code="planner_failed",
                    message="无法生成合法计划",
                    retryable=True,
                )
            ],
        }

    builder = StateGraph(PowerAgentState)

    builder.add_node(
        "router",
        router_node,
    )
    builder.add_node(
        "planner",
        planner_node,
    )

    builder.add_edge(
        START,
        "router",
    )
    builder.add_edge(
        "router",
        "planner",
    )
    builder.add_edge(
        "planner",
        END,
    )

    graph = builder.compile()

    result = graph.invoke(
        create_initial_state("分析充电异常")
    )

    assert (
        result["current_node"]
        == WorkflowNode.PLANNER
    )

    assert len(result["execution_trace"]) == 2

    assert (
        result["execution_trace"][0].node
        == WorkflowNode.ROUTER
    )

    assert (
        result["execution_trace"][1].node
        == WorkflowNode.PLANNER
    )

    assert len(result["errors"]) == 1
    assert result["errors"][0].retryable is True


def test_create_initial_state_rejects_blank_input() -> None:
    """空白用户输入必须在进入工作流前被拒绝。"""

    with pytest.raises(ValidationError):
        create_initial_state("   ")