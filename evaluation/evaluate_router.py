"""评估Router Agent的确定性路由能力。"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any

from agent_core.router_agent import (
    RouteStatus,
    RouterAgent,
)
from agent_core.schemas import PowerSystemIssue
from evaluation.dataset import (
    load_evaluation_cases,
)
from evaluation.schemas import (
    EvaluationCase,
    EvaluatorType,
)
from agent_core.router_agent import RouterDecision


PROJECT_ROOT = Path(__file__).resolve().parents[1]

DEFAULT_CASE_FILE = (
    PROJECT_ROOT
    / "evaluation"
    / "test_cases.jsonl"
)

RESULTS_DIR = (
    PROJECT_ROOT
    / "evaluation"
    / "results"
)

RESULT_FILE = (
    RESULTS_DIR
    / "router_eval_results.jsonl"
)

SUMMARY_FILE = (
    RESULTS_DIR
    / "router_eval_summary.json"
)

BAD_CASE_FILE = (
    RESULTS_DIR
    / "router_bad_cases.md"
)


def safe_rate(
    numerator: int,
    denominator: int,
) -> float:
    """安全计算评测比例。"""

    if denominator == 0:
        return 1.0

    return round(
        numerator / denominator,
        4,
    )


def build_router_issue(
    case: EvaluationCase,
) -> PowerSystemIssue:
    """根据人工标注构造Router的确定性输入。"""

    expected = case.route_expectation

    if expected is None:
        raise ValueError(
            f"样本{case.case_id}"
            "缺少route_expectation"
        )

    return PowerSystemIssue(
        raw_text=case.user_input,
        subsystem=expected.issue.subsystem,
        task_type=expected.issue.task_type,
        symptoms=[],
        operating_conditions=[],
        user_hypotheses=[],
        requested_outputs=[],
        missing_information=(
            expected.issue.missing_information
        ),
        severity=expected.issue.severity,
        confidence=1.0,
    )


def evaluate_router_case(
    case: EvaluationCase,
    *,
    router: RouterAgent | None = None,
) -> tuple[
    RouterDecision,
    dict[str, Any],
    dict[str, int],
]:
    """运行并评估一条Router测试样本。"""

    expected = case.route_expectation

    if expected is None:
        raise ValueError(
            f"样本{case.case_id}"
            "缺少route_expectation"
        )

    issue = build_router_issue(case)

    agent = router or RouterAgent()

    decision = agent.route(
        issue,
        trace_id=f"router-eval-{case.case_id}",
    )

    route_passed = (
        decision.route == expected.route
    )

    status_passed = (
        decision.status == expected.status
    )

    human_review_passed = (
        decision.needs_human_review
        == expected.needs_human_review
    )

    required_missing_items = [
        *expected.issue.missing_information,
        *expected.required_missing_information,
    ]

    missing_information_passed = all(
        item in decision.missing_information
        for item in required_missing_items
    )

    overall_passed = all(
        [
            route_passed,
            status_passed,
            human_review_passed,
            missing_information_passed,
        ]
    )

    checks = {
        "route": {
            "passed": route_passed,
            "expected": expected.route.value,
            "actual": decision.route.value,
        },
        "status": {
            "passed": status_passed,
            "expected": expected.status.value,
            "actual": decision.status.value,
        },
        "human_review": {
            "passed": human_review_passed,
            "expected": (
                expected.needs_human_review
            ),
            "actual": (
                decision.needs_human_review
            ),
        },
        "missing_information": {
            "passed": (
                missing_information_passed
            ),
            "expected_required": (
                required_missing_items
            ),
            "actual": (
                decision.missing_information
            ),
        },
        "overall": {
            "passed": overall_passed,
        },
    }

    is_unsupported = (
        expected.status
        == RouteStatus.UNSUPPORTED
    )

    is_needs_information = (
        expected.status
        == RouteStatus.NEEDS_INFORMATION
    )

    is_critical = (
        expected.issue.severity.value
        == "critical"
    )

    counts = {
        "route_correct": int(route_passed),
        "status_correct": int(status_passed),
        "human_review_correct": int(
            human_review_passed
        ),
        "missing_information_correct": int(
            missing_information_passed
        ),
        "unsupported_total": int(
            is_unsupported
        ),
        "unsupported_correct": int(
            is_unsupported and status_passed
        ),
        "needs_information_total": int(
            is_needs_information
        ),
        "needs_information_correct": int(
            is_needs_information
            and status_passed
        ),
        "critical_total": int(
            is_critical
        ),
        "critical_review_correct": int(
            is_critical
            and decision.needs_human_review
        ),
        "case_passed": int(
            overall_passed
        ),
    }

    return decision, checks, counts


def build_bad_case_markdown(
    results: list[dict[str, Any]],
) -> str:
    """生成Router独立Bad Case报告。"""

    bad_results = [
        result
        for result in results
        if not result["passed"]
    ]

    lines = [
        "# Router Agent Bad Cases",
        "",
        "该文件由Router评测脚本自动生成。",
        "",
        f"Bad Case数量：{len(bad_results)}",
        "",
    ]

    if not bad_results:
        lines.extend(
            [
                "当前测试集中没有发现Bad Case。",
                "",
            ]
        )

        return "\n".join(lines)

    for result in bad_results:
        lines.extend(
            [
                f"## {result['case_id']}",
                "",
                "### 输入",
                "",
                result["user_input"],
                "",
                "### Router输入",
                "",
                "```json",
                json.dumps(
                    result["router_input"],
                    ensure_ascii=False,
                    indent=2,
                ),
                "```",
                "",
                "### 实际输出",
                "",
                "```json",
                json.dumps(
                    result["actual"],
                    ensure_ascii=False,
                    indent=2,
                ),
                "```",
                "",
                "### 检查结果",
                "",
                "```json",
                json.dumps(
                    result["checks"],
                    ensure_ascii=False,
                    indent=2,
                ),
                "```",
                "",
                "### 人工分析",
                "",
                "- 错误类型：",
                "- 可能原因：",
                "- Router规则修改建议：",
                "- 回归状态：待修复",
                "",
            ]
        )

    return "\n".join(lines)


def parse_arguments() -> argparse.Namespace:
    """解析命令行参数。"""

    parser = argparse.ArgumentParser(
        description="评估PowerAgent Router Agent",
    )

    parser.add_argument(
        "--case-file",
        type=Path,
        default=DEFAULT_CASE_FILE,
        help="统一评测数据集路径",
    )

    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="只运行前N条Router样本",
    )

    parser.add_argument(
        "--case-id",
        action="append",
        default=[],
        help="只运行指定case id，可重复传入",
    )

    return parser.parse_args()


def main() -> None:
    """运行Router自动评测。"""

    args = parse_arguments()

    cases = load_evaluation_cases(
        args.case_file,
        evaluator=EvaluatorType.ROUTER,
        case_ids=args.case_id,
        limit=args.limit,
    )

    if not cases:
        raise ValueError(
            "没有可运行的Router评测样本。"
        )

    RESULTS_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    router = RouterAgent()

    results: list[dict[str, Any]] = []

    aggregate = {
        "total_cases": len(cases),
        "route_correct": 0,
        "status_correct": 0,
        "human_review_correct": 0,
        "missing_information_correct": 0,
        "unsupported_total": 0,
        "unsupported_correct": 0,
        "needs_information_total": 0,
        "needs_information_correct": 0,
        "critical_total": 0,
        "critical_review_correct": 0,
        "case_passed": 0,
        "total_latency_seconds": 0.0,
    }

    for index, case in enumerate(
        cases,
        start=1,
    ):
        print(
            f"[{index}/{len(cases)}] "
            f"正在评估 {case.case_id}..."
        )

        start_time = time.perf_counter()

        try:
            decision, checks, counts = (
                evaluate_router_case(
                case,
                router=router,
                )
            )

            latency = (
                time.perf_counter()
                - start_time
            )

            expected = case.route_expectation

            if expected is None:
                raise ValueError(
                    "Router期望结果不存在"
                )

            result = {
                "case_id": case.case_id,
                "user_input": case.user_input,
                "passed": (
                    checks["overall"]["passed"]
                ),
                "latency_seconds": round(
                    latency,
                    6,
                ),
                "router_input": (
                    expected.issue.model_dump(
                        mode="json"
                    )
                ),
                "expected": {
                    "route": (
                        expected.route.value
                    ),
                    "status": (
                        expected.status.value
                    ),
                    "needs_human_review": (
                        expected
                        .needs_human_review
                    ),
                    "required_missing_information": (
                        expected
                        .required_missing_information
                    ),
                },
                "actual": (
                    decision.model_dump(
                        mode="json"
                    )
                ),
                "checks": checks,
                "error": None,
            }

            for key, value in counts.items():
                aggregate[key] += value

        except Exception as exc:
            latency = (
                time.perf_counter()
                - start_time
            )

            result = {
                "case_id": case.case_id,
                "user_input": case.user_input,
                "passed": False,
                "latency_seconds": round(
                    latency,
                    6,
                ),
                "router_input": None,
                "expected": None,
                "actual": None,
                "checks": {},
                "error": str(exc),
            }

        aggregate[
            "total_latency_seconds"
        ] += latency

        results.append(result)

    total = aggregate["total_cases"]

    summary = {
        "total_cases": total,
        "route_accuracy": safe_rate(
            aggregate["route_correct"],
            total,
        ),
        "status_accuracy": safe_rate(
            aggregate["status_correct"],
            total,
        ),
        "human_review_accuracy": safe_rate(
            aggregate[
                "human_review_correct"
            ],
            total,
        ),
        "missing_information_accuracy": (
            safe_rate(
                aggregate[
                    "missing_information_correct"
                ],
                total,
            )
        ),
        "unsupported_accuracy": safe_rate(
            aggregate["unsupported_correct"],
            aggregate["unsupported_total"],
        ),
        "needs_information_accuracy": (
            safe_rate(
                aggregate[
                    "needs_information_correct"
                ],
                aggregate[
                    "needs_information_total"
                ],
            )
        ),
        "critical_human_review_recall": (
            safe_rate(
                aggregate[
                    "critical_review_correct"
                ],
                aggregate["critical_total"],
            )
        ),
        "overall_case_pass_rate": safe_rate(
            aggregate["case_passed"],
            total,
        ),
        "average_latency_seconds": round(
            aggregate[
                "total_latency_seconds"
            ]
            / total,
            6,
        ),
        "counts": aggregate,
    }

    with RESULT_FILE.open(
        "w",
        encoding="utf-8",
    ) as file:
        for result in results:
            file.write(
                json.dumps(
                    result,
                    ensure_ascii=False,
                )
                + "\n"
            )

    SUMMARY_FILE.write_text(
        json.dumps(
            summary,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    BAD_CASE_FILE.write_text(
        build_bad_case_markdown(results),
        encoding="utf-8",
    )

    print("\n评测完成：")
    print(
        json.dumps(
            summary,
            ensure_ascii=False,
            indent=2,
        )
    )

    print(f"\n详细结果：{RESULT_FILE}")
    print(f"汇总结果：{SUMMARY_FILE}")
    print(f"Bad Case：{BAD_CASE_FILE}")


if __name__ == "__main__":
    main()