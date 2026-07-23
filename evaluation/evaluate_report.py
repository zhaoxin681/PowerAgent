"""评估Review Agent与Final Report的可靠性。"""

from __future__ import annotations

import argparse
import json
import re
import time
from pathlib import Path
from typing import Any

from agent_core.report_agent import ReportAgent
from agent_core.review_agent import ReviewAgent
from agent_core.workflow_models import (
    FinalWorkflowReport,
    ReviewResult,
)
from evaluation.dataset import (
    load_evaluation_cases,
)
from evaluation.report_fixture import (
    build_review_report_fixture,
)
from evaluation.schemas import (
    EvaluationCase,
    EvaluatorType,
    ReportExpectation,
)


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
    / "report_eval_results.jsonl"
)

SUMMARY_FILE = (
    RESULTS_DIR
    / "report_eval_summary.json"
)

BAD_CASE_FILE = (
    RESULTS_DIR
    / "report_bad_cases.md"
)


def safe_rate(
    numerator: int | float,
    denominator: int | float,
) -> float:
    """安全计算必须存在分母的评测比例。"""

    if denominator == 0:
        return 1.0

    return round(
        numerator / denominator,
        4,
    )


def optional_rate(
    numerator: int | float,
    denominator: int | float,
) -> float | None:
    """没有适用样本时返回None。"""

    if denominator == 0:
        return None

    return round(
        numerator / denominator,
        4,
    )


def require_expectation(
    case: EvaluationCase,
) -> ReportExpectation:
    """读取Review和Report联合评测期望。"""

    expected = case.report_expectation

    if expected is None:
        raise ValueError(
            f"样本{case.case_id}"
            "缺少report_expectation"
        )

    return expected


def normalize_text(
    value: str,
) -> str:
    """规范化概念匹配文本。"""

    return re.sub(
        (
            r"[\s，。！？；：、,.!?;:"
            r"'\"“”‘’（）()【】\[\]-]+"
        ),
        "",
        value.strip().lower(),
    )


def concept_coverage(
    text: str,
    groups: list[list[str]],
) -> tuple[
    bool,
    int,
    list[dict[str, Any]],
]:
    """检查文本是否覆盖全部概念组。"""

    normalized_text = normalize_text(text)

    matched_count = 0

    details: list[dict[str, Any]] = []

    for alternatives in groups:
        matched = any(
            normalize_text(alternative)
            in normalized_text
            for alternative in alternatives
        )

        if matched:
            matched_count += 1

        details.append(
            {
                "alternatives": alternatives,
                "matched": matched,
            }
        )

    return (
        matched_count == len(groups),
        matched_count,
        details,
    )


def classify_report_failure(
    *,
    checks: dict[str, Any],
    error: str | None,
) -> list[str]:
    """根据检查结果自动识别失败类型。"""

    if error is not None:
        return [
            "PIPELINE_ERROR",
        ]

    failure_types: list[str] = []

    check_mapping = {
        "review_status": (
            "REVIEW_STATUS_MISMATCH"
        ),
        "report_status": (
            "REPORT_STATUS_MISMATCH"
        ),
        "generation": (
            "REPORT_GENERATION_MISMATCH"
        ),
        "human_review": (
            "HUMAN_REVIEW_MISMATCH"
        ),
        "severity_preservation": (
            "SEVERITY_NOT_PRESERVED"
        ),
        "risk_preservation": (
            "RISK_NOT_PRESERVED"
        ),
        "required_fields": (
            "MISSING_REPORT_FIELDS"
        ),
        "findings_preservation": (
            "FINDINGS_NOT_PRESERVED"
        ),
        "recommendations_preservation": (
            "RECOMMENDATIONS_NOT_PRESERVED"
        ),
        "evidence_preservation": (
            "EVIDENCE_NOT_PRESERVED"
        ),
        "unresolved_preservation": (
            "UNRESOLVED_ITEMS_NOT_PRESERVED"
        ),
        "review_concepts": (
            "REVIEW_CONCEPT_MISS"
        ),
        "report_concepts": (
            "REPORT_CONCEPT_MISS"
        ),
        "evidence_concepts": (
            "EVIDENCE_CONCEPT_MISS"
        ),
        "unresolved_concepts": (
            "UNRESOLVED_CONCEPT_MISS"
        ),
        "forbidden_claims": (
            "UNSUPPORTED_CLAIM"
        ),
    }

    for check_name, failure_type in (
        check_mapping.items()
    ):
        check = checks.get(check_name)

        if (
            isinstance(check, dict)
            and not check.get(
                "passed",
                False,
            )
        ):
            failure_types.append(
                failure_type
            )

    return failure_types


