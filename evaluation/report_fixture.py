"""Review与Report评测的确定性输入场景。"""

from __future__ import annotations

from dataclasses import dataclass

from agent_core.schemas import (
    PowerSystemIssue,
    Severity,
    Subsystem,
    TaskType,
)
from agent_core.state import (
    WorkflowDecision,
    WorkflowError,
    WorkflowStep,
    WorkflowStepStatus,
)
from agent_core.tool_models import (
    ToolCallingResult,
    ToolCallingStatus,
)
from evaluation.schemas import (
    ReviewReportScenario,
)
from rag.schemas import (
    RAGAnswer,
    RAGCitation,
)
from skills.battery_analysis_skill import (
    BatteryAnalysisOutput,
)
from skills.cloud_dispatch_skill import (
    CloudDispatchOutput,
    DispatchStatus,
    DispatchStrategy,
)
from skills.diagnosis_skill import DiagnosisOutput
from skills.digital_twin_skill import (
    DigitalTwinOutput,
)
from skills.optimization_skill import (
    CandidateEvaluation,
    OptimizationOutput,
    OptimizationStatus,
)
from skills.schemas import RiskLevel


@dataclass(frozen=True)
class ReviewReportFixture:
    """一次Review和Report联合评测输入。"""

    issue: PowerSystemIssue

    plan: tuple[WorkflowStep, ...]

    tool_results: tuple[ToolCallingResult, ...]

    rag_answers: tuple[RAGAnswer, ...]

    errors: tuple[WorkflowError, ...]

    decision: WorkflowDecision | None

    device_id: str | None = None 


def make_issue(
    *,
    raw_text: str,
    severity: Severity = Severity.MEDIUM,
    missing_information: list[str] | None = None,
) -> PowerSystemIssue:
    """构造评测问题。"""

    return PowerSystemIssue(
        raw_text=raw_text,
        subsystem=Subsystem.BATTERY,
        task_type=TaskType.FAULT_DIAGNOSIS,
        symptoms=["动力系统状态异常"],
        operating_conditions=[],
        user_hypotheses=[],
        requested_outputs=["结构化异常报告"],
        missing_information=(
            missing_information or []
        ),
        severity=severity,
        confidence=1.0,
    )


def make_step(
    *,
    target: str,
    status: WorkflowStepStatus,
    sequence: int = 0,
) -> WorkflowStep:
    """构造确定性计划步骤。"""

    return WorkflowStep(
        step_id=f"step_{sequence}",
        sequence=sequence,
        action=f"执行{target}",
        target=target,
        input_keys=["issue"],
        output_key="tool_results",
        status=status,
    )


def make_battery_result(
    *,
    trace_id: str,
) -> ToolCallingResult:
    """构造有效电池分析结果。"""

    output = BatteryAnalysisOutput(
        minimum_voltage_v=3.55,
        maximum_voltage_v=3.64,
        average_voltage_v=3.60,
        voltage_spread_v=0.09,
        minimum_cell_number=3,
        maximum_cell_number=5,
        out_of_range_cell_numbers=[],
        consistency_risk=True,
        risk_level=RiskLevel.MEDIUM,
        rule_evidence=[
            "单体最大压差超过设定阈值。"
        ],
    )

    return ToolCallingResult(
        status=ToolCallingStatus.SUCCESS,
        trace_id=trace_id,
        tool_name="battery_analysis",
        output=output.model_dump(
            mode="json"
        ),
    )


def make_diagnosis_result(
    *,
    trace_id: str,
    placeholder_evidence: bool,
    risk_level: RiskLevel,
) -> ToolCallingResult:
    """构造候选诊断结果。"""

    evidence = (
        [
            "当前仅有问题描述，缺少量化异常证据。"
        ]
        if placeholder_evidence
        else [
            "异常单体编号：3"
        ]
    )

    output = DiagnosisOutput(
        primary_cause="电芯电压一致性异常",
        alternative_causes=[
            "采样链路异常"
        ],
        risk_level=risk_level,
        verification_steps=[
            "复核异常单体电压数据。"
        ],
        immediate_action_required=(
            risk_level == RiskLevel.HIGH
        ),
        evidence=evidence,
        uncertainty_statement=(
            "该结果属于规则驱动的候选诊断，"
            "仍需结合原始数据和专业人员复核。"
        ),
    )

    return ToolCallingResult(
        status=ToolCallingStatus.SUCCESS,
        trace_id=trace_id,
        tool_name="diagnosis",
        output=output.model_dump(
            mode="json"
        ),
    )


