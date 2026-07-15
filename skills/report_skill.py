"""结构化动力系统报告生成Skill。"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from skills.base_skill import BaseSkill
from skills.schemas import RiskLevel, SkillContext


class ReportGenerationInput(BaseModel):
    """报告生成输入。"""

    model_config = ConfigDict(extra="forbid")

    original_question: str = Field(min_length=1)
    findings: list[str] = Field(min_length=1)
    risk_level: RiskLevel
    recommendations: list[str] = Field(min_length=1)
    evidence: list[str] = Field(default_factory=list)
    unresolved_items: list[str] = Field(
        default_factory=list,
    )
    device_id: str | None = None


class ReportGenerationOutput(BaseModel):
    """结构化报告输出。"""

    model_config = ConfigDict(extra="forbid")

    title: str
    summary: str
    key_findings: list[str]
    risk_level: RiskLevel
    recommended_actions: list[str]
    evidence: list[str]
    unresolved_items: list[str]


class ReportGenerationSkill(
    BaseSkill[
        ReportGenerationInput,
        ReportGenerationOutput,
    ]
):
    """根据分析结果生成确定性结构化报告。"""

    name = "report_generation"
    description = "将动力系统分析和诊断结果整理为结构化报告。"

    input_model = ReportGenerationInput
    output_model = ReportGenerationOutput

    def execute(
        self,
        skill_input: ReportGenerationInput,
        context: SkillContext,
    ) -> dict[str, object]:
        # 1. 生成设备描述文本
        device_text = (
            f"设备{skill_input.device_id}"
            if skill_input.device_id
            else "动力系统设备"
        )

        return {
            # 2. 拼装标题
            "title": f"{device_text}异常分析报告",
            # 3. 拼接摘要
            "summary": (
                f"针对“{skill_input.original_question}”，"
                f"共形成{len(skill_input.findings)}项关键发现，"
                f"当前风险等级为"
                f"{skill_input.risk_level.value}。"
            ),
            "key_findings": skill_input.findings,
            "risk_level": skill_input.risk_level,
            "recommended_actions": (
                skill_input.recommendations
            ),
            "evidence": skill_input.evidence,
            "unresolved_items": (
                skill_input.unresolved_items
            ),
        }