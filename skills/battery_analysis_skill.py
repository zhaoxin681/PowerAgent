"""电池单体电压基础分析Skill。"""

from __future__ import annotations

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    model_validator,
)

from skills.base_skill import BaseSkill
from skills.schemas import RiskLevel, SkillContext


class BatteryAnalysisInput(BaseModel):
    """电池电压分析输入。"""

    model_config = ConfigDict(extra="forbid")

    cell_voltages_v: list[float] = Field(
        min_length=2,
        description="单体电压列表，单位为V。",
    )
    minimum_allowed_voltage_v: float = Field(
        default=2.8,
        gt=0,
    )
    maximum_allowed_voltage_v: float = Field(
        default=4.25,
        gt=0,
    )
    spread_threshold_v: float = Field(
        default=0.05,
        ge=0,
    )
    soc_pct: float | None = Field(
        default=None,
        ge=0,
        le=100,
    )
    pack_current_a: float | None = None
    # 模型级校验器：在所有单个字段各自校验通过、模型实例已经构造完毕后执行
    @model_validator(mode="after")
    def validate_voltage_limits(self) -> "BatteryAnalysisInput":
        """检查电压上下限关系。"""

        if (
            self.minimum_allowed_voltage_v
            >= self.maximum_allowed_voltage_v
        ):
            raise ValueError(
                "minimum_allowed_voltage_v must be lower "
                "than maximum_allowed_voltage_v"
            )

        return self


class BatteryAnalysisOutput(BaseModel):
    """电池电压分析输出。"""

    model_config = ConfigDict(extra="forbid")

    minimum_voltage_v: float
    maximum_voltage_v: float
    average_voltage_v: float
    voltage_spread_v: float
    minimum_cell_number: int = Field(ge=1)
    maximum_cell_number: int = Field(ge=1)
    out_of_range_cell_numbers: list[int]
    consistency_risk: bool
    risk_level: RiskLevel
    rule_evidence: list[str]


class BatteryAnalysisSkill(
    BaseSkill[BatteryAnalysisInput, BatteryAnalysisOutput]
):
    """分析单体电压极值、压差和越界情况。"""

    name = "battery_analysis"
    description = (
        "分析电池单体电压极值、压差、异常单体和一致性风险。"
    )

    input_model = BatteryAnalysisInput
    output_model = BatteryAnalysisOutput

    def execute(
        self,
        skill_input: BatteryAnalysisInput,
        context: SkillContext,
    ) -> dict[str, object]:
        voltages = skill_input.cell_voltages_v

        minimum_voltage = min(voltages)
        maximum_voltage = max(voltages)
        voltage_spread = maximum_voltage - minimum_voltage
        # 1. 检测越界电芯
        out_of_range_cells = [
            index
            for index, voltage in enumerate(voltages, start=1)
            if (
                voltage < skill_input.minimum_allowed_voltage_v
                or voltage > skill_input.maximum_allowed_voltage_v
            )
        ]
        # 2. 判断一致性风险
        consistency_risk = (
            voltage_spread > skill_input.spread_threshold_v
        )
        # 3. 生成‘规则依据’说明文本
        rule_evidence: list[str] = []

        if out_of_range_cells:
            rule_evidence.append(
                "存在单体电压超出允许范围。"
            )

        if consistency_risk:
            rule_evidence.append(
                "单体最大压差超过设定阈值。"
            )

        if not rule_evidence:
            rule_evidence.append(
                "单体电压范围和最大压差均满足规则要求。"
            )
        # 4. 综合判定风险等级
        if out_of_range_cells:
            risk_level = RiskLevel.HIGH
        elif consistency_risk:
            risk_level = RiskLevel.MEDIUM
        else:
            risk_level = RiskLevel.NORMAL
        # 5. 组装最终输出
        return {
            "minimum_voltage_v": minimum_voltage,
            "maximum_voltage_v": maximum_voltage,
            "average_voltage_v": round(
                sum(voltages) / len(voltages),
                6,
            ),
            "voltage_spread_v": round(voltage_spread, 6),
            "minimum_cell_number": (
                voltages.index(minimum_voltage) + 1
            ),
            "maximum_cell_number": (
                voltages.index(maximum_voltage) + 1
            ),
            "out_of_range_cell_numbers": out_of_range_cells,
            "consistency_risk": consistency_risk,
            "risk_level": risk_level,
            "rule_evidence": rule_evidence,
        }