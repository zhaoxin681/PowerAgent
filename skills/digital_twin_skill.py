"""动力电池简化充电数字孪生Skill。用于在给定候选充电参数的情况下，预测电池未来一段时间的状态变化，
判断是否安全可行。    整体机构分为：输入模型、输出模型、执行逻辑。"""

from __future__ import annotations

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    model_validator,
)

from skills.base_skill import BaseSkill
from skills.schemas import RiskLevel, SkillContext


class DigitalTwinInput(BaseModel):
    """简化充电数字孪生输入。"""

    model_config = ConfigDict(extra="forbid")

    # 当前动力电池状态
    current_soc_pct: float = Field(
        ge=0,
        le=100,
        description="当前SOC，单位为百分比。",
    )
    current_pack_voltage_v: float = Field(
        gt=0,
        description="当前电池组端电压，单位为V。",
    )
    current_maximum_temperature_c: float = Field(
        description="当前最高温度，单位为摄氏度。",
    )
    current_charging_current_a: float = Field(
        ge=0,
        description="当前充电电流，单位为A。",
    )

    # 候选控制参数
    candidate_charging_current_a: float = Field(
        ge=0,
        description="待评估的候选充电电流，单位为A。",
    )
    forecast_minutes: float = Field(
        gt=0,
        le=120,
        description="预测时间长度，单位为分钟。",
    )
    cooling_power_w: float = Field(
        default=0.0,
        ge=0,
        description="预测期间的等效冷却功率，单位为W。",
    )

    # 简化电池模型参数
    battery_capacity_ah: float = Field(
        default=100.0,
        gt=0,
        description="电池组额定容量，单位为Ah。",
    )
    pack_internal_resistance_ohm: float = Field(
        default=0.05,
        ge=0,
        description="电池组等效内阻，单位为欧姆。",
    )
    effective_thermal_capacity_j_per_c: float = Field(
        default=100000.0,
        gt=0,
        description="电池组等效热容量，单位为J/℃。",
    )
    ocv_rise_per_soc_pct_v: float = Field(
        default=0.05,
        ge=0,
        description="SOC每增加1%对应的等效开路电压增量，单位为V。",
    )
    charging_efficiency: float = Field(
        default=0.98,
        gt=0,
        le=1,
        description="充电库仑效率。",
    )
    ambient_temperature_c: float = Field(
        default=25.0,
        description="环境温度，单位为摄氏度。",
    )

    # 充电安全边界
    maximum_pack_voltage_v: float = Field(
        gt=0,
        description="允许的最高电池组电压，单位为V。",
    )
    maximum_charging_current_a: float = Field(
        gt=0,
        description="允许的最大充电电流，单位为A。",
    )
    maximum_charging_temperature_c: float = Field(
        default=50.0,
        description="允许的最高充电温度，单位为摄氏度。",
    )
    high_soc_threshold_pct: float = Field(
        default=90.0,
        ge=0,
        le=100,
        description="进入高SOC阶段的阈值。",
    )
    high_soc_current_limit_a: float = Field(
        default=20.0,
        ge=0,
        description="高SOC阶段允许的最大充电电流，单位为A。",
    )

    @model_validator(mode="after")
    def validate_current_limits(self) -> "DigitalTwinInput":
        """检查普通充电电流上限和高SOC电流上限的关系。"""

        if (
            self.high_soc_current_limit_a
            > self.maximum_charging_current_a
        ):
            raise ValueError(
                "high_soc_current_limit_a must not exceed "
                "maximum_charging_current_a"
            )

        return self


class DigitalTwinOutput(BaseModel):
    """简化充电数字孪生输出。"""

    model_config = ConfigDict(extra="forbid")

    predicted_soc_pct: float = Field(
        ge=0,
        le=100,
    )
    predicted_pack_voltage_v: float = Field(
        gt=0,
    )
    predicted_maximum_temperature_c: float

    soc_increase_pct: float = Field(
        ge=0,
    )
    voltage_margin_v: float
    temperature_margin_c: float

    violated_constraints: list[str]
    is_feasible: bool
    risk_level: RiskLevel

    model_assumptions: list[str]
    rule_evidence: list[str]


