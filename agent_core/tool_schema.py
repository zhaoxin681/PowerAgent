"""将PowerAgent Skill转换为大模型可读取的工具Schema。"""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from skills import BaseSkill


class ToolSchemaGenerationError(ValueError):
    """生成工具Schema失败。"""

    default_code = "tool_schema_generation_error"

    def __init__(
        self,
        message: str,
        *,
        skill_name: str | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.skill_name = skill_name
        self.code = self.default_code

    def __str__(self) -> str:
        if self.skill_name:
            return (
                f"[{self.code}] skill={self.skill_name}: "
                f"{self.message}"
            )

        return f"[{self.code}] {self.message}"


# 核心转换逻辑
def build_tool_schema(
    skill: BaseSkill[Any, Any],
) -> dict[str, Any]:
    """根据Skill输入模型生成OpenAI兼容的工具Schema。

    Args:
        skill:
            已完成初始化的BaseSkill实例。

    Returns:
        OpenAI兼容的function tool定义。

    Raises:
        ToolSchemaGenerationError:
            Skill类型非法、输入模型Schema生成失败，或者输入模型
            不是对象类型时抛出。
    """
    # 确保输入进来的是BaseSkill实例
    if not isinstance(skill, BaseSkill):
        raise ToolSchemaGenerationError(
            "Only BaseSkill instances can be converted to tool schemas."
        )

    # 生成输入模型的JSON Schema
    skill_name = skill.definition.name

    try:
        parameter_schema = deepcopy(
            skill.input_model.model_json_schema(mode="validation")
        )
    except Exception as exc:
        raise ToolSchemaGenerationError(
            "Failed to generate JSON Schema from the skill input model.",
            skill_name=skill_name,
        ) from exc

    # Tool Calling的函数参数必须是JSON对象。
    # RootModel[list[...]]等数组根模型不能直接作为函数参数。
    if parameter_schema.get("type") != "object":
        raise ToolSchemaGenerationError(
            "The skill input model must generate an object JSON Schema.",
            skill_name=skill_name,
        )

    # 根节点标题对大模型选择工具没有必要，删除后Schema更简洁。
    parameter_schema.pop("title", None)
    # 组装成Open AI兼容格式
    return {
        "type": "function",
        "function": {
            "name": skill_name,
            "description": skill.definition.description,
            "parameters": parameter_schema,
        },
    }