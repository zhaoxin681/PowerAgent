"""Tool Schema生成测试。"""

from __future__ import annotations

from enum import Enum
from typing import Any

import pytest
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    RootModel,
)

from agent_core.tool_schema import (
    ToolSchemaGenerationError,
    build_tool_schema,
)
from skills import BaseSkill, SkillContext

# 功能齐全输入模型
class AnalysisMode(str, Enum):
    """测试使用的分析模式。"""

    BASIC = "basic"
    DETAILED = "detailed"


class ThresholdConfig(BaseModel):
    """测试嵌套模型。"""

    model_config = ConfigDict(extra="forbid")

    warning_voltage_v: float = Field(gt=0)
    critical_voltage_v: float = Field(gt=0)


class BatteryToolInput(BaseModel):
    """包含必填、可选、枚举和嵌套字段的输入模型。"""

    model_config = ConfigDict(extra="forbid")

    cell_voltages_v: list[float] = Field(
        min_length=2,
        description="单体电压列表，单位为V。",
    )
    mode: AnalysisMode = Field(
        description="分析模式。",
    )
    thresholds: ThresholdConfig
    note: str | None = None


class BatteryToolOutput(BaseModel):
    """测试输出模型。"""

    model_config = ConfigDict(extra="forbid")

    voltage_spread_v: float


class BatteryToolSkill(
    BaseSkill[BatteryToolInput, BatteryToolOutput]
):
    """用于测试Tool Schema生成。"""

    name = "battery_tool"
    description = "分析电池单体电压和阈值状态。"

    input_model = BatteryToolInput
    output_model = BatteryToolOutput

    def execute(
        self,
        skill_input: BatteryToolInput,
        context: SkillContext,
    ) -> dict[str, float]:
        return {
            "voltage_spread_v": (
                max(skill_input.cell_voltages_v)
                - min(skill_input.cell_voltages_v)
            )
        }

# 非法输入模型
class ListRootInput(RootModel[list[float]]):
    """不符合函数参数要求的数组根模型。"""


class ListRootOutput(BaseModel):
    """数组根模型Skill的测试输出。"""

    value: float


class ListRootSkill(BaseSkill[ListRootInput, ListRootOutput]):
    """用于验证非对象输入Schema会被拒绝。"""

    name = "list_root"
    description = "测试非法数组根输入模型。"

    input_model = ListRootInput
    output_model = ListRootOutput

    def execute(
        self,
        skill_input: ListRootInput,
        context: SkillContext,
    ) -> dict[str, float]:
        return {"value": sum(skill_input.root)}


"""
逐个测试用例解析
"""
# OpenAI Function Calling范式检查   
def test_build_tool_schema_has_openai_compatible_structure() -> None:
    schema = build_tool_schema(BatteryToolSkill())

    assert schema["type"] == "function"
    assert schema["function"]["name"] == "battery_tool"
    assert schema["function"]["description"]
    assert schema["function"]["parameters"]["type"] == "object"

# 有默认值的不出现在required中，无默认值的需要
def test_required_fields_are_preserved() -> None:
    schema = build_tool_schema(BatteryToolSkill())

    required = schema["function"]["parameters"]["required"]

    assert set(required) == {
        "cell_voltages_v",
        "mode",
        "thresholds",
    }
    assert "note" not in required

# 测试复杂类型信息在转换过程中不会失真
def test_nested_models_and_enums_are_preserved() -> None:
    schema = build_tool_schema(BatteryToolSkill())
    parameters = schema["function"]["parameters"]

    assert "$defs" in parameters
    assert "AnalysisMode" in parameters["$defs"]
    assert "ThresholdConfig" in parameters["$defs"]

# 额外字段输入测试
def test_extra_fields_remain_forbidden_in_schema() -> None:
    schema = build_tool_schema(BatteryToolSkill())
    parameters = schema["function"]["parameters"]

    assert parameters["additionalProperties"] is False

# 确认Schema中完全不包含输出模型的任何痕迹
def test_output_model_is_not_exposed_as_function_parameters() -> None:
    schema_text = str(build_tool_schema(BatteryToolSkill()))

    assert "BatteryToolOutput" not in schema_text
    assert "voltage_spread_v" not in schema_text

# 多次调用返回的不是同一个对象
def test_schema_generation_is_deterministic() -> None:
    skill = BatteryToolSkill()

    first = build_tool_schema(skill)
    second = build_tool_schema(skill)

    assert first == second
    assert first is not second

# 验证输入对象
def test_non_skill_object_is_rejected() -> None:
    with pytest.raises(ToolSchemaGenerationError):
        build_tool_schema(object())  # type: ignore[arg-type]

# 数组根模型会被正确拦截
def test_array_root_input_schema_is_rejected() -> None:
    with pytest.raises(ToolSchemaGenerationError) as exc_info:
        build_tool_schema(ListRootSkill())

    assert exc_info.value.skill_name == "list_root"   