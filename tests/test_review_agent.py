"""Review Agent核心功能测试。覆盖：正常通过审核、诊断占位证据的正确分类、RAG证据不足的拦截、
Skill执行失败的拦截、诊断结论后选型的保留验证"""

from agent_core.review_agent import ReviewAgent
from agent_core.schemas import (
    PowerSystemIssue,
    Severity,
    Subsystem,
    TaskType,
)
from agent_core.state import (
    WorkflowDecision,
    WorkflowStep,
    WorkflowStepStatus,
)
from agent_core.tool_models import (
    ToolCallingResult,
    ToolCallingStatus,
)
from agent_core.workflow_models import (
    ReviewStatus,
)
from rag.schemas import (
    RAGAnswer,
    RAGCitation,
)
from skills.battery_analysis_skill import (
    BatteryAnalysisOutput,
)
from skills.diagnosis_skill import DiagnosisOutput
from skills.schemas import RiskLevel
from skills.cloud_dispatch_skill import (
    CloudDispatchOutput,
    DispatchStatus,
    DispatchStrategy,
)
from skills.digital_twin_skill import (
    DigitalTwinOutput,
)
from skills.optimization_skill import (
    CandidateEvaluation,
    OptimizationOutput,
    OptimizationStatus,
)


def make_issue(
    *,
    severity: Severity = Severity.MEDIUM,
) -> PowerSystemIssue:
    """构造Review测试问题。"""

    return PowerSystemIssue(
        raw_text="分析电池单体压差异常",
        subsystem=Subsystem.BATTERY,
        task_type=TaskType.FAULT_DIAGNOSIS,
        symptoms=["单体压差增大"],
        operating_conditions=[],
        user_hypotheses=[],
        requested_outputs=["异常原因"],
        missing_information=[],
        severity=severity,
        confidence=0.95,
    )


def make_step(
    *,
    target: str,
    status: WorkflowStepStatus,
    sequence: int = 0,
) -> WorkflowStep:
    """构造计划步骤。"""

    return WorkflowStep(
        step_id=f"step_{sequence}",
        sequence=sequence,
        action=f"执行{target}",
        target=target,
        input_keys=["issue"],
        output_key="tool_results",
        status=status,
    )


"""
五个测试用例详解
"""
# 正常场景：有效分析结果+充分RAG证据->完全通过
def test_review_valid_analysis_and_rag() -> None:
    """有效分析结果和RAG证据应通过审核。"""

    battery_output = BatteryAnalysisOutput(
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

    tool_result = ToolCallingResult(
        status=ToolCallingStatus.SUCCESS,
        trace_id="trace_review_001",
        tool_name="battery_analysis",
        output=battery_output.model_dump(
            mode="json"
        ),
    )

    rag_answer = RAGAnswer(
        question="单体压差增大可能说明什么？",
        answer=(
            "单体压差增大可作为一致性异常"
            "或状态差异的候选信号。"
        ),
        citations=[
            RAGCitation(
                chunk_id="battery_chunk_1",
                document_id="battery_doc",
                title="电池一致性诊断",
                section_path="电压一致性",
                page_number=None,
                supported_claim=(
                    "压差增大是状态差异候选信号"
                ),
                evidence_text=(
                    "单体压差增大可能反映"
                    "单体状态差异。"
                ),
            )
        ],
        confidence=0.9,
        sufficient_evidence=True,
        missing_information=[],
        needs_human_review=False,
    )

    result = ReviewAgent().review(
        issue=make_issue(),
        plan=[
            make_step(
                target="battery_analysis",
                status=WorkflowStepStatus.SUCCESS,
            )
        ],
        tool_results=[tool_result],
        rag_answers=[rag_answer],
        errors=[],
        decision=WorkflowDecision.FINISH,
    )

    assert result.approved_for_report is True
    assert result.status == ReviewStatus.APPROVED
    assert result.risk_level == RiskLevel.MEDIUM
    assert result.findings
    assert result.recommendations
    assert any(
        "battery_chunk_1" in item
        for item in result.evidence
    )


# 诊断占位证据应归入unresolved_items，而非evidence
def test_review_moves_placeholder_evidence_to_unresolved(
) -> None:
    """诊断占位说明不能作为最终报告证据。"""

    diagnosis_output = DiagnosisOutput(
        primary_cause="暂未发现明确异常",
        alternative_causes=[],
        risk_level=RiskLevel.NORMAL,
        verification_steps=[
            "复核原始测量数据。"
        ],
        immediate_action_required=False,
        evidence=[
            "当前仅有问题描述，缺少量化异常证据。"
        ],
        uncertainty_statement=(
            "该结果属于规则驱动的候选诊断，"
            "仍需结合原始数据和专业人员复核。"
        ),
    )

    result = ReviewAgent().review(
        issue=make_issue(),
        plan=[
            make_step(
                target="diagnosis",
                status=WorkflowStepStatus.SUCCESS,
            )
        ],
        tool_results=[
            ToolCallingResult(
                status=ToolCallingStatus.SUCCESS,
                trace_id="trace_review_002",
                tool_name="diagnosis",
                output=(
                    diagnosis_output.model_dump(
                        mode="json"
                    )
                ),
            )
        ],
        rag_answers=[],
        errors=[],
        decision=WorkflowDecision.FINISH,
    )

    placeholder = (
        "当前仅有问题描述，缺少量化异常证据。"
    )

    assert placeholder not in result.evidence
    assert placeholder in result.unresolved_items

# RAG证据不足->不批准报告
def test_review_insufficient_rag_evidence(
) -> None:
    """只有证据不足的RAG结果时不得批准报告。"""

    result = ReviewAgent().review(
        issue=make_issue(),
        plan=[
            make_step(
                target="rag_pipeline",
                status=WorkflowStepStatus.SUCCESS,
            )
        ],
        tool_results=[],
        rag_answers=[
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
            )
        ],
        errors=[],
        decision=(
            WorkflowDecision.HUMAN_REVIEW
        ),
    )

    assert result.approved_for_report is False
    assert (
        result.status
        == ReviewStatus.INSUFFICIENT_EVIDENCE
    )
    assert result.needs_human_review is True

