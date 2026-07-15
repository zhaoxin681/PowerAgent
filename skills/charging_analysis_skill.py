"""充电过程安全约束分析Skill。"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from skills.base_skill import BaseSkill
from skills.schemas import (
    RecommendedAction,
    RiskLevel,
    SkillContext,
)


class ChargingAnalysisInput(BaseModel):
    """充电过程分析输入。"""

    model_config = ConfigDict(extra="forbid")

    pack_voltage_v: float = Field(gt=0)
    charging_current_a: float = Field(ge=0)
    soc_pct: float = Field(ge=0, le=100)
    maximum_temperature_c: float

    maximum_pack_voltage_v: float = Field(gt=0)
    maximum_charging_current_a: float = Field(gt=0)
    maximum_charging_temperature_c: float = 50.0

    high_soc_threshold_pct: float = Field(
        default=90.0,
        ge=0,
        le=100,
    )
    high_soc_current_limit_a: float = Field(
        default=20.0,
        ge=0,
    )


class ChargingAnalysisOutput(BaseModel):
    """充电过程分析输出。"""

    model_config = ConfigDict(extra="forbid")

    violated_constraints: list[str]
    has_risk: bool
    risk_level: RiskLevel
    recommended_action: RecommendedAction
    rule_evidence: list[str]


class ChargingAnalysisSkill(
    BaseSkill[
        ChargingAnalysisInput,
        ChargingAnalysisOutput,
    ]
):
    """检查充电电压、电流、SOC和温度约束。"""

    name = "charging_analysis"
    description = "检查充电过程中的电压、电流、SOC和温度安全约束。"

    input_model = ChargingAnalysisInput
    output_model = ChargingAnalysisOutput

    def execute(
        self,
        skill_input: ChargingAnalysisInput,
        context: SkillContext,
    ) -> dict[str, object]:
        # 1. 逐条检查四类约束
        violated_constraints: list[str] = []

        if (
            skill_input.pack_voltage_v
            > skill_input.maximum_pack_voltage_v
        ):
            violated_constraints.append("pack_overvoltage")

        if (
            skill_input.charging_current_a
            > skill_input.maximum_charging_current_a
        ):
            violated_constraints.append(
                "charging_overcurrent"
            )

        if (
            skill_input.maximum_temperature_c
            > skill_input.maximum_charging_temperature_c
        ):
            violated_constraints.append(
                "charging_overtemperature"
            )

        if (
            skill_input.soc_pct
            >= skill_input.high_soc_threshold_pct
            and skill_input.charging_current_a
            > skill_input.high_soc_current_limit_a
        ):
            violated_constraints.append(
                "high_soc_high_current"
            )

        stop_conditions = {
            "pack_overvoltage",
            "charging_overtemperature",
        }

        # 2. 判断是否需要立即停止充电
        if stop_conditions.intersection(
            violated_constraints
        ):  # 最高优先级：用交集方法检查
            recommended_action = (
                RecommendedAction.STOP_CHARGING
            )
            risk_level = RiskLevel.HIGH
        elif violated_constraints:  # 次级优先：降低功率
            recommended_action = (
                RecommendedAction.REDUCE_POWER
            )  # 最低优先级：正常继续充电
            risk_level = RiskLevel.MEDIUM
        else:
            recommended_action = (
                RecommendedAction.CONTINUE_CHARGING
            )
            risk_level = RiskLevel.NORMAL

        # 3. 生成规则依据
        if violated_constraints:
            rule_evidence = [
                f"触发充电约束：{item}"
                for item in violated_constraints
            ]
        else:
            rule_evidence = [
                "当前充电参数未触发设定约束。"
            ]

        return {
            "violated_constraints": violated_constraints,
            "has_risk": bool(violated_constraints),
            "risk_level": risk_level,
            "recommended_action": recommended_action,
            "rule_evidence": rule_evidence,
        }