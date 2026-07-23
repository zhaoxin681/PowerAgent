"""统一评测看板核心逻辑测试。"""

from copy import deepcopy

from evaluation.benchmark_config import (
    MODULE_CONFIGS,
)
from evaluation.build_evaluation_dashboard import (
    build_dashboard_from_summaries,
)


def make_perfect_summaries(
) -> dict[str, dict[str, float | int]]:
    """构造所有指标均为100%的Summary。"""

    summaries: dict[
        str,
        dict[str, float | int]
    ] = {}

    for module_name, config in (
        MODULE_CONFIGS.items()
    ):
        summary: dict[
            str,
            float | int
        ] = {
            "total_cases": 10,
        }

        for metric in config.metrics:
            summary[metric.name] = 1.0

        summaries[module_name] = (
            summary
        )

    summaries[
        "router"
    ][
        "critical_human_review_recall"
    ] = 1.0

    summaries[
        "skill_call"
    ][
        "execution_success_rate"
    ] = 1.0

    summaries[
        "rag"
    ][
        "pipeline_error_rate"
    ] = 0.0

    summaries[
        "rag"
    ][
        "citation_validity_rate"
    ] = 1.0

    summaries[
        "rag"
    ][
        "forbidden_claim_avoidance_rate"
    ] = 1.0

    summaries[
        "rag"
    ][
        "retrieval_case_pass_rate"
    ] = 1.0

    summaries[
        "report"
    ][
        "pipeline_error_rate"
    ] = 0.0

    return summaries


def test_perfect_dashboard_passes() -> None:
    """全部指标满分时应正式通过。"""

    dashboard = (
        build_dashboard_from_summaries(
            make_perfect_summaries()
        )
    )

    assert dashboard["status"] == "pass"

    assert (
        dashboard["overall_score"]
        == 100.0
    )

    assert (
        dashboard[
            "safety_gate_passed"
        ]
        is True
    )

    assert (
        dashboard[
            "quality_gate_passed"
        ]
        is True
    )


def test_safety_gate_failure_blocks_acceptance(
) -> None:
    """引用合法率失败时必须判定为失败。"""

    summaries = (
        make_perfect_summaries()
    )

    summaries[
        "rag"
    ][
        "citation_validity_rate"
    ] = 0.9

    dashboard = (
        build_dashboard_from_summaries(
            summaries
        )
    )

    assert dashboard["status"] == "fail"

    assert (
        dashboard[
            "safety_gate_passed"
        ]
        is False
    )

    assert any(
        item["gate_id"]
        == "rag_citation_validity"
        for item
        in dashboard["blocking_issues"]
    )


def test_quality_gap_returns_conditional_pass(
) -> None:
    """安全通过但端到端质量不足时应有条件通过。"""

    summaries = deepcopy(
        make_perfect_summaries()
    )

    summaries[
        "issue_parser"
    ][
        "overall_case_pass_rate"
    ] = 0.40

    summaries[
        "rag"
    ][
        "overall_case_pass_rate"
    ] = 0.46

    dashboard = (
        build_dashboard_from_summaries(
            summaries
        )
    )

    assert (
        dashboard["overall_score"]
        >= 75.0
    )

    assert (
        dashboard[
            "safety_gate_passed"
        ]
        is True
    )

    assert (
        dashboard[
            "quality_gate_passed"
        ]
        is False
    )

    assert (
        dashboard["status"]
        == "conditional_pass"
    )