# Skill执行失败->判定为执行失败
def test_review_skill_failure_blocks_report(
) -> None:
    """没有任何有效结果且Skill失败时应阻断报告。"""

    result = ReviewAgent().review(
        issue=make_issue(),
        plan=[
            make_step(
                target="battery_analysis",
                status=WorkflowStepStatus.FAILED,
            )
        ],
        tool_results=[
            ToolCallingResult(
                status=(
                    ToolCallingStatus
                    .SKILL_EXECUTION_FAILED
                ),
                trace_id="trace_review_004",
                tool_name="battery_analysis",
                error_code="skill_execution_error",
                error_message="执行失败",
                needs_human_review=True,
            )
        ],
        rag_answers=[],
        errors=[],
        decision=(
            WorkflowDecision.HUMAN_REVIEW
        ),
    )

    assert result.approved_for_report is False
    assert (
        result.status
        == ReviewStatus.EXECUTION_FAILED
    )

# 诊断结论保持候选性质，不得被篡改为确定结论
def test_review_keeps_diagnosis_as_candidate(
) -> None:
    """Diagnosis输出不得被改写为确定故障结论。"""

    diagnosis_output = DiagnosisOutput(
        primary_cause="电芯电压一致性异常",
        alternative_causes=[
            "采样链路异常"
        ],
        risk_level=RiskLevel.MEDIUM,
        verification_steps=[
            "复核异常单体电压数据。"
        ],
        immediate_action_required=False,
        evidence=[
            "异常单体编号：3"
        ],
        uncertainty_statement=(
            "该结果属于规则驱动的候选诊断，"
            "仍需结合原始数据和专业人员复核。"
        ),
    )

    result = ReviewAgent().review(
        issue=make_issue(),
        plan=[
            make_step(
                target="diagnosis",
                status=WorkflowStepStatus.SUCCESS,
            )
        ],
        tool_results=[
            ToolCallingResult(
                status=ToolCallingStatus.SUCCESS,
                trace_id="trace_review_005",
                tool_name="diagnosis",
                output=(
                    diagnosis_output.model_dump(
                        mode="json"
                    )
                ),
            )
        ],
        rag_answers=[],
        errors=[],
        decision=WorkflowDecision.FINISH,
    )

    assert any(
        item.startswith("候选主要原因")
        for item in result.findings
    )

    assert not any(
        "已确认" in item
        for item in result.findings
    )

def test_review_accepts_optimization_workflow_outputs(
) -> None:
    """数字孪生、参数寻优和模拟下发结果应被统一审核。"""

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

    optimization_output = OptimizationOutput(
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

    dispatch_output = CloudDispatchOutput(
        status=DispatchStatus.READY,
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
        requires_manual_review=False,
        blocking_reasons=[],
        decision_evidence=[
            "推荐参数通过下发层独立安全检查。"
        ],
        rollback_recommendation=(
            "状态异常时停止采用该策略并恢复安全参数。"
        ),
        source_trace_id="trace_review_optimization",
    )

    tool_results = [
        ToolCallingResult(
            status=ToolCallingStatus.SUCCESS,
            trace_id="trace_review_optimization",
            tool_name="digital_twin",
            output=prediction.model_dump(
                mode="json"
            ),
        ),
        ToolCallingResult(
            status=ToolCallingStatus.SUCCESS,
            trace_id="trace_review_optimization",
            tool_name="parameter_optimization",
            output=optimization_output.model_dump(
                mode="json"
            ),
        ),
        ToolCallingResult(
            status=ToolCallingStatus.SUCCESS,
            trace_id="trace_review_optimization",
            tool_name="cloud_dispatch",
            output=dispatch_output.model_dump(
                mode="json"
            ),
        ),
    ]

    result = ReviewAgent().review(
        issue=make_issue(
            severity=Severity.LOW
        ),
        plan=[
            make_step(
                target="digital_twin",
                status=WorkflowStepStatus.SUCCESS,
                sequence=0,
            ),
            make_step(
                target="parameter_optimization",
                status=WorkflowStepStatus.SUCCESS,
                sequence=1,
            ),
            make_step(
                target="cloud_dispatch",
                status=WorkflowStepStatus.SUCCESS,
                sequence=2,
            ),
        ],
        tool_results=tool_results,
        rag_answers=[],
        errors=[],
        decision=WorkflowDecision.FINISH,
    )

    assert result.approved_for_report is True

    assert (
        result.status
        == ReviewStatus.APPROVED_WITH_WARNINGS
    )

    assert result.needs_human_review is False

    assert any(
        "推荐充电电流" in item
        for item in result.findings
    )

    assert any(
        "模拟云端策略状态" in item
        for item in result.findings
    )

    assert any(
        "simulation_only=True" in item
        for item in result.evidence
    )

    assert not any(
        "暂不支持审核工具" in item
        for item in result.unresolved_items
    )