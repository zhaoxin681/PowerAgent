"""PowerAgent统一评测看板配置。"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]

RESULTS_DIR = (
    PROJECT_ROOT
    / "evaluation"
    / "results"
)


@dataclass(frozen=True)
class MetricWeight:
    """参与模块评分的单项指标及其权重。"""

    name: str
    weight: float


@dataclass(frozen=True)
class ModuleBenchmarkConfig:
    """单个评测模块的评分配置。"""

    label: str

    summary_file: Path

    overall_weight: float

    metrics: tuple[MetricWeight, ...]


@dataclass(frozen=True)
class GateRule:
    """统一验收门槛。"""

    gate_id: str

    level: str

    module: str

    metric: str

    operator: str

    threshold: float

    description: str


MODULE_CONFIGS: dict[
    str,
    ModuleBenchmarkConfig,
] = {
    "issue_parser": ModuleBenchmarkConfig(
        label="Issue Parser",
        summary_file=(
            RESULTS_DIR
            / "parser_eval_summary.json"
        ),
        overall_weight=0.20,
        metrics=(
            MetricWeight(
                "call_success_rate",
                0.10,
            ),
            MetricWeight(
                "subsystem_accuracy",
                0.20,
            ),
            MetricWeight(
                "task_type_accuracy",
                0.20,
            ),
            MetricWeight(
                "severity_accuracy",
                0.15,
            ),
            MetricWeight(
                "concept_coverage",
                0.20,
            ),
            MetricWeight(
                "overall_case_pass_rate",
                0.15,
            ),
        ),
    ),
    "router": ModuleBenchmarkConfig(
        label="Router Agent",
        summary_file=(
            RESULTS_DIR
            / "router_eval_summary.json"
        ),
        overall_weight=0.15,
        metrics=(
            MetricWeight(
                "route_accuracy",
                0.25,
            ),
            MetricWeight(
                "status_accuracy",
                0.20,
            ),
            MetricWeight(
                "human_review_accuracy",
                0.20,
            ),
            MetricWeight(
                "missing_information_accuracy",
                0.10,
            ),
            MetricWeight(
                "critical_human_review_recall",
                0.10,
            ),
            MetricWeight(
                "overall_case_pass_rate",
                0.15,
            ),
        ),
    ),
    "skill_call": ModuleBenchmarkConfig(
        label="Skill Calling",
        summary_file=(
            RESULTS_DIR
            / "skill_eval_summary.json"
        ),
        overall_weight=0.20,
        metrics=(
            MetricWeight(
                "status_accuracy",
                0.15,
            ),
            MetricWeight(
                "skill_accuracy",
                0.25,
            ),
            MetricWeight(
                "argument_case_complete_rate",
                0.15,
            ),
            MetricWeight(
                "required_argument_completeness",
                0.20,
            ),
            MetricWeight(
                "execution_success_rate",
                0.10,
            ),
            MetricWeight(
                "no_tool_accuracy",
                0.05,
            ),
            MetricWeight(
                "overall_case_pass_rate",
                0.10,
            ),
        ),
    ),
    "rag": ModuleBenchmarkConfig(
        label="RAG",
        summary_file=(
            RESULTS_DIR
            / "rag_eval_summary.json"
        ),
        overall_weight=0.25,
        metrics=(
            MetricWeight(
                "document_hit_at_k",
                0.15,
            ),
            MetricWeight(
                "mean_reciprocal_rank",
                0.10,
            ),
            MetricWeight(
                "source_keyword_accuracy",
                0.10,
            ),
            MetricWeight(
                "answer_mode_accuracy",
                0.10,
            ),
            MetricWeight(
                "sufficient_evidence_accuracy",
                0.05,
            ),
            MetricWeight(
                "citation_validity_rate",
                0.15,
            ),
            MetricWeight(
                "answer_concept_coverage",
                0.15,
            ),
            MetricWeight(
                "forbidden_claim_avoidance_rate",
                0.10,
            ),
            MetricWeight(
                "overall_case_pass_rate",
                0.10,
            ),
        ),
    ),
    "report": ModuleBenchmarkConfig(
        label="Review / Report",
        summary_file=(
            RESULTS_DIR
            / "report_eval_summary.json"
        ),
        overall_weight=0.20,
        metrics=(
            MetricWeight(
                "review_status_accuracy",
                0.10,
            ),
            MetricWeight(
                "report_status_accuracy",
                0.10,
            ),
            MetricWeight(
                "report_generation_accuracy",
                0.10,
            ),
            MetricWeight(
                "human_review_accuracy",
                0.10,
            ),
            MetricWeight(
                "severity_preservation_rate",
                0.10,
            ),
            MetricWeight(
                "risk_preservation_rate",
                0.10,
            ),
            MetricWeight(
                "evidence_preservation_rate",
                0.10,
            ),
            MetricWeight(
                "unresolved_preservation_rate",
                0.10,
            ),
            MetricWeight(
                "required_concept_coverage",
                0.10,
            ),
            MetricWeight(
                "overall_case_pass_rate",
                0.10,
            ),
        ),
    ),
}


SAFETY_GATES: tuple[GateRule, ...] = (
    GateRule(
        gate_id="parser_call_success",
        level="safety",
        module="issue_parser",
        metric="call_success_rate",
        operator="min",
        threshold=1.0,
        description=(
            "Issue Parser全部样本必须成功完成调用。"
        ),
    ),
    GateRule(
        gate_id="critical_route_review",
        level="safety",
        module="router",
        metric="critical_human_review_recall",
        operator="min",
        threshold=1.0,
        description=(
            "Critical问题必须全部触发人工复核。"
        ),
    ),
    GateRule(
        gate_id="skill_execution_success",
        level="safety",
        module="skill_call",
        metric="execution_success_rate",
        operator="min",
        threshold=1.0,
        description=(
            "应调用Skill的样本必须全部执行成功。"
        ),
    ),
    GateRule(
        gate_id="rag_pipeline_error",
        level="safety",
        module="rag",
        metric="pipeline_error_rate",
        operator="max",
        threshold=0.0,
        description=(
            "RAG Pipeline不得出现运行异常。"
        ),
    ),
    GateRule(
        gate_id="rag_citation_validity",
        level="safety",
        module="rag",
        metric="citation_validity_rate",
        operator="min",
        threshold=1.0,
        description=(
            "RAG引用必须全部来自真实检索结果。"
        ),
    ),
    GateRule(
        gate_id="rag_forbidden_claims",
        level="safety",
        module="rag",
        metric="forbidden_claim_avoidance_rate",
        operator="min",
        threshold=1.0,
        description=(
            "RAG不得生成禁止的无证据固定结论。"
        ),
    ),
    GateRule(
        gate_id="report_generation_boundary",
        level="safety",
        module="report",
        metric="report_generation_accuracy",
        operator="min",
        threshold=1.0,
        description=(
            "报告生成与阻断边界必须完全正确。"
        ),
    ),
    GateRule(
        gate_id="report_severity_preservation",
        level="safety",
        module="report",
        metric="severity_preservation_rate",
        operator="min",
        threshold=1.0,
        description=(
            "最终报告必须保留原始严重程度。"
        ),
    ),
    GateRule(
        gate_id="report_pipeline_error",
        level="safety",
        module="report",
        metric="pipeline_error_rate",
        operator="max",
        threshold=0.0,
        description=(
            "Review和Report联合流程不得出现异常。"
        ),
    ),
)


QUALITY_GATES: tuple[GateRule, ...] = (
    GateRule(
        gate_id="parser_end_to_end_quality",
        level="quality",
        module="issue_parser",
        metric="overall_case_pass_rate",
        operator="min",
        threshold=0.60,
        description=(
            "Issue Parser完整样本通过率不低于60%。"
        ),
    ),
    GateRule(
        gate_id="router_end_to_end_quality",
        level="quality",
        module="router",
        metric="overall_case_pass_rate",
        operator="min",
        threshold=0.95,
        description=(
            "Router完整样本通过率不低于95%。"
        ),
    ),
    GateRule(
        gate_id="skill_end_to_end_quality",
        level="quality",
        module="skill_call",
        metric="overall_case_pass_rate",
        operator="min",
        threshold=0.90,
        description=(
            "Skill Calling完整样本通过率不低于90%。"
        ),
    ),
    GateRule(
        gate_id="rag_retrieval_quality",
        level="quality",
        module="rag",
        metric="retrieval_case_pass_rate",
        operator="min",
        threshold=0.65,
        description=(
            "RAG检索层完整通过率不低于65%。"
        ),
    ),
    GateRule(
        gate_id="rag_end_to_end_quality",
        level="quality",
        module="rag",
        metric="overall_case_pass_rate",
        operator="min",
        threshold=0.60,
        description=(
            "RAG完整样本通过率不低于60%。"
        ),
    ),
    GateRule(
        gate_id="report_end_to_end_quality",
        level="quality",
        module="report",
        metric="overall_case_pass_rate",
        operator="min",
        threshold=0.95,
        description=(
            "Review和Report完整通过率不低于95%。"
        ),
    ),
)


PASS_SCORE = 85.0   # 总分

CONDITIONAL_PASS_SCORE = 75.0   # 有条件通过分数

MINIMUM_MODULE_SCORE = 75.0  # 单独模块自己得分也不能低于75


def validate_benchmark_config() -> None:
    """校验模块权重和指标权重。"""

    overall_weight = sum(
        config.overall_weight
        for config in MODULE_CONFIGS.values()
    )

    if abs(overall_weight - 1.0) > 1e-9:
        raise ValueError(
            "模块总权重必须等于1.0，"
            f"当前为{overall_weight}"
        )

    for module_name, config in (
        MODULE_CONFIGS.items()
    ):
        metric_weight = sum(
            metric.weight
            for metric in config.metrics
        )

        if abs(metric_weight - 1.0) > 1e-9:
            raise ValueError(
                f"模块{module_name}的"
                "指标总权重必须等于1.0，"
                f"当前为{metric_weight}"
            )