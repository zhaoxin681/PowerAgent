"""首批动力系统Skills核心功能测试。
将创建的6个真实技能一起注册到Registry里，模拟真实端对端调用场景，验证整套系统组合起来是否协同工作正常"""

from __future__ import annotations

import pytest

from agent_core import SkillRegistry
from skills import (
    RecommendedAction,
    RiskLevel,
    SkillInputValidationError,
    create_default_skills,
)

# 注册所有技能
def create_registry() -> SkillRegistry:
    """创建包含默认Skill的测试Registry。"""

    registry = SkillRegistry()

    for skill in create_default_skills():
        registry.register(skill)

    return registry

"""
逐个测试用例解析
"""
# 验证技能全部成功注册
def test_default_skills_can_register_and_generate_schemas() -> None:
    registry = create_registry()

    names = [
        item.name
        for item in registry.list_skills()
    ]

    assert names == [
        "battery_analysis",
        "charging_analysis",
        "diagnosis",
        "knowledge_lookup",
        "report_generation",
        "thermal_analysis",
    ]

    assert len(registry.get_tool_schemas()) == 6

# 验证电压/温度分析
def test_battery_and_thermal_risk_rules() -> None:
    registry = create_registry()

    battery_result = registry.invoke(
        "battery_analysis",
        {
            "cell_voltages_v": [
                3.65,
                3.64,
                3.50,
            ],
            "spread_threshold_v": 0.05,
        },
    )

    thermal_result = registry.invoke(
        "thermal_analysis",
        {
            "temperatures_c": [
                26.0,
                27.0,
                55.0,
            ]
        },
    )

    assert battery_result.consistency_risk is True
    assert battery_result.minimum_cell_number == 3
    assert battery_result.risk_level == RiskLevel.MEDIUM

    assert thermal_result.risk_level == RiskLevel.HIGH
    assert thermal_result.hottest_sensor_number == 3

# 充电分析测试
def test_charging_analysis_prioritizes_stop_action() -> None:
    registry = create_registry()

    result = registry.invoke(
        "charging_analysis",
        {
            "pack_voltage_v": 410.0,
            "charging_current_a": 30.0,
            "soc_pct": 95.0,
            "maximum_temperature_c": 55.0,
            "maximum_pack_voltage_v": 400.0,
            "maximum_charging_current_a": 50.0,
        },
    )

    assert result.risk_level == RiskLevel.HIGH
    assert (
        result.recommended_action
        == RecommendedAction.STOP_CHARGING
    )

# 四个技能串联测试，模拟一次完整的端到端业务流程：知识查询->诊断->生成报告
def test_knowledge_diagnosis_and_report_flow() -> None:
    registry = create_registry()

    knowledge = registry.invoke(
        "knowledge_lookup",
        {"term": "SOC"},
    )

    diagnosis = registry.invoke(
        "diagnosis",
        {
            "issue_summary": "第3号单体压差持续扩大",
            "battery_risk": True,
            "abnormal_cell_numbers": [3],
        },
    )

    report = registry.invoke(
        "report_generation",
        {
            "original_question": (
                "第3号单体压差持续扩大"
            ),
            "findings": [
                diagnosis.primary_cause,
                knowledge.explanation,
            ],
            "risk_level": diagnosis.risk_level,
            "recommendations": (
                diagnosis.verification_steps
            ),
            "evidence": diagnosis.evidence,
            "unresolved_items": [
                "需要继续确认异常是否持续。"
            ],
        },
    )

    assert knowledge.found is True
    assert diagnosis.primary_cause == "电芯电压一致性异常"
    assert report.risk_level == RiskLevel.MEDIUM
    assert len(report.key_findings) == 2

# 验证电压字段约束
def test_invalid_skill_input_is_rejected() -> None:
    registry = create_registry()

    with pytest.raises(SkillInputValidationError):
        registry.invoke(
            "battery_analysis",
            {
                "cell_voltages_v": [3.6],
            },
        )