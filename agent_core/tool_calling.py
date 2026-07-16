"""单轮单工具Tool Calling执行流程。"""

from __future__ import annotations

import json
import logging
from typing import Protocol

from agent_core.prompts import (
    POWER_SYSTEM_TOOL_ROUTER_PROMPT,
)
from agent_core.skill_registry import (
    SkillNotFoundError,
    SkillRegistry,
)
from agent_core.tool_models import (
    ToolCallingResult,
    ToolCallingStatus,
    ToolSelectionResponse,
)
from skills import (
    SkillContext,
    SkillExecutionError,
    SkillInputValidationError,
    SkillOutputValidationError,
)


logger = logging.getLogger(__name__)


# 用protocol定义的最小接口，只要某个对象有一个签名匹配的request_tool_call方法，就能被当作ToolCallingClient使用
class ToolCallingClient(Protocol):
    """Tool Calling Runner依赖的最小LLM客户端接口。"""

    def request_tool_call(
        self,
        *,
        developer_prompt: str,
        user_input: str,
        tools: list[dict[str, object]],
    ) -> ToolSelectionResponse:
        """请求大模型选择工具。"""

# 只负责流程编排
class ToolCallingRunner:
    """完成LLM工具选择、参数解析和Skill执行。"""

    def __init__(
        self,
        *,
        registry: SkillRegistry,
        client: ToolCallingClient,
        developer_prompt: str = (
            POWER_SYSTEM_TOOL_ROUTER_PROMPT
        ),
    ) -> None:
        self._registry = registry
        self._client = client
        self._developer_prompt = developer_prompt

    def run(
        self,
        user_input: str,
        *,
        context: SkillContext | None = None,
    ) -> ToolCallingResult:
        """执行一次单轮、单工具Tool Calling。"""

        runtime_context = context or SkillContext(
            source="tool_calling",
        )

        # 检查点1：调用大模型本身失败
        try:
            selection = self._client.request_tool_call(
                developer_prompt=self._developer_prompt,
                user_input=user_input,
                tools=self._registry.get_tool_schemas(),
            )
        except Exception:
            return self._finish(
                ToolCallingResult(
                    status=(
                        ToolCallingStatus.LLM_REQUEST_FAILED
                    ),
                    trace_id=runtime_context.trace_id,
                    error_code="llm_request_failed",
                    error_message=(
                        "大模型工具选择请求执行失败。"
                    ),
                    needs_human_review=True,
                )
            )
        
        # 检查点2：大模型没有选择任何工具
        if not selection.tool_calls:
            return self._finish(
                ToolCallingResult(
                    status=(
                        ToolCallingStatus.NO_TOOL_SELECTED
                    ),
                    trace_id=runtime_context.trace_id,
                    assistant_content=(
                        selection.assistant_content
                    ),
                )
            )

        # 检查点3：大模型同时选择了多个工具（当前不支持）
        if len(selection.tool_calls) > 1:
            return self._finish(
                ToolCallingResult(
                    status=(
                        ToolCallingStatus
                        .MULTIPLE_TOOLS_NOT_SUPPORTED
                    ),
                    trace_id=runtime_context.trace_id,
                    error_code=(
                        "multiple_tools_not_supported"
                    ),
                    error_message=(
                        "当前版本只支持单次调用一个工具。"
                    ),
                    needs_human_review=True,
                )
            )

        # 提取出唯一的工具调用决策
        decision = selection.tool_calls[0]

        # 检查点4：解析JSON参数失败
        try:
            arguments = json.loads(
                decision.arguments_json
            )
        except json.JSONDecodeError:
            return self._finish(
                ToolCallingResult(
                    status=(
                        ToolCallingStatus.INVALID_ARGUMENTS
                    ),
                    trace_id=runtime_context.trace_id,
                    tool_name=decision.tool_name,
                    call_id=decision.call_id,
                    error_code="invalid_json_arguments",
                    error_message=(
                        "大模型生成的工具参数不是合法JSON。"
                    ),
                )
            )

        # 检查点5：解析出来的JSON不是一个对象
        if not isinstance(arguments, dict):
            return self._finish(
                ToolCallingResult(
                    status=(
                        ToolCallingStatus.INVALID_ARGUMENTS
                    ),
                    trace_id=runtime_context.trace_id,
                    tool_name=decision.tool_name,
                    call_id=decision.call_id,
                    error_code="arguments_not_object",
                    error_message=(
                        "工具参数必须是JSON对象。"
                    ),
                )
            )

        # 检查点6：调用Registry执行技能，分别处理各种可能异常
        try:
            skill_output = self._registry.invoke(
                decision.tool_name,
                arguments,
                context=runtime_context,
            )
        except SkillNotFoundError:
            return self._finish(
                ToolCallingResult(
                    status=ToolCallingStatus.UNKNOWN_TOOL,
                    trace_id=runtime_context.trace_id,
                    tool_name=decision.tool_name,
                    call_id=decision.call_id,
                    arguments=arguments,
                    error_code="unknown_tool",
                    error_message=(
                        "大模型选择了未注册的工具。"
                    ),
                )
            )
        except SkillInputValidationError as exc:
            return self._finish(
                ToolCallingResult(
                    status=(
                        ToolCallingStatus.INVALID_ARGUMENTS
                    ),
                    trace_id=runtime_context.trace_id,
                    tool_name=decision.tool_name,
                    call_id=decision.call_id,
                    arguments=arguments,
                    error_code=exc.code,
                    error_message=str(exc),
                )
            )
        except SkillOutputValidationError as exc:
            return self._finish(
                ToolCallingResult(
                    status=(
                        ToolCallingStatus
                        .INVALID_SKILL_OUTPUT
                    ),
                    trace_id=runtime_context.trace_id,
                    tool_name=decision.tool_name,
                    call_id=decision.call_id,
                    arguments=arguments,
                    error_code=exc.code,
                    error_message=str(exc),
                    needs_human_review=True,
                )
            )
        except SkillExecutionError as exc:
            return self._finish(
                ToolCallingResult(
                    status=(
                        ToolCallingStatus
                        .SKILL_EXECUTION_FAILED
                    ),
                    trace_id=runtime_context.trace_id,
                    tool_name=decision.tool_name,
                    call_id=decision.call_id,
                    arguments=arguments,
                    error_code=exc.code,
                    error_message=str(exc),
                    needs_human_review=True,
                )
            )

        return self._finish(
            ToolCallingResult(
                status=ToolCallingStatus.SUCCESS,
                trace_id=runtime_context.trace_id,
                tool_name=decision.tool_name,
                call_id=decision.call_id,
                arguments=arguments,
                output=skill_output.model_dump(
                    mode="json",
                ),
            )
        )

    # 统一收尾和日志记录
    @staticmethod
    def _finish(
        result: ToolCallingResult,
    ) -> ToolCallingResult:
        """记录结构化摘要并返回调用结果。"""

        logger.info(
            "tool_calling_completed",
            extra={
                "event": "tool_calling_completed",
                "trace_id": result.trace_id,
                "tool_name": result.tool_name,
                "call_id": result.call_id,
                "status": result.status.value,
                "error_type": result.error_code,
            },
        )

        return result