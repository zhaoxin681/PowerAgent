"""简化数字孪生Skill核心功能测试。
包括 正常场景、危险场景、输入校验失败场景。"""

from __future__ import annotations

import pytest

from skills.digital_twin_skill import DigitalTwinSkill
from skills.exceptions import SkillInputValidationError
from skills.schemas import RiskLevel


def test_digital_twin_predicts_feasible_state() -> None:
    """验证正常候选参数能够生成可行预测。"""

    skill = DigitalTwinSkill()

    result = skill.run(
        {
            "current_soc_pct": 80.0,
            "current_pack_voltage_v": 380.0,
            "current_maximum_temperature_c": 32.0,
            "current_charging_current_a": 25.0,
            "candidate_charging_current_a": 18.0,
            "forecast_minutes": 20.0,
            "cooling_power_w": 20.0,
            "battery_capacity_ah": 100.0,
            "pack_internal_resistance_ohm": 0.05,
            "effective_thermal_capacity_j_per_c": (
                100000.0
            ),
            "ocv_rise_per_soc_pct_v": 0.05,
            "charging_efficiency": 0.98,
            "ambient_temperature_c": 25.0,
            "maximum_pack_voltage_v": 400.0,
            "maximum_charging_current_a": 50.0,
            "maximum_charging_temperature_c": 50.0,
            "high_soc_threshold_pct": 90.0,
            "high_soc_current_limit_a": 20.0,
        }
    )

    assert result.predicted_soc_pct == pytest.approx(
        85.88
    )
    assert result.soc_increase_pct == pytest.approx(
        5.88
    )
    assert result.predicted_pack_voltage_v == pytest.approx(
        379.944
    )
    assert (
        result.predicted_maximum_temperature_c
        == pytest.approx(31.9544)
    )

    assert result.voltage_margin_v > 0
    assert result.temperature_margin_c > 0
    assert result.violated_constraints == []
    assert result.is_feasible is True
    assert result.risk_level == RiskLevel.NORMAL
    assert result.model_assumptions
    assert result.rule_evidence == [
        (
            "候选充电参数在当前简化模型和"
            "安全边界下可行。"
        )
    ]


def test_digital_twin_identifies_dangerous_candidate() -> None:
    """验证危险候选参数能够触发高风险约束。"""

    skill = DigitalTwinSkill()

    result = skill.run(
        {
            "current_soc_pct": 50.0,
            "current_pack_voltage_v": 399.0,
            "current_maximum_temperature_c": 44.0,
            "current_charging_current_a": 10.0,
            "candidate_charging_current_a": 100.0,
            "forecast_minutes": 60.0,
            "cooling_power_w": 0.0,
            "battery_capacity_ah": 100.0,
            "pack_internal_resistance_ohm": 0.05,
            "effective_thermal_capacity_j_per_c": (
                1000.0
            ),
            "ocv_rise_per_soc_pct_v": 0.05,
            "charging_efficiency": 0.98,
            "ambient_temperature_c": 25.0,
            "maximum_pack_voltage_v": 400.0,
            "maximum_charging_current_a": 50.0,
            "maximum_charging_temperature_c": 45.0,
            "high_soc_threshold_pct": 90.0,
            "high_soc_current_limit_a": 20.0,
        }
    )

    assert (
        "candidate_charging_overcurrent"
        in result.violated_constraints
    )
    assert (
        "predicted_pack_overvoltage"
        in result.violated_constraints
    )
    assert (
        "predicted_charging_overtemperature"
        in result.violated_constraints
    )
    assert (
        "predicted_high_soc_high_current"
        in result.violated_constraints
    )

    assert result.predicted_soc_pct == 100.0
    assert result.voltage_margin_v < 0
    assert result.temperature_margin_c < 0
    assert result.is_feasible is False
    assert result.risk_level == RiskLevel.HIGH


def test_digital_twin_rejects_invalid_limits() -> None:
    """验证高SOC电流上限不能大于普通电流上限。"""

    skill = DigitalTwinSkill()

    with pytest.raises(SkillInputValidationError):
        skill.run(
            {
                "current_soc_pct": 80.0,
                "current_pack_voltage_v": 380.0,
                "current_maximum_temperature_c": 32.0,
                "current_charging_current_a": 25.0,
                "candidate_charging_current_a": 18.0,
                "forecast_minutes": 20.0,
                "maximum_pack_voltage_v": 400.0,
                "maximum_charging_current_a": 30.0,
                "high_soc_current_limit_a": 40.0,
            }
        )