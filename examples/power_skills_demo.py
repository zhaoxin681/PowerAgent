"""首批动力系统Skills业务闭环演示。"""

from __future__ import annotations

from agent_core import SkillRegistry
from skills import create_default_skills


def main() -> None:
    """执行电池、温度、充电、诊断和报告流程。"""

    registry = SkillRegistry()

    for skill in create_default_skills():
        registry.register(skill)

    battery_result = registry.invoke(
        "battery_analysis",
        {
            "cell_voltages_v": [
                3.652,
                3.648,
                3.571,
                3.655,
            ],
            "spread_threshold_v": 0.05,
        },
    )

    thermal_result = registry.invoke(
        "thermal_analysis",
        {
            "temperatures_c": [
                27.0,
                27.5,
                34.2,
                28.1,
            ],
            "spread_threshold_c": 5.0,
        },
    )

    charging_result = registry.invoke(
        "charging_analysis",
        {
            "pack_voltage_v": 395.0,
            "charging_current_a": 28.0,
            "soc_pct": 95.0,
            "maximum_temperature_c": 34.2,
            "maximum_pack_voltage_v": 400.0,
            "maximum_charging_current_a": 50.0,
            "high_soc_current_limit_a": 20.0,
        },
    )

    diagnosis_result = registry.invoke(
        "diagnosis",
        {
            "issue_summary": "电池组压差扩大且温差偏高",
            "battery_risk": (
                battery_result.consistency_risk
            ),
            "thermal_risk": (
                thermal_result
                .temperature_inconsistency_risk
            ),
            "charging_risk": charging_result.has_risk,
            "abnormal_cell_numbers": [
                battery_result.minimum_cell_number
            ],
            "abnormal_sensor_numbers": (
                thermal_result
                .overtemperature_sensor_numbers
            ),
            "violated_constraints": (
                charging_result.violated_constraints
            ),
        },
    )

    report_result = registry.invoke(
        "report_generation",
        {
            "original_question": (
                "电池组压差扩大且温差偏高"
            ),
            "findings": [
                diagnosis_result.primary_cause,
                *diagnosis_result.alternative_causes,
            ],
            "risk_level": diagnosis_result.risk_level,
            "recommendations": (
                diagnosis_result.verification_steps
            ),
            "evidence": diagnosis_result.evidence,
            "unresolved_items": [
                "需要结合历史数据确认异常持续性。"
            ],
            "device_id": "PACK-001",
        },
    )

    print("电池分析结果：")
    print(battery_result.model_dump_json(indent=2))

    print("\n温度分析结果：")
    print(thermal_result.model_dump_json(indent=2))

    print("\n充电分析结果：")
    print(charging_result.model_dump_json(indent=2))

    print("\n候选诊断结果：")
    print(diagnosis_result.model_dump_json(indent=2))

    print("\n结构化报告：")
    print(report_result.model_dump_json(indent=2))


if __name__ == "__main__":
    main()