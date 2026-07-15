"""Minimal deterministic PowerAgent skill demonstration. 实现了一个电池单体电压极差分析的技能"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from skills import BaseSkill, SkillContext


class VoltageSpreadInput(BaseModel):
    """Input contract for cell-voltage spread analysis."""

    model_config = ConfigDict(extra="forbid")

    cell_voltages_v: list[float] = Field(
        min_length=2,
        description="Cell voltages in volts.",
    )


class VoltageSpreadOutput(BaseModel):
    """Output contract for cell-voltage spread analysis."""

    model_config = ConfigDict(extra="forbid")

    minimum_voltage_v: float
    maximum_voltage_v: float
    voltage_spread_v: float
    minimum_cell_number: int = Field(ge=1)
    maximum_cell_number: int = Field(ge=1)
    trace_id: str


class VoltageSpreadSkill(
    BaseSkill[VoltageSpreadInput, VoltageSpreadOutput]
):
    """Calculate basic cell-voltage consistency indicators."""

    name = "voltage_spread"
    description = (
        "Calculate minimum voltage, maximum voltage, voltage spread, "
        "and corresponding cell numbers."
    )

    input_model = VoltageSpreadInput
    output_model = VoltageSpreadOutput

    def execute(
        self,
        skill_input: VoltageSpreadInput,
        context: SkillContext,
    ) -> dict[str, float | int | str]:
        voltages = skill_input.cell_voltages_v

        minimum_voltage = min(voltages)
        maximum_voltage = max(voltages)

        return {
            "minimum_voltage_v": minimum_voltage,
            "maximum_voltage_v": maximum_voltage,
            "voltage_spread_v": round(
                maximum_voltage - minimum_voltage,
                6,
            ),
            # Python list indices start at zero, while engineering cell
            # numbering starts at one.
            "minimum_cell_number": voltages.index(minimum_voltage) + 1,
            "maximum_cell_number": voltages.index(maximum_voltage) + 1,
            "trace_id": context.trace_id,
        }


def main() -> None:
    """Run the minimal skill without using an LLM or network request."""

    skill = VoltageSpreadSkill()  # 实例化技能

    result = skill.run(
        {
            "cell_voltages_v": [
                3.652,
                3.648,
                3.571,
                3.655,
            ]
        },
        context={
            "trace_id": "minimal-skill-demo",
            "source": "example",
        },
    )

    print("Skill definition:")
    print(skill.definition.model_dump_json(indent=2))

    print("\nValidated result:")
    print(result.model_dump_json(indent=2))

# 保证这段代码只有在直接运行这个文件时才会执行，而作为模块被其他地方import时不会自动跑main()
if __name__ == "__main__":
    main()