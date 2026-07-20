"""云端策略模拟下发Skill核心功能测试。

覆盖自动下发就绪、人工复核和安全阻断三个核心场景。
"""

from __future__ import annotations

from skills.cloud_dispatch_skill import (
    CloudDispatchSkill,
    DispatchStatus,
)
from skills.digital_twin_skill import DigitalTwinOutput
from skills.optimization_skill import (
    CandidateEvaluation,
    OptimizationStatus,
)
from skills.schemas import RiskLevel


def create_feasible_candidate(
    *,
    charging_current_a: float = 18.0,
    cooling_power_w: float = 20.0,
) -> CandidateEvaluation:
    """创建通过数字孪生安全检查的候选方案。"""

    prediction = DigitalTwinOutput(
        predicted_soc_pct=86.0,
        predicted_pack_voltage_v=390.0,
        predicted_maximum_temperature_c=35.0,
        soc_increase_pct=6.0,
        voltage_margin_v=10.0,
        temperature_margin_c=15.0,
        violated_constraints=[],
        is_feasible=True,
        risk_level=RiskLevel.NORMAL,
        model_assumptions=[
            "使用简化模型进行测试。",
        ],
        rule_evidence=[
            "候选参数满足安全约束。",
        ],
    )

    return CandidateEvaluation(
        candidate_charging_current_a=(
            charging_current_a
        ),
        cooling_power_w=cooling_power_w,
        score=0.85,
        prediction=prediction,
    )


def test_cloud_dispatch_returns_ready_state() -> None:
    """验证安全方案获得授权后进入自动下发就绪状态。"""

    skill = CloudDispatchSkill()
    candidate = create_feasible_candidate()

    result = skill.run(
        {
            "optimization_status": (
                OptimizationStatus.SUCCESS
            ),
            "recommended_candidate": candidate,
            "optimization_reason": (
                "该方案满足全部约束且综合评分最高。"
            ),
            "current_risk_level": RiskLevel.NORMAL,
            "strategy_id": "STRATEGY-001",
            "strategy_version": "1.0.0",
            "target_device_id": "PACK-001",
            "valid_for_minutes": 30,
            "allow_automatic_dispatch": True,
            "force_manual_review": False,
            "maximum_dispatch_current_a": 30.0,
            "maximum_dispatch_cooling_power_w": 50.0,
        },
        context={
            "trace_id": "trace-ready-001",
            "source": "test",
        },
    )

    assert result.status == DispatchStatus.READY
    assert result.strategy is not None
    assert result.strategy.simulation_only is True

    assert result.strategy.charging_current_a == 18.0
    assert result.strategy.cooling_power_w == 20.0
    assert result.strategy.target_device_id == "PACK-001"

    assert result.safety_checks_passed is True
    assert result.requires_manual_review is False
    assert result.blocking_reasons == []
    assert result.source_trace_id == "trace-ready-001"


def test_cloud_dispatch_requires_manual_review() -> None:
    """验证中风险状态下策略必须进入人工复核。"""

    skill = CloudDispatchSkill()
    candidate = create_feasible_candidate()

    result = skill.run(
        {
            "optimization_status": (
                OptimizationStatus.SUCCESS
            ),
            "recommended_candidate": candidate,
            "optimization_reason": (
                "该方案满足数字孪生安全约束。"
            ),
            "current_risk_level": RiskLevel.MEDIUM,
            "strategy_id": "STRATEGY-002",
            "target_device_id": "PACK-002",
            "allow_automatic_dispatch": True,
            "force_manual_review": False,
            "maximum_dispatch_current_a": 30.0,
            "maximum_dispatch_cooling_power_w": 50.0,
        }
    )

    assert (
        result.status
        == DispatchStatus.REQUIRES_REVIEW
    )
    assert result.strategy is not None
    assert result.safety_checks_passed is True
    assert result.requires_manual_review is True
    assert result.blocking_reasons == []

    assert any(
        "中风险" in evidence
        for evidence in result.decision_evidence
    )


def test_cloud_dispatch_blocks_excessive_current() -> None:
    """验证推荐电流超过下发层权限时阻断策略。"""

    skill = CloudDispatchSkill()

    candidate = create_feasible_candidate(
        charging_current_a=40.0,
        cooling_power_w=20.0,
    )

    result = skill.run(
        {
            "optimization_status": (
                OptimizationStatus.SUCCESS
            ),
            "recommended_candidate": candidate,
            "optimization_reason": (
                "该方案通过数字孪生安全约束。"
            ),
            "current_risk_level": RiskLevel.NORMAL,
            "strategy_id": "STRATEGY-003",
            "target_device_id": "PACK-003",
            "allow_automatic_dispatch": True,
            "maximum_dispatch_current_a": 30.0,
            "maximum_dispatch_cooling_power_w": 50.0,
        }
    )

    assert result.status == DispatchStatus.BLOCKED
    assert result.strategy is None
    assert result.source_candidate is not None

    assert result.safety_checks_passed is False
    assert result.requires_manual_review is True

    assert (
        "dispatch_current_limit_exceeded"
        in result.blocking_reasons
    )