class DigitalTwinSkill(
    BaseSkill[DigitalTwinInput, DigitalTwinOutput]
):
    """预测候选充电参数下的SOC、电压和温度变化。"""

    name = "digital_twin"
    description = (
        "使用简化数字孪生模型预测候选充电参数下的"
        "SOC、电池组电压、最高温度和安全约束。"
    )

    input_model = DigitalTwinInput
    output_model = DigitalTwinOutput

    def execute(
        self,
        skill_input: DigitalTwinInput,
        context: SkillContext,
    ) -> dict[str, object]:
        """执行简化数字孪生状态预测。"""

        # 1. 将预测时间转换为小时和秒
        forecast_hours = (
            skill_input.forecast_minutes / 60.0
        )
        forecast_seconds = (
            skill_input.forecast_minutes * 60.0
        )

        # 2. 使用库仑积分估算SOC变化
        charged_capacity_ah = (
            skill_input.candidate_charging_current_a
            * forecast_hours
            * skill_input.charging_efficiency
        )

        theoretical_soc_increase_pct = (
            charged_capacity_ah
            / skill_input.battery_capacity_ah
            * 100.0
        )

        predicted_soc_pct = min(
            100.0,
            (
                skill_input.current_soc_pct
                + theoretical_soc_increase_pct
            ),
        )

        # 使用实际能够增加的SOC，避免SOC达到100%后继续累计
        actual_soc_increase_pct = (
            predicted_soc_pct
            - skill_input.current_soc_pct
        )

        # 3. 使用线性OCV变化和等效内阻预测端电压
        estimated_current_ocv_v = (
            skill_input.current_pack_voltage_v
            - (
                skill_input.current_charging_current_a
                * skill_input.pack_internal_resistance_ohm
            )
        )

        ocv_increase_v = (
            actual_soc_increase_pct
            * skill_input.ocv_rise_per_soc_pct_v
        )

        predicted_pack_voltage_v = (
            estimated_current_ocv_v
            + ocv_increase_v
            + (
                skill_input.candidate_charging_current_a
                * skill_input.pack_internal_resistance_ohm
            )
        )

        # 4. 使用I²R发热和等效冷却功率预测最高温度
        heating_power_w = (
            skill_input.candidate_charging_current_a
            ** 2
            * skill_input.pack_internal_resistance_ohm
        )

        net_heating_power_w = (
            heating_power_w
            - skill_input.cooling_power_w
        )

        temperature_change_c = (
            net_heating_power_w
            * forecast_seconds
            / skill_input.effective_thermal_capacity_j_per_c
        )

        predicted_maximum_temperature_c = max(
            skill_input.ambient_temperature_c,
            (
                skill_input.current_maximum_temperature_c
                + temperature_change_c
            ),
        )

        # 5. 计算电压和温度安全裕度（电压裕度=最大允许电压-预测电压，温度裕度同理）
        voltage_margin_v = (
            skill_input.maximum_pack_voltage_v
            - predicted_pack_voltage_v
        )

        temperature_margin_c = (
            skill_input.maximum_charging_temperature_c
            - predicted_maximum_temperature_c
        )

        # 6. 检查候选参数和预测状态是否违反安全约束
        violated_constraints: list[str] = []

        if (
            skill_input.candidate_charging_current_a
            > skill_input.maximum_charging_current_a
        ):
            violated_constraints.append(
                "candidate_charging_overcurrent"
            )

        if (
            predicted_pack_voltage_v
            > skill_input.maximum_pack_voltage_v
        ):
            violated_constraints.append(
                "predicted_pack_overvoltage"
            )

        if (
            predicted_maximum_temperature_c
            > skill_input.maximum_charging_temperature_c
        ):
            violated_constraints.append(
                "predicted_charging_overtemperature"
            )

        if (
            predicted_soc_pct
            >= skill_input.high_soc_threshold_pct
            and skill_input.candidate_charging_current_a
            > skill_input.high_soc_current_limit_a
        ):
            violated_constraints.append(
                "predicted_high_soc_high_current"
            )

        # 7. 根据约束严重程度确定风险等级
        # 超压/超温->高风险；其他违规->中风险；无违规->正常
        high_risk_constraints = {
            "predicted_pack_overvoltage",
            "predicted_charging_overtemperature",
        }

        if high_risk_constraints.intersection(
            violated_constraints
        ):
            risk_level = RiskLevel.HIGH
        elif violated_constraints:
            risk_level = RiskLevel.MEDIUM
        else:
            risk_level = RiskLevel.NORMAL

        is_feasible = not violated_constraints

        # 8. 生成约束判断依据
        if violated_constraints:
            rule_evidence = [
                f"预测触发约束：{constraint}"
                for constraint in violated_constraints
            ]
        else:
            rule_evidence = [
                (
                    "候选充电参数在当前简化模型和"
                    "安全边界下可行。"
                )
            ]

        # 9. 明确简化数字孪生模型的适用边界
        model_assumptions = [
            "使用恒定充电电流进行预测。",
            "使用库仑积分估算SOC变化。",
            (
                "使用线性OCV变化和等效内阻"
                "估算电池组端电压。"
            ),
            (
                "使用I²R发热与恒定冷却功率"
                "估算最高温度变化。"
            ),
            (
                "预测结果仅用于PowerAgent工作流演示，"
                "不代表真实设备控制结果。"
            ),
        ]

        return {
            "predicted_soc_pct": round(
                predicted_soc_pct,
                6,
            ),
            "predicted_pack_voltage_v": round(
                predicted_pack_voltage_v,
                6,
            ),
            "predicted_maximum_temperature_c": round(
                predicted_maximum_temperature_c,
                6,
            ),
            "soc_increase_pct": round(
                actual_soc_increase_pct,
                6,
            ),
            "voltage_margin_v": round(
                voltage_margin_v,
                6,
            ),
            "temperature_margin_c": round(
                temperature_margin_c,
                6,
            ),
            "violated_constraints": violated_constraints,
            "is_feasible": is_feasible,
            "risk_level": risk_level,
            "model_assumptions": model_assumptions,
            "rule_evidence": rule_evidence,
        }