def evaluate_report_case(
    case: EvaluationCase,
    *,
    review_agent: ReviewAgent | None = None,
    report_agent: ReportAgent | None = None,
) -> tuple[
    ReviewResult,
    FinalWorkflowReport,
    dict[str, Any],
    dict[str, int],
]:
    """执行一条Review和Report联合评测样本。"""

    expected = require_expectation(
        case
    )

    trace_id = (
        f"report-eval-{case.case_id}"
    )

    fixture = build_review_report_fixture(
        expected.scenario,
        trace_id=trace_id,
    )

    reviewer = (
        review_agent
        or ReviewAgent()
    )

    reporter = (
        report_agent
        or ReportAgent()
    )

    # 1. 执行Review Agent
    review_result = reviewer.review(
        issue=fixture.issue,
        plan=list(fixture.plan),
        tool_results=list(
            fixture.tool_results
        ),
        rag_answers=list(
            fixture.rag_answers
        ),
        errors=list(fixture.errors),
        decision=fixture.decision,
        trace_id=trace_id,
    )

    # 2. 执行Report Agent
    final_report = reporter.generate(
        issue=fixture.issue,
        review_result=review_result,
        trace_id=trace_id,
        device_id=fixture.device_id,
    )

    # 3. 检查Review状态
    review_status_passed = (
        review_result.status
        == expected.expected_review_status
    )

    # 4. 检查Report状态
    report_status_passed = (
        final_report.status
        == expected.expected_report_status
    )

    generated = (
        final_report.report is not None
    )

    generation_passed = (
        generated
        == expected.should_generate
    )

    # 5. 检查人工复核状态
    human_review_passed = (
        final_report.needs_human_review
        == expected.needs_human_review
    )

    # 6. 检查Issue严重程度是否保留
    severity_passed = (
        final_report.issue_severity
        == expected.expected_issue_severity
    )

    # 7. 检查风险等级
    risk_passed = (
        review_result.risk_level
        == expected.expected_risk_level
    )

    required_field_total = len(
        expected.required_fields
    )

    required_field_present = 0
    missing_fields: list[str] = []

    # 被阻断的报告没有ReportGenerationOutput。
    if final_report.report is None:
        report_payload: dict[str, Any] = {}

        missing_fields = list(
            expected.required_fields
        )

        field_passed = (
            required_field_total == 0
        )

        # 报告本就不应生成时，字段传递指标不适用，
        # 在单条样本判断中视为通过。
        findings_preserved = (
            not expected.should_generate
        )

        recommendations_preserved = (
            not expected.should_generate
        )

        evidence_preserved = (
            not expected.should_generate
        )

        unresolved_preserved = (
            not expected.should_generate
        )

    else:
        report_payload = (
            final_report.report.model_dump(
                mode="json"
            )
        )

        missing_fields = [
            field
            for field
            in expected.required_fields
            if field not in report_payload
        ]

        required_field_present = (
            required_field_total
            - len(missing_fields)
        )

        field_passed = not missing_fields

        # Report Agent应完整保留Review结果。
        findings_preserved = (
            final_report.report.key_findings
            == review_result.findings
        )

        recommendations_preserved = (
            final_report
            .report
            .recommended_actions
            == review_result.recommendations
        )

        evidence_preserved = (
            final_report.report.evidence
            == review_result.evidence
        )

        expected_unresolved_items = (
            review_result.unresolved_items
            + review_result.review_issues
        )

        unresolved_preserved = (
            final_report
            .report
            .unresolved_items
            == expected_unresolved_items
        )

        # 同时检查Review和Report中的风险一致性。
        risk_passed = (
            risk_passed
            and final_report.report.risk_level
            == review_result.risk_level
        )

    # 8. 组织不同字段对应的概念检查文本
    review_payload = (
        review_result.model_dump(
            mode="json"
        )
    )

    final_report_payload = (
        final_report.model_dump(
            mode="json"
        )
    )

    review_text = json.dumps(
        review_payload,
        ensure_ascii=False,
    )

    report_text = json.dumps(
        final_report_payload,
        ensure_ascii=False,
    )

    evidence_text = "\n".join(
        review_result.evidence
    )

    unresolved_text = "\n".join(
        review_result.unresolved_items
        + review_result.review_issues
    )

    (
        review_concepts_passed,
        review_matched,
        review_concept_details,
    ) = concept_coverage(
        review_text,
        expected.required_review_concepts,
    )

    (
        report_concepts_passed,
        report_matched,
        report_concept_details,
    ) = concept_coverage(
        report_text,
        expected.required_report_concepts,
    )

    (
        evidence_concepts_passed,
        evidence_matched,
        evidence_concept_details,
    ) = concept_coverage(
        evidence_text,
        expected.required_evidence_concepts,
    )

    (
        unresolved_concepts_passed,
        unresolved_matched,
        unresolved_concept_details,
    ) = concept_coverage(
        unresolved_text,
        expected.required_unresolved_concepts,
    )

    # 9. 检查禁止结论
    combined_text = (
        review_text
        + "\n"
        + report_text
    )

    matched_forbidden_claims = [
        claim
        for claim in expected.forbidden_claims
        if (
            normalize_text(claim)
            in normalize_text(
                combined_text
            )
        )
    ]

    forbidden_claims_passed = (
        not matched_forbidden_claims
    )

    # 10. 汇总单条样本是否通过
    overall_passed = all(
        [
            review_status_passed,
            report_status_passed,
            generation_passed,
            human_review_passed,
            severity_passed,
            risk_passed,
            field_passed,
            findings_preserved,
            recommendations_preserved,
            evidence_preserved,
            unresolved_preserved,
            review_concepts_passed,
            report_concepts_passed,
            evidence_concepts_passed,
            unresolved_concepts_passed,
            forbidden_claims_passed,
        ]
    )

    checks = {
        "review_status": {
            "passed": review_status_passed,
            "expected": (
                expected
                .expected_review_status
                .value
            ),
            "actual": (
                review_result.status.value
            ),
        },
        "report_status": {
            "passed": report_status_passed,
            "expected": (
                expected
                .expected_report_status
                .value
            ),
            "actual": (
                final_report.status.value
            ),
        },
        "generation": {
            "passed": generation_passed,
            "expected": (
                expected.should_generate
            ),
            "actual": generated,
        },
        "human_review": {
            "passed": human_review_passed,
            "expected": (
                expected.needs_human_review
            ),
            "actual": (
                final_report
                .needs_human_review
            ),
        },
        "severity_preservation": {
            "passed": severity_passed,
            "expected": (
                expected
                .expected_issue_severity
                .value
            ),
            "actual": (
                final_report
                .issue_severity
                .value
            ),
        },
        "risk_preservation": {
            "passed": risk_passed,
            "expected": (
                expected
                .expected_risk_level
                .value
            ),
            "actual": (
                review_result
                .risk_level
                .value
            ),
        },
        "required_fields": {
            "passed": field_passed,
            "expected": (
                expected.required_fields
            ),
            "missing": missing_fields,
            "actual_fields": sorted(
                report_payload.keys()
            ),
        },
        "findings_preservation": {
            "passed": findings_preserved,
            "review": (
                review_result.findings
            ),
            "report": (
                final_report.report.key_findings
                if final_report.report
                is not None
                else None
            ),
        },
        "recommendations_preservation": {
            "passed": (
                recommendations_preserved
            ),
            "review": (
                review_result.recommendations
            ),
            "report": (
                final_report
                .report
                .recommended_actions
                if final_report.report
                is not None
                else None
            ),
        },
        "evidence_preservation": {
            "passed": evidence_preserved,
            "review": (
                review_result.evidence
            ),
            "report": (
                final_report.report.evidence
                if final_report.report
                is not None
                else None
            ),
        },
        "unresolved_preservation": {
            "passed": unresolved_preserved,
            "review": (
                review_result.unresolved_items
                + review_result.review_issues
            ),
            "report": (
                final_report
                .report
                .unresolved_items
                if final_report.report
                is not None
                else None
            ),
        },
        "review_concepts": {
            "passed": (
                review_concepts_passed
            ),
            "matched": review_matched,
            "total": len(
                expected
                .required_review_concepts
            ),
            "details": (
                review_concept_details
            ),
        },
        "report_concepts": {
            "passed": (
                report_concepts_passed
            ),
            "matched": report_matched,
            "total": len(
                expected
                .required_report_concepts
            ),
            "details": (
                report_concept_details
            ),
        },
        "evidence_concepts": {
            "passed": (
                evidence_concepts_passed
            ),
            "matched": evidence_matched,
            "total": len(
                expected
                .required_evidence_concepts
            ),
            "details": (
                evidence_concept_details
            ),
        },
        "unresolved_concepts": {
            "passed": (
                unresolved_concepts_passed
            ),
            "matched": unresolved_matched,
            "total": len(
                expected
                .required_unresolved_concepts
            ),
            "details": (
                unresolved_concept_details
            ),
        },
        "forbidden_claims": {
            "passed": (
                forbidden_claims_passed
            ),
            "expected_absent": (
                expected.forbidden_claims
            ),
            "matched": (
                matched_forbidden_claims
            ),
        },
        "overall": {
            "passed": overall_passed,
        },
    }

    generated_case = int(
        expected.should_generate
    )

    required_field_case = int(
        bool(expected.required_fields)
    )

    counts = {
        "review_status_correct": int(
            review_status_passed
        ),
        "report_status_correct": int(
            report_status_passed
        ),
        "generation_correct": int(
            generation_passed
        ),
        "human_review_correct": int(
            human_review_passed
        ),
        "severity_preserved": int(
            severity_passed
        ),
        "risk_preserved": int(
            risk_passed
        ),
        "required_field_case_total": (
            required_field_case
        ),
        "required_field_case_complete": int(
            required_field_case
            and field_passed
        ),
        "required_field_total": (
            required_field_total
        ),
        "required_field_present": (
            required_field_present
        ),
        "generated_expected_total": (
            generated_case
        ),
        "findings_preserved": int(
            generated_case
            and findings_preserved
        ),
        "recommendations_preserved": int(
            generated_case
            and recommendations_preserved
        ),
        "evidence_preserved": int(
            generated_case
            and evidence_preserved
        ),
        "unresolved_preserved": int(
            generated_case
            and unresolved_preserved
        ),
        "required_concept_total": (
            len(
                expected
                .required_review_concepts
            )
            + len(
                expected
                .required_report_concepts
            )
            + len(
                expected
                .required_evidence_concepts
            )
            + len(
                expected
                .required_unresolved_concepts
            )
        ),
        "required_concept_matched": (
            review_matched
            + report_matched
            + evidence_matched
            + unresolved_matched
        ),
        "forbidden_claim_total": len(
            expected.forbidden_claims
        ),
        "forbidden_claim_absent": (
            len(expected.forbidden_claims)
            - len(matched_forbidden_claims)
        ),
        "case_passed": int(
            overall_passed
        ),
    }

    return (
        review_result,
        final_report,
        checks,
        counts,
    )


