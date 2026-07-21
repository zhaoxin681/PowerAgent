"""研发分析数据模型核心测试。"""

import pytest
from pydantic import ValidationError

from agent_core.schemas import (
    PowerSystemIssue,
    Severity,
    Subsystem,
    TaskType,
)
from skills.schemas import RiskLevel
from workflows.rnd_models import (
    EvidenceSource,
    ExperimentCriterion,
    KnownFact,
    RndAnalysisResult,
    RndAnalysisStatus,
    RndPriority,
    RootCauseHypothesis,
    RootCauseStatus,
    TeamAssignment,
    TeamName,
    ValidationExperiment,
)


def make_issue(
    severity: Severity = Severity.MEDIUM,
) -> PowerSystemIssue:
    """构造研发分析问题。"""

    return PowerSystemIssue(
        raw_text=(
            "快充后段电流下降，同时最高温度偏高"
        ),
        subsystem=Subsystem.MULTI_SYSTEM,
        task_type=TaskType.RND_ANALYSIS,
        symptoms=[
            "SOC超过80%后充电电流下降",
            "最高温度偏高",
        ],
        operating_conditions=[],
        user_hypotheses=[],
        requested_outputs=[
            "根因分析",
            "验证实验",
            "团队分工",
        ],
        missing_information=[],
        severity=severity,
        confidence=0.9,
    )


def make_fact(
    *,
    verified: bool = True,
) -> KnownFact:
    """构造已知事实。"""

    return KnownFact(
        fact_id="fact_temp_high",
        description="SOC超过80%后最高温度达到52℃",
        subsystem=Subsystem.THERMAL,
        source=EvidenceSource.SKILL_RESULT,
        source_reference="thermal_analysis",
        is_verified=verified,
        confidence=0.95,
    )


def make_hypothesis(
    *,
    status: RootCauseStatus = (
        RootCauseStatus.SUPPORTED
    ),
) -> RootCauseHypothesis:
    """构造候选根因。"""

    return RootCauseHypothesis(
        hypothesis_id="hyp_cooling_limit",
        description="高SOC阶段冷却能力不足触发限流",
        subsystem=Subsystem.THERMAL,
        status=status,
        priority=RndPriority.P1,
        supporting_fact_ids=["fact_temp_high"],
        contradicting_fact_ids=[],
        reasoning="温度升高与充电限流同步出现",
        confidence=(
            0.9
            if status == RootCauseStatus.CONFIRMED
            else 0.75
        ),
        potential_impact="延长快充时间并增加热风险",
        needs_human_review=False,
    )


def make_experiment(
    *,
    risk_level: RiskLevel = RiskLevel.MEDIUM,
    needs_human_approval: bool = False,
) -> ValidationExperiment:
    """构造验证实验。"""

    return ValidationExperiment(
        experiment_id="exp_cooling_ab",
        title="冷却功率A/B对比实验",
        linked_hypothesis_ids=[
            "hyp_cooling_limit"
        ],
        objective="判断冷却能力是否导致后段限流",
        required_inputs=[
            "充电电流",
            "单体温度",
        ],
        controlled_variables=[
            "初始SOC",
            "环境温度",
        ],
        steps=[
            "固定初始SOC和环境温度",
            "分别使用两档冷却功率完成快充",
        ],
        observed_metrics=[
            "最高温度",
            "SOC 80%后的平均充电电流",
        ],
        expected_observation=(
            "提高冷却功率后温度下降且限流减轻"
        ),
        criteria=[
            ExperimentCriterion(
                metric="SOC 80%后的平均充电电流",
                measurement_method="对比两组充电日志",
                pass_condition=(
                    "提高冷却后平均电流明显上升"
                ),
                fail_condition=(
                    "两组平均电流无明显差异"
                ),
            )
        ],
        stop_conditions=[
            "最高温度超过安全上限"
        ],
        safety_requirements=(
            ["配置超温保护"]
            if risk_level == RiskLevel.HIGH
            else []
        ),
        deliverables=[
            "A/B实验数据和分析报告"
        ],
        risk_level=risk_level,
        needs_human_approval=needs_human_approval,
    )


