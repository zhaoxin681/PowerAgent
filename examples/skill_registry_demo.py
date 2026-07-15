"""Skill Registry与Tool Schema演示。展示多个技能如何被统一注册、发现、导出给LLM、以及被调用的完整流程"""

from __future__ import annotations

import json

from pydantic import BaseModel, ConfigDict, Field

from agent_core import SkillRegistry
from examples.minimal_skill_demo import VoltageSpreadSkill
from skills import BaseSkill, SkillContext


class TemperatureSpreadInput(BaseModel):
    """温度一致性分析输入。"""

    model_config = ConfigDict(extra="forbid")

    temperatures_c: list[float] = Field(
        min_length=2,
        description="温度测点列表，单位为摄氏度。",
    )


class TemperatureSpreadOutput(BaseModel):
    """温度一致性分析输出。"""

    model_config = ConfigDict(extra="forbid")

    minimum_temperature_c: float
    maximum_temperature_c: float
    temperature_spread_c: float
    trace_id: str


class TemperatureSpreadSkill(
    BaseSkill[
        TemperatureSpreadInput,
        TemperatureSpreadOutput,
    ]
):
    """计算多个温度测点的极值与温差。"""

    name = "temperature_spread"
    description = "计算温度测点的最低温度、最高温度和最大温差。"

    input_model = TemperatureSpreadInput
    output_model = TemperatureSpreadOutput

    def execute(
        self,
        skill_input: TemperatureSpreadInput,
        context: SkillContext,
    ) -> dict[str, float | str]:
        temperatures = skill_input.temperatures_c

        minimum_temperature = min(temperatures)
        maximum_temperature = max(temperatures)

        return {
            "minimum_temperature_c": minimum_temperature,
            "maximum_temperature_c": maximum_temperature,
            "temperature_spread_c": round(
                maximum_temperature - minimum_temperature,
                6,
            ),
            "trace_id": context.trace_id,
        }


# 完整演示流程
def main() -> None:
    """展示Skill注册、发现、Schema生成和统一调用。"""

    # 1. 创建注册表，注册两个技能
    registry = SkillRegistry()

    registry.register(VoltageSpreadSkill())
    registry.register(TemperatureSpreadSkill())

    # 2. 列出所有已注册的技能
    print("已注册Skill：")
    for definition in registry.list_skills():
        print(
            f"- {definition.name} "
            f"(version={definition.version})"
        )

    # 3. 生成并打印所有技能的Tool Schema
    print("\nTool Schemas：")
    print(
        json.dumps(
            registry.get_tool_schemas(),
            ensure_ascii=False,
            indent=2,
        )
    )

    # 4. 调用电压分析技能
    voltage_result = registry.invoke(
        "voltage_spread",
        {
            "cell_voltages_v": [
                3.652,
                3.648,
                3.571,
                3.655,
            ]
        },
        context={
            "trace_id": "registry-voltage-demo",
            "source": "example",
        },
    )

    print("\n电压分析结果：")
    print(voltage_result.model_dump_json(indent=2))

    # 5. 调用电压分析技能
    temperature_result = registry.invoke(
        "temperature_spread",
        {
            "temperatures_c": [
                26.4,
                27.1,
                31.8,
                28.0,
            ]
        },
        context={
            "trace_id": "registry-temperature-demo",
            "source": "example",
        },
    )

    print("\n温度分析结果：")
    print(temperature_result.model_dump_json(indent=2))


if __name__ == "__main__":
    main()