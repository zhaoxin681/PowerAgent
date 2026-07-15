"""Reusable skills and shared skill contracts for PowerAgent."""

from skills.base_skill import BaseSkill
from skills.exceptions import (
    SkillError,
    SkillExecutionError,
    SkillInputValidationError,
    SkillOutputValidationError,
)
from skills.schemas import SkillContext, SkillDefinition
from skills.battery_analysis_skill import (
    BatteryAnalysisInput,
    BatteryAnalysisOutput,
    BatteryAnalysisSkill,
)
from skills.catalog import create_default_skills
from skills.charging_analysis_skill import (
    ChargingAnalysisInput,
    ChargingAnalysisOutput,
    ChargingAnalysisSkill,
)
from skills.diagnosis_skill import (
    DiagnosisInput,
    DiagnosisOutput,
    DiagnosisSkill,
)
from skills.knowledge_skill import (
    KnowledgeLookupInput,
    KnowledgeLookupOutput,
    KnowledgeLookupSkill,
)
from skills.report_skill import (
    ReportGenerationInput,
    ReportGenerationOutput,
    ReportGenerationSkill,
)
from skills.schemas import RecommendedAction, RiskLevel
from skills.thermal_analysis_skill import (
    ThermalAnalysisInput,
    ThermalAnalysisOutput,
    ThermalAnalysisSkill,
)

__all__ = [
    "BaseSkill",
    "SkillContext",
    "SkillDefinition",
    "SkillError",
    "SkillInputValidationError",
    "SkillExecutionError",
    "SkillOutputValidationError",
    "RiskLevel",
    "RecommendedAction",
    "KnowledgeLookupInput",
    "KnowledgeLookupOutput",
    "KnowledgeLookupSkill",
    "BatteryAnalysisInput",
    "BatteryAnalysisOutput",
    "BatteryAnalysisSkill",
    "ThermalAnalysisInput",
    "ThermalAnalysisOutput",
    "ThermalAnalysisSkill",
    "ChargingAnalysisInput",
    "ChargingAnalysisOutput",
    "ChargingAnalysisSkill",
    "DiagnosisInput",
    "DiagnosisOutput",
    "DiagnosisSkill",
    "ReportGenerationInput",
    "ReportGenerationOutput",
    "ReportGenerationSkill",
    "create_default_skills",
] # 定义了这个包目前正式对外暴露的公共接口