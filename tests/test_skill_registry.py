"""SkillRegistry注册、发现和调用测试。"""

from __future__ import annotations

from typing import Any

import pytest
from pydantic import BaseModel, ConfigDict

from agent_core.skill_registry import (
    DuplicateSkillError,
    InvalidSkillDefinitionError,
    SkillNotFoundError,
    SkillRegistry,
)
from skills import (
    BaseSkill,
    SkillContext,
    SkillInputValidationError,
)


class NumberInput(BaseModel):
    """简单数值输入。"""

    model_config = ConfigDict(extra="forbid")

    left: float
    right: float


class NumberOutput(BaseModel):
    """简单数值输出。"""

    model_config = ConfigDict(extra="forbid")

    result: float
    trace_id: str


class AddNumbersSkill(BaseSkill[NumberInput, NumberOutput]):
    """加法Skill。"""

    name = "add_numbers"
    description = "计算两个数值之和。"

    input_model = NumberInput
    output_model = NumberOutput

    def execute(
        self,
        skill_input: NumberInput,
        context: SkillContext,
    ) -> dict[str, float | str]:
        return {
            "result": skill_input.left + skill_input.right,
            "trace_id": context.trace_id,
        }

# 测试显式覆盖机制
class ReplacementAddSkill(BaseSkill[NumberInput, NumberOutput]):
    """用于测试显式覆盖的加法Skill。"""

    name = "add_numbers"
    description = "覆盖原有加法Skill，用减法验证覆盖结果。"

    input_model = NumberInput
    output_model = NumberOutput

    def execute(
        self,
        skill_input: NumberInput,
        context: SkillContext,
    ) -> dict[str, float | str]:
        return {
            "result": skill_input.left - skill_input.right,
            "trace_id": context.trace_id,
        }


class MultiplyNumbersSkill(BaseSkill[NumberInput, NumberOutput]):
    """乘法Skill。"""

    name = "multiply_numbers"
    description = "计算两个数值之积。"

    input_model = NumberInput
    output_model = NumberOutput

    def execute(
        self,
        skill_input: NumberInput,
        context: SkillContext,
    ) -> dict[str, float | str]:
        return {
            "result": skill_input.left * skill_input.right,
            "trace_id": context.trace_id,
        }

"""
逐个测试用例解析
"""
# 最基础正常路径：技能注册、精确查找、验证身份/in/len
def test_register_and_get_skill() -> None:
    registry = SkillRegistry()
    skill = AddNumbersSkill()

    registry.register(skill)

    assert registry.get("add_numbers") is skill
    assert "add_numbers" in registry
    assert len(registry) == 1

# 重复注册名抛出异常
def test_duplicate_registration_is_rejected() -> None:
    registry = SkillRegistry()

    registry.register(AddNumbersSkill())

    with pytest.raises(DuplicateSkillError) as exc_info:
        registry.register(AddNumbersSkill())

    assert exc_info.value.skill_name == "add_numbers"

# 验证显示覆盖机制
def test_explicit_overwrite_replaces_existing_skill() -> None:
    registry = SkillRegistry()

    registry.register(AddNumbersSkill())
    registry.register(
        ReplacementAddSkill(),
        overwrite=True,
    )

    result = registry.invoke(
        "add_numbers",
        {
            "left": 10,
            "right": 3,
        },
    )

    assert result.result == 7

# 验证查找不存在的技能名
def test_unknown_skill_raises_clear_error() -> None:
    registry = SkillRegistry()

    with pytest.raises(SkillNotFoundError) as exc_info:
        registry.get("unknown_skill")

    assert exc_info.value.skill_name == "unknown_skill"

# 注册不相关的对象
def test_non_skill_object_is_rejected() -> None:
    registry = SkillRegistry()

    with pytest.raises(InvalidSkillDefinitionError):
        registry.register(object())  # type: ignore[arg-type]

# 验证invoke()的正常执行路径：传入字典形式的参数和context，最终拿到经过校验的输出实例
def test_invoke_runs_skill_validation_and_execution() -> None:
    registry = SkillRegistry()
    registry.register(AddNumbersSkill())

    result = registry.invoke(
        "add_numbers",
        {
            "left": 2.5,
            "right": 4.5,
        },
        context={
            "trace_id": "registry-test",
            "source": "unit_test",
        },
    )

    assert isinstance(result, NumberOutput)
    assert result.result == 7.0
    assert result.trace_id == "registry-test"

# 验证registry不会绕过BaseSkill.run
def test_invoke_does_not_bypass_input_validation() -> None:
    registry = SkillRegistry()
    registry.register(AddNumbersSkill())

    with pytest.raises(SkillInputValidationError):
        registry.invoke(
            "add_numbers",
            {
                "left": 1,
                "right": 2,
                "unknown_field": 3,
            },
        )

# 注册顺序验证-按字母顺序排序
def test_list_skills_is_sorted_and_immutable() -> None:
    registry = SkillRegistry()

    registry.register(MultiplyNumbersSkill())
    registry.register(AddNumbersSkill())

    definitions = registry.list_skills()
    names = tuple(item.name for item in definitions)

    assert names == (
        "add_numbers",
        "multiply_numbers",
    )
    assert isinstance(definitions, tuple)

# 和上一个类似
def test_get_tool_schemas_are_sorted_by_skill_name() -> None:
    registry = SkillRegistry()

    registry.register(MultiplyNumbersSkill())
    registry.register(AddNumbersSkill())

    schemas = registry.get_tool_schemas()
    names = [
        item["function"]["name"]
        for item in schemas
    ]

    assert names == [
        "add_numbers",
        "multiply_numbers",
    ]

# 防污染测试
def test_returned_tool_schema_mutation_does_not_affect_registry() -> None:
    registry = SkillRegistry()
    registry.register(AddNumbersSkill())

    first = registry.get_tool_schemas()
    first[0]["function"]["name"] = "changed"

    second = registry.get_tool_schemas()

    assert second[0]["function"]["name"] == "add_numbers"