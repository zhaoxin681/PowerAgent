"""基于规则证据的动力系统诊断Skill。将多个分析技能的结论作为输入进行二次综合、给出一个整体诊断"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from skills.base_skill import BaseSkill
from skills.schemas import RiskLevel, SkillContext


class DiagnosisInput(BaseModel):
    """规则诊断输入。"""

    model_config = ConfigDict(extra="forbid")

    # 问题描述
    issue_summary: str = Field(min_length=1)
    # 来自其他技能的风险信号
    battery_risk: bool = False
    thermal_risk: bool = False
    charging_risk: bool = False

    abnormal_cell_numbers: list[int] = Field(
        default_factory=list,
    )
    abnormal_sensor_numbers: list[int] = Field(
        default_factory=list,
    )
    violated_constraints: list[str] = Field(
        default_factory=list,
    )


class DiagnosisOutput(BaseModel):
    """规则诊断输出。"""

    model_config = ConfigDict(extra="forbid")

    primary_cause: str
    alternative_causes: list[str]
    risk_level: RiskLevel
    verification_steps: list[str]
    immediate_action_required: bool
    evidence: list[str]
    uncertainty_statement: str


class DiagnosisSkill(
    BaseSkill[DiagnosisInput, DiagnosisOutput]
):
    """根据已有规则结果生成候选诊断。"""

    name = "diagnosis"
    description = "根据电池、热管理和充电分析结果生成候选诊断。"

    input_model = DiagnosisInput
    output_model = DiagnosisOutput

    def execute(
        self,
        skill_input: DiagnosisInput,
        context: SkillContext,
    ) -> dict[str, object]:
        # 1. 根据三类风险信号，拼出候选原因列表
        causes: list[str] = []

        if skill_input.charging_risk:
            causes.append("充电过程约束异常")

        if skill_input.thermal_risk:
            causes.append("动力电池热状态异常")

        if skill_input.battery_risk:
            causes.append("电芯电压一致性异常")

        if causes:
            primary_cause = causes[0]  # 第一个为主要原因
            alternative_causes = causes[1:]  # 其余为备选原因
        else:
            primary_cause = "暂未发现明确异常"
            alternative_causes = []

        # 2. 判定整体风险等级
        if (
            skill_input.charging_risk
            or skill_input.thermal_risk
        ):
            risk_level = RiskLevel.HIGH
        elif skill_input.battery_risk:
            risk_level = RiskLevel.MEDIUM
        else:
            risk_level = RiskLevel.NORMAL

        # 3. 组装证据列表
        evidence: list[str] = []

        if skill_input.abnormal_cell_numbers:
            evidence.append(
                "异常单体编号："
                + ", ".join(
                    str(item)
                    for item in skill_input.abnormal_cell_numbers
                )
            )

        if skill_input.abnormal_sensor_numbers:
            evidence.append(
                "异常温度测点："
                + ", ".join(
                    str(item)
                    for item in skill_input.abnormal_sensor_numbers
                )
            )

        if skill_input.violated_constraints:
            evidence.append(
                "违反约束："
                + ", ".join(
                    skill_input.violated_constraints
                )
            )

        if not evidence:
            evidence.append("当前仅有问题描述，缺少量化异常证据。")

        # 4. 固定的核实步骤建议
        verification_steps = [
            "复核原始电压、温度、电流和SOC测量数据。",
            "检查异常测点及其相邻测点的变化趋势。",
            "结合历史工况确认异常是否持续存在。",
        ]

        # 5. 组装最终输出
        return {
            "primary_cause": primary_cause,
            "alternative_causes": alternative_causes,
            "risk_level": risk_level,
            "verification_steps": verification_steps,
            "immediate_action_required": (
                skill_input.charging_risk
                or skill_input.thermal_risk
            ),
            "evidence": evidence,
            "uncertainty_statement": (
                "该结果属于规则驱动的候选诊断，"
                "仍需结合原始数据和专业人员复核。"
            ),
        }