def make_optimization_results(
    *,
    trace_id: str,
    dispatch_status: DispatchStatus,
) -> tuple[ToolCallingResult, ...]:
    """构造数字孪生、寻优和模拟下发结果。"""

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
            "使用简化模型进行预测。"
        ],
        rule_evidence=[
            "候选参数满足数字孪生安全约束。"
        ],
    )

    candidate = CandidateEvaluation(
        candidate_charging_current_a=18.0,
        cooling_power_w=0.0,
        score=0.90,
        prediction=prediction,
    )

    optimization = OptimizationOutput(
        status=OptimizationStatus.SUCCESS,
        recommended_candidate=candidate,
        alternative_candidates=[],
        evaluated_candidates=[candidate],
        evaluated_candidate_count=1,
        feasible_candidate_count=1,
        selection_reason=(
            "推荐方案满足全部约束且综合评分最高。"
        ),
    )

    requires_review = (
        dispatch_status
        == DispatchStatus.REQUIRES_REVIEW
    )

    dispatch = CloudDispatchOutput(
        status=dispatch_status,
        strategy=DispatchStrategy(
            strategy_id="STRATEGY-001",
            strategy_version="1.0.0",
            target_device_id="PACK-001",
            charging_current_a=18.0,
            cooling_power_w=0.0,
            valid_for_minutes=30,
            simulation_only=True,
        ),
        source_candidate=candidate,
        safety_checks_passed=True,
        requires_manual_review=requires_review,
        blocking_reasons=[],
        decision_evidence=[
            "推荐参数通过下发层独立安全检查。"
        ],
        rollback_recommendation=(
            "状态异常时停止采用该策略并恢复安全参数。"
        ),
        source_trace_id=trace_id,
    )

    return (
        ToolCallingResult(
            status=ToolCallingStatus.SUCCESS,
            trace_id=trace_id,
            tool_name="digital_twin",
            output=prediction.model_dump(
                mode="json"
            ),
        ),
        ToolCallingResult(
            status=ToolCallingStatus.SUCCESS,
            trace_id=trace_id,
            tool_name="parameter_optimization",
            output=optimization.model_dump(
                mode="json"
            ),
        ),
        ToolCallingResult(
            status=ToolCallingStatus.SUCCESS,
            trace_id=trace_id,
            tool_name="cloud_dispatch",
            output=dispatch.model_dump(
                mode="json"
            ),
        ),
    )