def build_bad_case_markdown(
    results: list[dict[str, Any]],
) -> str:
    """生成Review和Report独立Bad Case报告。"""

    bad_results = [
        result
        for result in results
        if not result["passed"]
    ]

    lines = [
        "# Review and Report Bad Cases",
        "",
        "该文件由联合评测脚本自动生成。",
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
                "### 用户输入",
                "",
                result["user_input"],
                "",
                "### 自动分类",
                "",
                (
                    ", ".join(
                        result["failure_types"]
                    )
                    or "UNCLASSIFIED"
                ),
                "",
                "### 期望结果",
                "",
                "```json",
                json.dumps(
                    result["expected"],
                    ensure_ascii=False,
                    indent=2,
                ),
                "```",
                "",
                "### Review结果",
                "",
                "```json",
                json.dumps(
                    result["review_result"],
                    ensure_ascii=False,
                    indent=2,
                ),
                "```",
                "",
                "### 最终报告",
                "",
                "```json",
                json.dumps(
                    result["final_report"],
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
            ]
        )

        if result["error"] is not None:
            lines.extend(
                [
                    "### 异常",
                    "",
                    result["error"],
                    "",
                ]
            )

        lines.extend(
            [
                "### 人工分析",
                "",
                "- 错误层级：Review / Report / Fixture / 标注",
                "- 错误原因：",
                "- 修复建议：",
                "- 回归状态：待修复",
                "",
            ]
        )

    return "\n".join(lines)


