"""动力电池参数寻优Skill核心功能测试。

覆盖正常推荐、无可行方案和非法搜索空间三个核心场景。
"""

from __future__ import annotations

import pytest

from skills.exceptions import SkillInputValidationError
from skills.optimization_skill import (
    OptimizationSkill,
    OptimizationStatus,
)


def test_optimization_selects_best_feasible_candidate() -> None:
    """验证能够从可行候选中选择综合评分最高的方案。"""

    skill = OptimizationSkill()

    result = skill.run(
        {
            "current_soc_pct": 80.0,
            "current_pack_voltage_v": 380.0,
            "current_maximum_temperature_c": 32.0,
            "current_charging_current_a": 25.0,
            "candidate_charging_currents_a": [
                10.0,
                18.0,
                25.0,
            ],
            "candidate_cooling_powers_w": [
                0.0,
                20.0,
            ],
            "forecast_minutes": 20.0,
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

    assert result.status == OptimizationStatus.SUCCESS
    assert result.evaluated_candidate_count == 6
    assert result.feasible_candidate_count == 6

    assert result.recommended_candidate is not None
    assert (
        result.recommended_candidate
        .prediction.is_feasible
        is True
    )
    assert result.recommended_candidate.score is not None

    # 当前权重下，25 A且不启用额外冷却的方案得分最高
    assert (
        result.recommended_candidate
        .candidate_charging_current_a
        == 25.0
    )
    assert (
        result.recommended_candidate.cooling_power_w
        == 0.0
    )

    assert len(result.alternative_candidates) == 3

    assert all(
        candidate.score is not None
        for candidate in result.evaluated_candidates
    )


def test_optimization_returns_no_feasible_solution() -> None:
    """验证所有候选违反约束时不生成推荐方案。-高SOC高电流"""

    skill = OptimizationSkill()

    result = skill.run(
        {
            "current_soc_pct": 95.0,
            "current_pack_voltage_v": 395.0,
            "current_maximum_temperature_c": 35.0,
            "current_charging_current_a": 18.0,
            "candidate_charging_currents_a": [
                30.0,
                40.0,
            ],
            "candidate_cooling_powers_w": [
                0.0,
            ],
            "forecast_minutes": 20.0,
            "maximum_pack_voltage_v": 410.0,
            "maximum_charging_current_a": 50.0,
            "maximum_charging_temperature_c": 50.0,
            "high_soc_threshold_pct": 90.0,
            "high_soc_current_limit_a": 20.0,
        }
    )

    assert (
        result.status
        == OptimizationStatus.NO_FEASIBLE_SOLUTION
    )
    assert result.recommended_candidate is None
    assert result.alternative_candidates == []

    assert result.evaluated_candidate_count == 2
    assert result.feasible_candidate_count == 0

    assert all(
        candidate.score is None
        for candidate in result.evaluated_candidates
    )

    assert all(
        (
            "predicted_high_soc_high_current"
            in candidate.prediction.violated_constraints
        )
        for candidate in result.evaluated_candidates
    )


def test_optimization_rejects_excessive_candidate_space() -> None:
    """验证候选参数组合数量不能超过25个。"""

    skill = OptimizationSkill()

    with pytest.raises(SkillInputValidationError):
        skill.run(
            {
                "current_soc_pct": 80.0,
                "current_pack_voltage_v": 380.0,
                "current_maximum_temperature_c": 32.0,
                "current_charging_current_a": 25.0,
                "candidate_charging_currents_a": [
                    5.0,
                    10.0,
                    15.0,
                    20.0,
                    25.0,
                    30.0,
                ],
                "candidate_cooling_powers_w": [
                    0.0,
                    10.0,
                    20.0,
                    30.0,
                    40.0,
                ],
                "forecast_minutes": 20.0,
                "maximum_pack_voltage_v": 400.0,
                "maximum_charging_current_a": 50.0,
            }
        )