def build_review_report_fixture(
    scenario: ReviewReportScenario,
    *,
    trace_id: str,
) -> ReviewReportFixture:
    """根据场景名称构造联合评测输入。"""

    if (
        scenario
        == ReviewReportScenario
        .BATTERY_ANALYSIS_APPROVED
    ):
        return ReviewReportFixture(
            issue=make_issue(
                raw_text="分析电池单体压差异常",
                severity=Severity.LOW,
            ),
            plan=(
                make_step(
                    target="battery_analysis",
                    status=WorkflowStepStatus.SUCCESS,
                ),
            ),
            tool_results=(
                make_battery_result(
                    trace_id=trace_id
                ),
            ),
            rag_answers=(),
            errors=(),
            decision=WorkflowDecision.FINISH,
            device_id="PACK-001",
        )

    if (
        scenario
        == ReviewReportScenario
        .APPROVED_WITH_MISSING_INFORMATION
    ):
        return ReviewReportFixture(
            issue=make_issue(
                raw_text="分析电池压差并生成报告",
                severity=Severity.LOW,
                missing_information=[
                    "缺少历史趋势数据"
                ],
            ),
            plan=(
                make_step(
                    target="battery_analysis",
                    status=WorkflowStepStatus.SUCCESS,
                ),
            ),
            tool_results=(
                make_battery_result(
                    trace_id=trace_id
                ),
            ),
            rag_answers=(),
            errors=(),
            decision=WorkflowDecision.FINISH,
        )

    if (
        scenario
        == ReviewReportScenario
        .RAG_INSUFFICIENT_EVIDENCE
    ):
        return ReviewReportFixture(
            issue=make_issue(
                raw_text="电池异常原因是什么？"
            ),
            plan=(
                make_step(
                    target="rag_pipeline",
                    status=WorkflowStepStatus.SUCCESS,
                ),
            ),
            tool_results=(),
            rag_answers=(
                RAGAnswer(
                    question="电池异常原因是什么？",
                    answer="当前证据不足。",
                    citations=[],
                    confidence=0.0,
                    sufficient_evidence=False,
                    missing_information=[
                        "需要补充原始运行数据"
                    ],
                    needs_human_review=True,
                ),
            ),
            errors=(),
            decision=(
                WorkflowDecision.HUMAN_REVIEW
            ),
        )

    if (
        scenario
        == ReviewReportScenario
        .SKILL_EXECUTION_FAILED
    ):
        return ReviewReportFixture(
            issue=make_issue(
                raw_text="分析电池单体电压"
            ),
            plan=(
                make_step(
                    target="battery_analysis",
                    status=WorkflowStepStatus.FAILED,
                ),
            ),
            tool_results=(
                ToolCallingResult(
                    status=(
                        ToolCallingStatus
                        .SKILL_EXECUTION_FAILED
                    ),
                    trace_id=trace_id,
                    tool_name="battery_analysis",
                    error_code="skill_execution_error",
                    error_message="执行失败",
                    needs_human_review=True,
                ),
            ),
            rag_answers=(),
            errors=(),
            decision=(
                WorkflowDecision.HUMAN_REVIEW
            ),
        )

    if (
        scenario
        == ReviewReportScenario
        .CRITICAL_DIAGNOSIS
    ):
        return ReviewReportFixture(
            issue=make_issue(
                raw_text="电池发生严重高风险异常",
                severity=Severity.CRITICAL,
            ),
            plan=(
                make_step(
                    target="diagnosis",
                    status=WorkflowStepStatus.SUCCESS,
                ),
            ),
            tool_results=(
                make_diagnosis_result(
                    trace_id=trace_id,
                    placeholder_evidence=False,
                    risk_level=RiskLevel.HIGH,
                ),
            ),
            rag_answers=(),
            errors=(),
            decision=(
                WorkflowDecision.HUMAN_REVIEW
            ),
        )

    if (
        scenario
        == ReviewReportScenario
        .DIAGNOSIS_PLACEHOLDER_EVIDENCE
    ):
        return ReviewReportFixture(
            issue=make_issue(
                raw_text="分析当前电池异常"
            ),
            plan=(
                make_step(
                    target="diagnosis",
                    status=WorkflowStepStatus.SUCCESS,
                ),
            ),
            tool_results=(
                make_diagnosis_result(
                    trace_id=trace_id,
                    placeholder_evidence=True,
                    risk_level=RiskLevel.NORMAL,
                ),
            ),
            rag_answers=(),
            errors=(),
            decision=WorkflowDecision.FINISH,
        )

    if (
        scenario
        == ReviewReportScenario
        .OPTIMIZATION_READY
    ):
        results = make_optimization_results(
            trace_id=trace_id,
            dispatch_status=DispatchStatus.READY,
        )

        return ReviewReportFixture(
            issue=make_issue(
                raw_text="优化充电参数并生成模拟策略",
                severity=Severity.LOW,
            ),
            plan=tuple(
                make_step(
                    target=result.tool_name or "unknown",
                    status=WorkflowStepStatus.SUCCESS,
                    sequence=index,
                )
                for index, result in enumerate(
                    results
                )
            ),
            tool_results=results,
            rag_answers=(),
            errors=(),
            decision=WorkflowDecision.FINISH,
            device_id="PACK-001",
        )

    if (
        scenario
        == ReviewReportScenario
        .DISPATCH_REQUIRES_REVIEW
    ):
        results = make_optimization_results(
            trace_id=trace_id,
            dispatch_status=(
                DispatchStatus.REQUIRES_REVIEW
            ),
        )

        return ReviewReportFixture(
            issue=make_issue(
                raw_text="生成需要人工审核的模拟充电策略",
                severity=Severity.MEDIUM,
            ),
            plan=tuple(
                make_step(
                    target=result.tool_name or "unknown",
                    status=WorkflowStepStatus.SUCCESS,
                    sequence=index,
                )
                for index, result in enumerate(
                    results
                )
            ),
            tool_results=results,
            rag_answers=(),
            errors=(),
            decision=(
                WorkflowDecision.HUMAN_REVIEW
            ),
            device_id="PACK-001",
        )

    if (
        scenario
        == ReviewReportScenario
        .UNSUPPORTED_TOOL_OUTPUT
    ):
        return ReviewReportFixture(
            issue=make_issue(
                raw_text="处理未知工具输出"
            ),
            plan=(
                make_step(
                    target="unknown_analysis",
                    status=WorkflowStepStatus.SUCCESS,
                ),
            ),
            tool_results=(
                ToolCallingResult(
                    status=ToolCallingStatus.SUCCESS,
                    trace_id=trace_id,
                    tool_name="unknown_analysis",
                    output={
                        "result": "unknown"
                    },
                ),
            ),
            rag_answers=(),
            errors=(),
            decision=WorkflowDecision.FINISH,
        )

    raise ValueError(
        f"未知Review/Report评测场景：{scenario}"
    )