def parse_arguments() -> argparse.Namespace:
    """解析命令行参数。"""

    parser = argparse.ArgumentParser(
        description=(
            "评估PowerAgent Review和Final Report"
        ),
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
        help="只运行前N条Report样本",
    )

    parser.add_argument(
        "--case-id",
        action="append",
        default=[],
        help=(
            "只运行指定case id，"
            "可以重复传入"
        ),
    )

    return parser.parse_args()


def main() -> None:
    """运行Review和Report联合自动评测。"""

    args = parse_arguments()

    cases = load_evaluation_cases(
        args.case_file,
        evaluator=EvaluatorType.REPORT,
        case_ids=args.case_id,
        limit=args.limit,
    )

    if not cases:
        raise ValueError(
            "没有可运行的Review/Report评测样本。"
        )

    RESULTS_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    review_agent = ReviewAgent()
    report_agent = ReportAgent()

    results: list[dict[str, Any]] = []

    aggregate = {
        "total_cases": len(cases),
        "review_status_correct": 0,
        "report_status_correct": 0,
        "generation_correct": 0,
        "human_review_correct": 0,
        "severity_preserved": 0,
        "risk_preserved": 0,
        "required_field_case_total": 0,
        "required_field_case_complete": 0,
        "required_field_total": 0,
        "required_field_present": 0,
        "generated_expected_total": 0,
        "findings_preserved": 0,
        "recommendations_preserved": 0,
        "evidence_preserved": 0,
        "unresolved_preserved": 0,
        "required_concept_total": 0,
        "required_concept_matched": 0,
        "forbidden_claim_total": 0,
        "forbidden_claim_absent": 0,
        "case_passed": 0,
        "pipeline_error_count": 0,
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
            (
                review_result,
                final_report,
                checks,
                counts,
            ) = evaluate_report_case(
                case,
                review_agent=review_agent,
                report_agent=report_agent,
            )

            latency = (
                time.perf_counter()
                - start_time
            )

            failure_types = (
                classify_report_failure(
                    checks=checks,
                    error=None,
                )
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
                "expected": (
                    require_expectation(
                        case
                    ).model_dump(
                        mode="json"
                    )
                ),
                "review_result": (
                    review_result.model_dump(
                        mode="json"
                    )
                ),
                "final_report": (
                    final_report.model_dump(
                        mode="json"
                    )
                ),
                "checks": checks,
                "failure_types": (
                    failure_types
                ),
                "error": None,
            }

            for key, value in (
                counts.items()
            ):
                aggregate[key] += value

        except Exception as exc:
            latency = (
                time.perf_counter()
                - start_time
            )

            aggregate[
                "pipeline_error_count"
            ] += 1

            error_message = (
                f"{type(exc).__name__}: {exc}"
            )

            result = {
                "case_id": case.case_id,
                "user_input": case.user_input,
                "passed": False,
                "latency_seconds": round(
                    latency,
                    6,
                ),
                "expected": (
                    require_expectation(
                        case
                    ).model_dump(
                        mode="json"
                    )
                ),
                "review_result": None,
                "final_report": None,
                "checks": {},
                "failure_types": [
                    "PIPELINE_ERROR",
                ],
                "error": error_message,
            }

        aggregate[
            "total_latency_seconds"
        ] += latency

        results.append(result)

    total = int(
        aggregate["total_cases"]
    )

    generated_total = int(
        aggregate[
            "generated_expected_total"
        ]
    )

    summary = {
        "total_cases": total,
        "review_status_accuracy": safe_rate(
            aggregate[
                "review_status_correct"
            ],
            total,
        ),
        "report_status_accuracy": safe_rate(
            aggregate[
                "report_status_correct"
            ],
            total,
        ),
        "report_generation_accuracy": safe_rate(
            aggregate[
                "generation_correct"
            ],
            total,
        ),
        "human_review_accuracy": safe_rate(
            aggregate[
                "human_review_correct"
            ],
            total,
        ),
        "severity_preservation_rate": (
            safe_rate(
                aggregate[
                    "severity_preserved"
                ],
                total,
            )
        ),
        "risk_preservation_rate": safe_rate(
            aggregate["risk_preserved"],
            total,
        ),
        "required_field_case_complete_rate": (
            optional_rate(
                aggregate[
                    "required_field_case_complete"
                ],
                aggregate[
                    "required_field_case_total"
                ],
            )
        ),
        "required_field_completeness": (
            optional_rate(
                aggregate[
                    "required_field_present"
                ],
                aggregate[
                    "required_field_total"
                ],
            )
        ),
        "findings_preservation_rate": (
            optional_rate(
                aggregate[
                    "findings_preserved"
                ],
                generated_total,
            )
        ),
        "recommendations_preservation_rate": (
            optional_rate(
                aggregate[
                    "recommendations_preserved"
                ],
                generated_total,
            )
        ),
        "evidence_preservation_rate": (
            optional_rate(
                aggregate[
                    "evidence_preserved"
                ],
                generated_total,
            )
        ),
        "unresolved_preservation_rate": (
            optional_rate(
                aggregate[
                    "unresolved_preserved"
                ],
                generated_total,
            )
        ),
        "required_concept_coverage": (
            optional_rate(
                aggregate[
                    "required_concept_matched"
                ],
                aggregate[
                    "required_concept_total"
                ],
            )
        ),
        "forbidden_claim_avoidance_rate": (
            optional_rate(
                aggregate[
                    "forbidden_claim_absent"
                ],
                aggregate[
                    "forbidden_claim_total"
                ],
            )
        ),
        "overall_case_pass_rate": safe_rate(
            aggregate["case_passed"],
            total,
        ),
        "pipeline_error_rate": safe_rate(
            aggregate[
                "pipeline_error_count"
            ],
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

    # 写入逐条结果
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

    # 写入汇总结果
    SUMMARY_FILE.write_text(
        json.dumps(
            summary,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    # 写入Bad Case
    BAD_CASE_FILE.write_text(
        build_bad_case_markdown(
            results
        ),
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

    print(
        f"\n详细结果：{RESULT_FILE}"
    )

    print(
        f"汇总结果：{SUMMARY_FILE}"
    )

    print(
        f"Bad Case：{BAD_CASE_FILE}"
    )


if __name__ == "__main__":
    main()