def make_assignment() -> TeamAssignment:
    """构造团队任务。"""

    return TeamAssignment(
        assignment_id="assign_thermal_test",
        experiment_ids=["exp_cooling_ab"],
        owner=TeamName.TEST_VALIDATION,
        collaborators=[
            TeamName.THERMAL_MANAGEMENT
        ],
        reviewers=[
            TeamName.FUNCTIONAL_SAFETY
        ],
        task="执行冷却功率A/B快充实验",
        input_dependencies=[
            "试验车辆和标定参数"
        ],
        deliverables=[
            "实验日志",
            "对比分析报告",
        ],
        completion_criteria=[
            "两组实验均完成且数据有效"
        ],
        blockers=[],
    )


def test_valid_rnd_analysis_result() -> None:
    """合法结果应通过全链路校验。"""

    result = RndAnalysisResult(
        status=RndAnalysisStatus.COMPLETED,
        trace_id="trace-week6",
        issue=make_issue(),
        summary="冷却能力不足是当前优先验证方向",
        known_facts=[make_fact()],
        hypotheses=[make_hypothesis()],
        experiments=[make_experiment()],
        team_assignments=[make_assignment()],
        dependencies=[],
        risks=[],
        overall_risk_level=RiskLevel.MEDIUM,
        needs_human_review=False,
        unresolved_items=[
            "尚缺少泵速和冷却液流量"
        ],
    )

    assert (
        result.hypotheses[0].priority
        == RndPriority.P1
    )


def test_supported_hypothesis_requires_evidence() -> None:
    """有证据结论不得缺少支持事实。"""

    with pytest.raises(
        ValidationError,
        match="必须有支持事实",
    ):
        RootCauseHypothesis(
            hypothesis_id="hyp_without_evidence",
            description="冷却能力不足",
            subsystem=Subsystem.THERMAL,
            status=RootCauseStatus.SUPPORTED,
            priority=RndPriority.P1,
            supporting_fact_ids=[],
            contradicting_fact_ids=[],
            reasoning="仅根据经验判断",
            confidence=0.75,
            potential_impact="可能触发限流",
            needs_human_review=True,
        )


def test_high_risk_experiment_requires_approval() -> None:
    """高风险实验必须经过人工审批。"""

    with pytest.raises(
        ValidationError,
        match="必须经过人工审批",
    ):
        make_experiment(
            risk_level=RiskLevel.HIGH,
            needs_human_approval=False,
        )


def test_result_rejects_invalid_reference() -> None:
    """实验不得引用不存在的候选根因。"""

    experiment = make_experiment().model_copy(
        update={
            "linked_hypothesis_ids": [
                "hyp_not_found"
            ]
        }
    )

    with pytest.raises(
        ValidationError,
        match="不存在的hypothesis_id",
    ):
        RndAnalysisResult(
            status=RndAnalysisStatus.COMPLETED,
            trace_id="trace-invalid-reference",
            issue=make_issue(),
            summary="测试无效引用",
            known_facts=[make_fact()],
            hypotheses=[make_hypothesis()],
            experiments=[experiment],
            team_assignments=[make_assignment()],
            dependencies=[],
            risks=[],
            overall_risk_level=RiskLevel.MEDIUM,
            needs_human_review=False,
            unresolved_items=[],
        )


def test_confirmed_hypothesis_requires_verified_fact() -> None:
    """确认根因必须由已验证事实支撑。"""

    with pytest.raises(
        ValidationError,
        match="已验证事实",
    ):
        RndAnalysisResult(
            status=RndAnalysisStatus.COMPLETED,
            trace_id="trace-unverified-fact",
            issue=make_issue(),
            summary="尝试确认冷却能力不足",
            known_facts=[
                make_fact(verified=False)
            ],
            hypotheses=[
                make_hypothesis(
                    status=RootCauseStatus.CONFIRMED
                )
            ],
            experiments=[make_experiment()],
            team_assignments=[make_assignment()],
            dependencies=[],
            risks=[],
            overall_risk_level=RiskLevel.MEDIUM,
            needs_human_review=False,
            unresolved_items=[],
        )


def test_high_severity_requires_human_review() -> None:
    """高严重度问题必须保留人工复核标志。"""

    with pytest.raises(
        ValidationError,
        match="必须要求人工复核",
    ):
        RndAnalysisResult(
            status=RndAnalysisStatus.COMPLETED,
            trace_id="trace-high-severity",
            issue=make_issue(Severity.HIGH),
            summary="高严重度问题测试",
            known_facts=[make_fact()],
            hypotheses=[make_hypothesis()],
            experiments=[make_experiment()],
            team_assignments=[make_assignment()],
            dependencies=[],
            risks=[],
            overall_risk_level=RiskLevel.MEDIUM,
            needs_human_review=False,
            unresolved_items=[],
        )