"""动力电池温度状态分析Skill。"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from skills.base_skill import BaseSkill
from skills.schemas import RiskLevel, SkillContext


class ThermalAnalysisInput(BaseModel):
    """温度状态分析输入。"""

    model_config = ConfigDict(extra="forbid")

    temperatures_c: list[float] = Field(
        min_length=2,
        description="温度测点列表，单位为摄氏度。",
    )
    maximum_temperature_threshold_c: float = 50.0
    spread_threshold_c: float = Field(
        default=5.0,
        ge=0,
    )
    ambient_temperature_c: float | None = None


class ThermalAnalysisOutput(BaseModel):
    """温度状态分析输出。"""

    model_config = ConfigDict(extra="forbid")

    minimum_temperature_c: float
    maximum_temperature_c: float
    average_temperature_c: float
    temperature_spread_c: float
    hottest_sensor_number: int = Field(ge=1)
    overtemperature_sensor_numbers: list[int]
    temperature_inconsistency_risk: bool
    risk_level: RiskLevel
    rule_evidence: list[str]


class ThermalAnalysisSkill(
    BaseSkill[ThermalAnalysisInput, ThermalAnalysisOutput]
):
    """分析温度极值、温差和超温状态。"""

    name = "thermal_analysis"
    description = "分析动力电池温度极值、超温测点和温差风险。"

    input_model = ThermalAnalysisInput
    output_model = ThermalAnalysisOutput

    def execute(
        self,
        skill_input: ThermalAnalysisInput,
        context: SkillContext,
    ) -> dict[str, object]:
        temperatures = skill_input.temperatures_c

        minimum_temperature = min(temperatures)
        maximum_temperature = max(temperatures)
        temperature_spread = (
            maximum_temperature - minimum_temperature
        )

        overtemperature_sensors = [
            index
            for index, temperature in enumerate(
                temperatures,
                start=1,
            )
            if (
                temperature
                > skill_input.maximum_temperature_threshold_c
            )
        ]

        inconsistency_risk = (
            temperature_spread
            > skill_input.spread_threshold_c
        )

        rule_evidence: list[str] = []

        if overtemperature_sensors:
            rule_evidence.append(
                "存在温度测点超过最高温度阈值。"
            )

        if inconsistency_risk:
            rule_evidence.append(
                "最大温差超过温差阈值。"
            )

        if not rule_evidence:
            rule_evidence.append(
                "温度极值和温差均满足规则要求。"
            )

        if overtemperature_sensors:
            risk_level = RiskLevel.HIGH
        elif inconsistency_risk:
            risk_level = RiskLevel.MEDIUM
        else:
            risk_level = RiskLevel.NORMAL

        return {
            "minimum_temperature_c": minimum_temperature,
            "maximum_temperature_c": maximum_temperature,
            "average_temperature_c": round(
                sum(temperatures) / len(temperatures),
                6,
            ),
            "temperature_spread_c": round(
                temperature_spread,
                6,
            ),
            "hottest_sensor_number": (
                temperatures.index(maximum_temperature) + 1
            ),
            "overtemperature_sensor_numbers": (
                overtemperature_sensors
            ),
            "temperature_inconsistency_risk": (
                inconsistency_risk
            ),
            "risk_level": risk_level,
            "rule_evidence": rule_evidence,
        }