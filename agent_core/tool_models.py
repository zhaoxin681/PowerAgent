"""Tool Calling流程使用的内部数据模型。
是连接大模型返回的原始工具调用请求和skill执行层之间的中间数据结构层。
大模型调用某个工具时，调用请求和调用结果改用什么样的标准化数据结构表示。
"""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


# 一次工具调用流程可能出现的全部结局状态，对应了整条流水线上不同环节可能发生的情况
class ToolCallingStatus(str, Enum):
    """Tool Calling统一执行状态。"""

    SUCCESS = "success"
    NO_TOOL_SELECTED = "no_tool_selected"
    UNKNOWN_TOOL = "unknown_tool"
    INVALID_ARGUMENTS = "invalid_arguments"
    SKILL_EXECUTION_FAILED = "skill_execution_failed"
    INVALID_SKILL_OUTPUT = "invalid_skill_output"
    MULTIPLE_TOOLS_NOT_SUPPORTED = (
        "multiple_tools_not_supported"
    )
    LLM_REQUEST_FAILED = "llm_request_failed"


class ToolCallDecision(BaseModel):
    """从大模型响应中提取的单次工具调用决策。"""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
    )

    call_id: str = Field(min_length=1)  # 本次工具调用的唯一标识
    tool_name: str = Field(
        pattern=r"^[a-z][a-z0-9_]*$",
    )  # 大模型说要调用的工具名字符串
    arguments_json: str  # 大模型API返回的‘工具调用参数’原始格式


# 对“一次大模型API响应的标准化封装”
class ToolSelectionResponse(BaseModel):
    """LLM客户端返回的供应商无关工具选择结果。
    不同大模型供应商API返回工具调用信息时原始的JSON结构可能不同，
    该模块的作用为把不同大模型响应 翻译 成一套固定的、内部通用的结构
    """

    model_config = ConfigDict(extra="forbid")

    tool_calls: list[ToolCallDecision] = Field(
        default_factory=list,
    )
    assistant_content: str | None = None


# 整个流程最终对外暴露的统一结果-系统最终执行结果
class ToolCallingResult(BaseModel):
    """Tool Calling Runner的统一结构化结果。"""

    model_config = ConfigDict(extra="forbid")

    status: ToolCallingStatus
    trace_id: str

    tool_name: str | None = None
    call_id: str | None = None

    arguments: dict[str, Any] | None = None
    output: dict[str, Any] | None = None

    assistant_content: str | None = None

    error_code: str | None = None
    error_message: str | None = None

    needs_human_review: bool = False