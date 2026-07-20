"""PowerAgent工作流结果审核与归一化。
职责是把工作流跑完之后积累下来的所有原始、零散的执行痕迹统一审核一遍，
转换成结构化、去重、可信、可直接用于生成最终报告的ReviewResult。
整体分为 类级配置、review()主流程（六步审核）、各类型工具输出的专属提取方法、若干工具函数。"""

from __future__ import annotations

import logging
from typing import Any

from pydantic import BaseModel, ValidationError

from agent_core.logging_config import get_logger
from agent_core.schemas import (
    PowerSystemIssue,
    Severity,
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
from agent_core.workflow_models import (
    ReviewResult,
    ReviewStatus,
)
from rag.schemas import RAGAnswer
from skills.battery_analysis_skill import (
    BatteryAnalysisOutput,
)
from skills.charging_analysis_skill import (
    ChargingAnalysisOutput,
)
from skills.diagnosis_skill import DiagnosisOutput
from skills.schemas import (
    RecommendedAction,
    RiskLevel,
)
from skills.thermal_analysis_skill import (
    ThermalAnalysisOutput,
)
from skills.cloud_dispatch_skill import (
    CloudDispatchOutput,
    DispatchStatus,
)
from skills.digital_twin_skill import (
    DigitalTwinOutput,
)
from skills.optimization_skill import (
    OptimizationOutput,
    OptimizationStatus,
)


class ReviewAgent:
    """审核工作流结果并形成可信报告输入。"""

    # 一、类型配置
    _RISK_ORDER = {
        RiskLevel.NORMAL: 0,
        RiskLevel.LOW: 1,
        RiskLevel.MEDIUM: 2,
        RiskLevel.HIGH: 3,
    }

    _TOOL_OUTPUT_MODELS: dict[
        str,
        type[BaseModel],
    ] = {
        "battery_analysis": BatteryAnalysisOutput,
        "thermal_analysis": ThermalAnalysisOutput,
        "charging_analysis": ChargingAnalysisOutput,
        "digital_twin": DigitalTwinOutput,
        "parameter_optimization": OptimizationOutput,
        "cloud_dispatch": CloudDispatchOutput,
        "diagnosis": DiagnosisOutput,
    }

    _DIAGNOSIS_PLACEHOLDER_EVIDENCE = (
        "当前仅有问题描述，缺少量化异常证据。"
    )

    def __init__(
        self,
        *,
        logger: logging.Logger | None = None,
    ) -> None:
        self._logger = logger or get_logger(
            "review_agent"
        )

    def review(
        self,
        *,
        issue: PowerSystemIssue,
        plan: list[WorkflowStep],
        tool_results: list[ToolCallingResult],
        rag_answers: list[RAGAnswer],
        errors: list[WorkflowError],
        decision: WorkflowDecision | None,
        trace_id: str | None = None,
    ) -> ReviewResult:
        """审核工作流执行结果并生成报告级可信数据。"""

        self._logger.info(
            "开始审核工作流结果。",
            extra={
                "event": "workflow_review_started",
                "trace_id": trace_id,
                "tool_result_count": len(
                    tool_results
                ),
                "rag_answer_count": len(
                    rag_answers
                ),
                "error_count": len(errors),
                "decision": (
                    decision.value
                    if decision is not None
                    else None
                ),
            },
        )

        # 二、六步审核主流程
        # 初始化五个累积容器
        findings: list[str] = []
        recommendations: list[str] = []
        evidence: list[str] = []
        unresolved_items: list[str] = list(
            issue.missing_information
        )
        review_issues: list[str] = []

        risk_level = self._severity_to_risk(
            issue.severity
        )

        needs_human_review = (
            issue.severity == Severity.CRITICAL
        )

        execution_failed = False

        # 1. 审核计划步骤状态。
        for step in plan:
            if step.status == WorkflowStepStatus.FAILED:
                execution_failed = True
                review_issues.append(
                    f"计划步骤{step.step_id}执行失败："
                    f"{step.action}"
                )

            elif step.status in {
                WorkflowStepStatus.PENDING,
                WorkflowStepStatus.RUNNING,
            }:
                review_issues.append(
                    f"计划步骤{step.step_id}尚未完成："
                    f"{step.action}"
                )

            elif step.status == WorkflowStepStatus.SKIPPED:
                unresolved_items.append(
                    f"计划步骤{step.step_id}未执行："
                    f"{step.action}"
                )

        # 2. 审核统一工作流错误。
        for error in errors:
            execution_failed = True
            needs_human_review = True

            review_issues.append(
                f"{error.node.value}节点错误"
                f"[{error.error_code}]："
                f"{error.message}"
            )

        # 3. 审核Tool Calling结果。
        for result in tool_results:
            if result.status != ToolCallingStatus.SUCCESS:
                execution_failed = True
                needs_human_review = (
                    needs_human_review
                    or result.needs_human_review
                )

                review_issues.append(
                    self._format_tool_failure(result)
                )
                continue

            if result.tool_name is None:
                execution_failed = True
                review_issues.append(
                    "成功的Tool Calling结果缺少tool_name。"
                )
                continue

            output_model = self._TOOL_OUTPUT_MODELS.get(
                result.tool_name
            )

            if output_model is None:
                unresolved_items.append(
                    "Review Agent暂不支持审核工具"
                    f"{result.tool_name}的输出。"
                )
                continue

            if result.output is None:
                execution_failed = True
                review_issues.append(
                    f"工具{result.tool_name}执行成功，"
                    "但没有返回结构化输出。"
                )
                continue

            try:
                validated_output = (
                    output_model.model_validate(
                        result.output
                    )
                )
            except ValidationError as exc:
                execution_failed = True
                needs_human_review = True

                review_issues.append(
                    f"工具{result.tool_name}输出"
                    "未通过Review阶段二次校验；"
                    f"错误数量：{exc.error_count()}。"
                )
                continue
            # 通过所有检查后，提取工具输出的实质内容
            output_risk = self._extract_tool_output(
                tool_name=result.tool_name,
                output=validated_output,
                findings=findings,
                recommendations=recommendations,
                evidence=evidence,
                unresolved_items=unresolved_items,
            )

            risk_level = self._max_risk(
                risk_level,
                output_risk,
            )

            if (
                result.needs_human_review
                or self._output_requires_review(
                    result.tool_name,
                    validated_output,
                )
            ):
                needs_human_review = True

        # 4. 审核RAG结果。
        for rag_answer in rag_answers:
            unresolved_items.extend(
                rag_answer.missing_information
            )

            needs_human_review = (
                needs_human_review
                or rag_answer.needs_human_review
            )

            if not rag_answer.sufficient_evidence:
                review_issues.append(
                    "知识库证据不足，RAG回答不能作为"
                    "可靠诊断结论。"
                )
                continue

            findings.append(
                "知识证据结论："
                f"{rag_answer.answer}"
            )

            for citation in rag_answer.citations:
                section_text = (
                    f" / {citation.section_path}"
                    if citation.section_path
                    else ""
                )

                page_text = (
                    f" / 第{citation.page_number}页"
                    if citation.page_number is not None
                    else ""
                )

                evidence.append(
                    "知识库证据"
                    f"[{citation.chunk_id}] "
                    f"{citation.title}"
                    f"{section_text}"
                    f"{page_text}："
                    f"{citation.evidence_text}"
                )

        # 5. 审核Decision Agent结论。
        if decision in {
            WorkflowDecision.HUMAN_REVIEW,
            WorkflowDecision.ABORT,
        }:
            needs_human_review = True

        if decision == WorkflowDecision.ABORT:
            execution_failed = True
            review_issues.append(
                "工作流因状态异常被终止。"
            )

        if decision in {
            WorkflowDecision.RETRY,
            WorkflowDecision.REPLAN,
        }:
            review_issues.append(
                "工作流仍处于重试或重新规划状态，"
                "尚未形成最终执行结论。"
            )

        # 6. 去重并提供最低限度的可靠建议。
        findings = self._deduplicate(findings)
        recommendations = self._deduplicate(
            recommendations
        )
        evidence = self._deduplicate(evidence)
        unresolved_items = self._deduplicate(
            unresolved_items
        )
        review_issues = self._deduplicate(
            review_issues
        )

        if findings and not recommendations:
            recommendations.append(
                "继续核验原始测量数据，"
                "并在采取控制或维修措施前"
                "由动力系统专业人员复核。"
            )

        approved_for_report = bool(
            findings and recommendations
        )

        # 最终状态判定
        if not approved_for_report:
            needs_human_review = True

            if execution_failed:
                status = ReviewStatus.EXECUTION_FAILED
            else:
                status = (
                    ReviewStatus.INSUFFICIENT_EVIDENCE
                )

        elif needs_human_review:
            status = (
                ReviewStatus.HUMAN_REVIEW_REQUIRED
            )

        elif review_issues or unresolved_items:
            status = (
                ReviewStatus.APPROVED_WITH_WARNINGS
            )

        else:
            status = ReviewStatus.APPROVED

        result = ReviewResult(
            status=status,
            approved_for_report=approved_for_report,
            findings=findings,
            recommendations=recommendations,
            evidence=evidence,
            unresolved_items=unresolved_items,
            risk_level=risk_level,
            issue_severity=issue.severity,
            review_issues=review_issues,
            needs_human_review=needs_human_review,
        )

        self._logger.info(
            "工作流结果审核完成。",
            extra={
                "event": "workflow_review_completed",
                "trace_id": trace_id,
                "review_status": result.status.value,
                "approved_for_report": (
                    result.approved_for_report
                ),
                "finding_count": len(result.findings),
                "evidence_count": len(result.evidence),
                "unresolved_count": len(
                    result.unresolved_items
                ),
                "risk_level": (
                    result.risk_level.value
                ),
                "needs_human_review": (
                    result.needs_human_review
                ),
            },
        )

        return result

    # 工具输出的分发提取
    def _extract_tool_output(
        self,
        *,
        tool_name: str,
        output: BaseModel,
        findings: list[str],
        recommendations: list[str],
        evidence: list[str],
        unresolved_items: list[str],
    ) -> RiskLevel:
        """将不同Skill输出转换为统一审核字段。"""

        if (
            tool_name == "battery_analysis"
            and isinstance(
                output,
                BatteryAnalysisOutput,
            )
        ):
            return self._extract_battery_output(
                output,
                findings,
                recommendations,
                evidence,
            )

        if (
            tool_name == "thermal_analysis"
            and isinstance(
                output,
                ThermalAnalysisOutput,
            )
        ):
            return self._extract_thermal_output(
                output,
                findings,
                recommendations,
                evidence,
            )

        if (
            tool_name == "charging_analysis"
            and isinstance(
                output,
                ChargingAnalysisOutput,
            )
        ):
            return self._extract_charging_output(
                output,
                findings,
                recommendations,
                evidence,
            )
        
        if (
            tool_name == "digital_twin"
            and isinstance(
                output,
                DigitalTwinOutput,
            )
        ):
            return self._extract_digital_twin_output(
                output,
                findings,
                recommendations,
                evidence,
                unresolved_items,
            )

        if (
            tool_name == "parameter_optimization"
            and isinstance(
                output,
                OptimizationOutput,
            )
        ):
            return self._extract_optimization_output(
                output,
                findings,
                recommendations,
                evidence,
                unresolved_items,
            )

        if (
            tool_name == "cloud_dispatch"
            and isinstance(
                output,
                CloudDispatchOutput,
            )
        ):
            return self._extract_cloud_dispatch_output(
                output,
                findings,
                recommendations,
                evidence,
                unresolved_items,
            )

        if (
            tool_name == "diagnosis"
            and isinstance(
                output,
                DiagnosisOutput,
            )
        ):
            return self._extract_diagnosis_output(
                output,
                findings,
                recommendations,
                evidence,
                unresolved_items,
            )

        return RiskLevel.NORMAL

    # 把Skill输出翻译成通用审核语言
    @staticmethod
    def _extract_battery_output(
        output: BatteryAnalysisOutput,
        findings: list[str],
        recommendations: list[str],
        evidence: list[str],
    ) -> RiskLevel:
        """提取电池分析结果。"""

        findings.append(
            "单体最低电压为"
            f"{output.minimum_voltage_v:.3f} V"
            f"（第{output.minimum_cell_number}号），"
            "最高电压为"
            f"{output.maximum_voltage_v:.3f} V"
            f"（第{output.maximum_cell_number}号），"
            "最大压差为"
            f"{output.voltage_spread_v:.3f} V。"
        )

        if output.out_of_range_cell_numbers:
            cells = ", ".join(
                str(item)
                for item
                in output.out_of_range_cell_numbers
            )

            findings.append(
                f"检测到电压越界单体：{cells}。"
            )

        if output.consistency_risk:
            findings.append(
                "单体电压一致性存在规则风险。"
            )

        evidence.extend(output.rule_evidence)

        if (
            output.out_of_range_cell_numbers
            or output.consistency_risk
        ):
            recommendations.append(
                "复核异常单体电压采样链路，"
                "并结合历史趋势开展静置复测。"
            )
        else:
            recommendations.append(
                "继续监测单体电压范围和压差变化。"
            )

        return output.risk_level

    @staticmethod
    def _extract_thermal_output(
        output: ThermalAnalysisOutput,
        findings: list[str],
        recommendations: list[str],
        evidence: list[str],
    ) -> RiskLevel:
        """提取热状态分析结果。"""

        findings.append(
            "最低温度为"
            f"{output.minimum_temperature_c:.2f} ℃，"
            "最高温度为"
            f"{output.maximum_temperature_c:.2f} ℃"
            f"（第{output.hottest_sensor_number}号测点），"
            "最大温差为"
            f"{output.temperature_spread_c:.2f} ℃。"
        )

        if output.overtemperature_sensor_numbers:
            sensors = ", ".join(
                str(item)
                for item
                in output.overtemperature_sensor_numbers
            )

            findings.append(
                f"检测到超温测点：{sensors}。"
            )

        if output.temperature_inconsistency_risk:
            findings.append(
                "温度一致性存在规则风险。"
            )

        evidence.extend(output.rule_evidence)

        if (
            output.overtemperature_sensor_numbers
            or output.temperature_inconsistency_risk
        ):
            recommendations.append(
                "复核异常温度测点、冷却回路"
                "及相邻测点变化趋势。"
            )
        else:
            recommendations.append(
                "继续监测最高温度和温差变化。"
            )

        return output.risk_level

    @staticmethod
    def _extract_charging_output(
        output: ChargingAnalysisOutput,
        findings: list[str],
        recommendations: list[str],
        evidence: list[str],
    ) -> RiskLevel:
        """提取充电分析结果。"""

        if output.violated_constraints:
            findings.append(
                "充电过程触发约束："
                + ", ".join(
                    output.violated_constraints
                )
                + "。"
            )
        else:
            findings.append(
                "当前充电参数未触发设定约束。"
            )

        evidence.extend(output.rule_evidence)

        action_text = {
            RecommendedAction.CONTINUE_CHARGING: (
                "可以在持续监测条件下继续充电。"
            ),
            RecommendedAction.REDUCE_POWER: (
                "建议降低充电功率并复核约束参数。"
            ),
            RecommendedAction.STOP_CHARGING: (
                "建议停止充电并立即开展安全复核。"
            ),
        }

        recommendations.append(
            action_text[output.recommended_action]
        )

        return output.risk_level
    
    @staticmethod
    def _extract_digital_twin_output(
        output: DigitalTwinOutput,
        findings: list[str],
        recommendations: list[str],
        evidence: list[str],
        unresolved_items: list[str],
    ) -> RiskLevel:
        """提取数字孪生预测结果和模型边界。"""

        findings.append(
            "数字孪生预测SOC为"
            f"{output.predicted_soc_pct:.2f}%，"
            "预测电池组电压为"
            f"{output.predicted_pack_voltage_v:.2f} V，"
            "预测最高温度为"
            f"{output.predicted_maximum_temperature_c:.2f} ℃。"
        )

        findings.append(
            "预测电压安全裕度为"
            f"{output.voltage_margin_v:.2f} V，"
            "温度安全裕度为"
            f"{output.temperature_margin_c:.2f} ℃。"
        )

        if output.is_feasible:
            findings.append(
                "候选参数在当前简化数字孪生模型和"
                "安全边界下可行。"
            )

            recommendations.append(
                "在实际应用前结合高保真模型、"
                "历史数据或台架试验复核预测结果。"
            )

        else:
            findings.append(
                "候选参数未通过数字孪生安全检查，"
                "触发约束："
                + "、".join(
                    output.violated_constraints
                )
                + "。"
            )

            recommendations.append(
                "调整候选充电电流、冷却功率或"
                "预测时间后重新执行数字孪生预测。"
            )

        evidence.extend(
            output.rule_evidence
        )

        unresolved_items.append(
            "数字孪生结果基于简化模型假设，"
            "尚未经过真实设备或高保真模型校准。"
        )

        return output.risk_level
    
    @staticmethod
    def _extract_optimization_output(
        output: OptimizationOutput,
        findings: list[str],
        recommendations: list[str],
        evidence: list[str],
        unresolved_items: list[str],
    ) -> RiskLevel:
        """提取参数寻优结果和推荐候选。"""

        findings.append(
            "参数寻优共评估"
            f"{output.evaluated_candidate_count}"
            "个候选方案，其中"
            f"{output.feasible_candidate_count}"
            "个满足安全约束。"
        )

        evidence.append(
            "参数寻优选择依据："
            f"{output.selection_reason}"
        )

        if (
            output.status
            == OptimizationStatus.NO_FEASIBLE_SOLUTION
        ):
            findings.append(
                "当前候选搜索空间内未找到"
                "满足全部安全约束的方案。"
            )

            recommendations.append(
                "调整候选电流、冷却能力、预测时长"
                "或约束边界后重新执行参数寻优。"
            )

            unresolved_items.append(
                "当前参数搜索空间不存在可下发的"
                "安全推荐方案。"
            )

            return RiskLevel.MEDIUM

        recommended = output.recommended_candidate

        if recommended is None:
            unresolved_items.append(
                "参数寻优成功状态缺少推荐候选方案。"
            )

            return RiskLevel.MEDIUM

        findings.append(
            "推荐充电电流为"
            f"{recommended.candidate_charging_current_a:.2f} A，"
            "推荐等效冷却功率为"
            f"{recommended.cooling_power_w:.2f} W，"
            "综合评分为"
            f"{recommended.score:.4f}。"
        )

        findings.append(
            "推荐方案预测SOC为"
            f"{recommended.prediction.predicted_soc_pct:.2f}%，"
            "预测电压为"
            f"{recommended.prediction.predicted_pack_voltage_v:.2f} V，"
            "预测最高温度为"
            f"{recommended.prediction.predicted_maximum_temperature_c:.2f} ℃。"
        )

        evidence.extend(
            (
                "推荐方案依据："
                f"{item}"
                for item in (
                    recommended.prediction.rule_evidence
                )
            )
        )

        recommendations.append(
            "在策略下发前复核推荐方案的安全裕度、"
            "设备权限和模型适用边界。"
        )

        return recommended.prediction.risk_level
    

    @staticmethod
    def _extract_cloud_dispatch_output(
        output: CloudDispatchOutput,
        findings: list[str],
        recommendations: list[str],
        evidence: list[str],
        unresolved_items: list[str],
    ) -> RiskLevel:
        """提取模拟云端策略及审批状态。"""

        findings.append(
            "模拟云端策略状态为"
            f"{output.status.value}。"
        )

        if output.strategy is not None:
            findings.append(
                "模拟策略建议充电电流为"
                f"{output.strategy.charging_current_a:.2f} A，"
                "建议等效冷却功率为"
                f"{output.strategy.cooling_power_w:.2f} W，"
                "有效时间为"
                f"{output.strategy.valid_for_minutes}分钟。"
            )

            evidence.append(
                "模拟策略标识："
                f"{output.strategy.strategy_id}，"
                "版本："
                f"{output.strategy.strategy_version}，"
                "目标设备："
                f"{output.strategy.target_device_id}。"
            )

            evidence.append(
                "该策略simulation_only="
                f"{output.strategy.simulation_only}，"
                "不代表真实设备控制命令。"
            )

        evidence.extend(
            output.decision_evidence
        )

        evidence.append(
            "下发工作流追踪标识："
            f"{output.source_trace_id}。"
        )

        recommendations.append(
            output.rollback_recommendation
        )

        if output.blocking_reasons:
            unresolved_items.append(
                "模拟策略被阻断，原因："
                + "、".join(
                    output.blocking_reasons
                )
                + "。"
            )

        if output.requires_manual_review:
            unresolved_items.append(
                "当前模拟策略必须经过动力系统"
                "专业人员复核后才能继续处理。"
            )

        risk_mapping = {
            DispatchStatus.READY: RiskLevel.NORMAL,
            DispatchStatus.DRAFT: RiskLevel.NORMAL,
            DispatchStatus.REQUIRES_REVIEW: (
                RiskLevel.MEDIUM
            ),
            DispatchStatus.BLOCKED: RiskLevel.HIGH,
        }

        return risk_mapping[output.status]


    def _extract_diagnosis_output(
        self,
        output: DiagnosisOutput,
        findings: list[str],
        recommendations: list[str],
        evidence: list[str],
        unresolved_items: list[str],
    ) -> RiskLevel:
        """提取候选诊断并保留不确定性边界。"""

        findings.append(
            "候选主要原因："
            f"{output.primary_cause}。"
        )

        if output.alternative_causes:
            findings.append(
                "其他候选原因："
                + "、".join(
                    output.alternative_causes
                )
                + "。"
            )

        recommendations.extend(
            output.verification_steps
        )

        if output.immediate_action_required:
            recommendations.append(
                "立即采取安全处置措施，"
                "并由动力系统专业人员复核。"
            )

        for item in output.evidence:
            if (
                item
                == self
                ._DIAGNOSIS_PLACEHOLDER_EVIDENCE
            ):
                unresolved_items.append(item)
            else:
                evidence.append(item)

        unresolved_items.append(
            output.uncertainty_statement
        )

        return output.risk_level

    @staticmethod
    def _output_requires_review(
        tool_name: str,
        output: BaseModel,
    ) -> bool:
        """判断Skill结果是否需要强制专业复核。"""

        if (
            tool_name == "diagnosis"
            and isinstance(output, DiagnosisOutput)
        ):
            return (
                output.immediate_action_required
                or output.risk_level
                in {
                    RiskLevel.MEDIUM,
                    RiskLevel.HIGH,
                }
            )

        if (
            tool_name == "digital_twin"
            and isinstance(output, DigitalTwinOutput)
        ):
            return (
                not output.is_feasible
                or output.risk_level
                in {
                    RiskLevel.MEDIUM,
                    RiskLevel.HIGH,
                }
            )

        if (
            tool_name == "parameter_optimization"
            and isinstance(output, OptimizationOutput)
        ):
            return (
                output.status
                == OptimizationStatus.NO_FEASIBLE_SOLUTION
            )

        if (
            tool_name == "cloud_dispatch"
            and isinstance(output, CloudDispatchOutput)
        ):
            return output.requires_manual_review

        if hasattr(output, "risk_level"):
            risk_level = getattr(
                output,
                "risk_level",
            )

            return risk_level == RiskLevel.HIGH

        return False

    @staticmethod
    def _format_tool_failure(
        result: ToolCallingResult,
    ) -> str:
        """生成不暴露内部细节的工具失败说明。"""

        tool_text = (
            result.tool_name
            or "unknown_tool"
        )

        error_text = (
            result.error_code
            or result.status.value
        )

        return (
            f"工具{tool_text}执行未成功："
            f"{error_text}。"
        )

    @classmethod
    def _max_risk(
        cls,
        first: RiskLevel,
        second: RiskLevel,
    ) -> RiskLevel:
        """返回两个风险等级中较高者。"""

        if (
            cls._RISK_ORDER[second]
            > cls._RISK_ORDER[first]
        ):
            return second

        return first

    @staticmethod
    def _severity_to_risk(
        severity: Severity,
    ) -> RiskLevel:
        """将Issue严重程度映射到Skill风险等级。"""

        mapping = {
            Severity.CRITICAL: RiskLevel.HIGH,
            Severity.HIGH: RiskLevel.HIGH,
            Severity.MEDIUM: RiskLevel.MEDIUM,
            Severity.LOW: RiskLevel.LOW,
            Severity.UNKNOWN: RiskLevel.NORMAL,
        }

        return mapping[severity]

    @staticmethod
    def _deduplicate(
        items: list[str],
    ) -> list[str]:
        """在保持原顺序的前提下去重。"""

        return list(dict.fromkeys(items))