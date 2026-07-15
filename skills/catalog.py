"""PowerAgent默认动力系统Skill目录。将具体技能实现汇总在一起，提供一个统一的入口函数来批量创建它们"""

from __future__ import annotations

from typing import Any

from skills.base_skill import BaseSkill
from skills.battery_analysis_skill import (
    BatteryAnalysisSkill,
)
from skills.charging_analysis_skill import (
    ChargingAnalysisSkill,
)
from skills.diagnosis_skill import DiagnosisSkill
from skills.knowledge_skill import KnowledgeLookupSkill
from skills.report_skill import ReportGenerationSkill
from skills.thermal_analysis_skill import (
    ThermalAnalysisSkill,
)


def create_default_skills() -> tuple[
    BaseSkill[Any, Any],
    ...,
]:
    """创建默认动力系统Skill实例。

    返回新实例，避免不同Registry之间共享可变运行状态。
    """

    return (
        KnowledgeLookupSkill(),
        BatteryAnalysisSkill(),
        ThermalAnalysisSkill(),
        ChargingAnalysisSkill(),
        DiagnosisSkill(),
        ReportGenerationSkill(),
    )