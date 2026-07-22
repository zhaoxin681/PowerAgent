"""评估PowerSystemIssueParser的分类和字段提取能力。"""

from __future__ import annotations

import argparse
import json
import re
import time
from pathlib import Path
from evaluation.dataset import load_evaluation_cases
from evaluation.schemas import (
    EvaluationCase,
    EvaluatorType,
    IssueExpectation,
)

from agent_core.issue_parser import PowerSystemIssueParser
from agent_core.llm_client import LLMClientError
from agent_core.schemas import PowerSystemIssue


# 获取绝对路径
PROJECT_ROOT = Path(__file__).resolve().parents[1]

DEFAULT_CASE_FILE = (
    PROJECT_ROOT / "evaluation" / "test_cases.jsonl"
) # jsonl每行都是一个完整的JSON对象

RESULTS_DIR = PROJECT_ROOT / "evaluation" / "results"

RESULT_FILE = RESULTS_DIR / "parser_eval_results.jsonl"
SUMMARY_FILE = RESULTS_DIR / "parser_eval_summary.json"
BAD_CASE_FILE = RESULTS_DIR / "parser_bad_cases.md"


def normalize_text(text: str) -> str:
    """
    统一文本格式，降低空格、大小写和标点差异对评测的影响。

    示例：
        "低 180 mV" -> "低180mv"
        "SOC 80%" -> "soc80%"
    """

    normalized = text.lower().strip()

    normalized = re.sub(
        r"[\s，。！？；：、“”‘’（）()\[\]{}《》<>]+",
        "",
        normalized,
    )

    return normalized


def flatten_field(
    issue: PowerSystemIssue,
    field_name: str,
) -> str:
    """将结构化字段转换成可进行关键词匹配的文本。"""

    value = getattr(issue, field_name)

    if field_name == "operating_conditions":
        return " ".join(
            f"{condition.name} {condition.value} {condition.unit}"
            for condition in value
        )

    if isinstance(value, list):
        return " ".join(str(item) for item in value)

    if hasattr(value, "value"):
        return str(value.value)

    return str(value)


def matches_concept_group(
    actual_text: str,
    alternatives: list[str],
) -> bool:
    """
    判断实际文本是否覆盖一组同义概念。

    alternatives中的任意一种表达被匹配，即认为该概念已覆盖。
    """

    normalized_actual = normalize_text(actual_text)

    return any(
        normalize_text(alternative) in normalized_actual
        for alternative in alternatives
    )


def evaluate_prediction(
    case: EvaluationCase,
    prediction: PowerSystemIssue,
) -> tuple[dict[str, object], dict[str, int]]:
    """比较单条预测结果和人工标注结果。"""

    expected = case.issue_expectation
    if expected is None:
        raise ValueError(
            f"样本{case.case_id}缺少issue_expectation"
        )

    actual_subsystem = prediction.subsystem.value
    actual_task_type = prediction.task_type.value
    actual_severity = prediction.severity.value

    subsystem_passed = (
        prediction.subsystem == expected.subsystem
    )

    task_type_passed = (
        prediction.task_type == expected.task_type
    )

    severity_passed = (
        prediction.severity
        in expected.severity_allowed
    )

    raw_text_passed = (
        not expected.exact_raw_text
        or prediction.raw_text == case.user_input
    )

    checks: dict[str, object] = {
        "subsystem": {
            "passed": subsystem_passed,
            "expected": expected.subsystem.value,
            "actual": actual_subsystem,
        },
        "task_type": {
            "passed": task_type_passed,
            "expected": expected.task_type.value,
            "actual": actual_task_type,
        },
        "severity": {
            "passed": severity_passed,
            "expected": [
                item.value
                for item in expected.severity_allowed
            ],
            "actual": actual_severity,
        },
        "raw_text": {
            "passed": raw_text_passed,
            "expected": (
                case.user_input
                if expected.exact_raw_text
                else "不要求完全一致"
            ),
            "actual": prediction.raw_text,
        },
    }

    # 概念覆盖度检查
    concept_matched = 0
    concept_total = 0
    concept_details: list[dict[str, object]] = []

    for concept in expected.required_concepts:
        actual_field_text = flatten_field(
            prediction,
            concept.field_name,
        )

        matched = matches_concept_group(
            actual_field_text,
            concept.alternatives,
        )

        concept_total += 1

        if matched:
            concept_matched += 1

        concept_details.append(
            {
                "field": concept.field_name,
                "alternatives": (
                    concept.alternatives
                ),
                "actual_text": actual_field_text,
                "matched": matched,
            }
        )

    concept_passed = concept_matched == concept_total

    checks["required_concepts"] = {
        "passed": concept_passed,
        "matched": concept_matched,
        "total": concept_total,
        "details": concept_details,
    }

    # 空字段检查
    empty_correct = 0
    empty_total = 0
    empty_details: list[dict[str, object]] = []

    for field_name in expected.must_be_empty:
        field_value = getattr(prediction, field_name)

        passed = isinstance(field_value, list) and len(field_value) == 0

        empty_total += 1

        if passed:
            empty_correct += 1

        empty_details.append(
            {
                "field": field_name,
                "passed": passed,
                "actual": (
                    [
                        item.model_dump(mode="json")
                        if hasattr(item, "model_dump")
                        else item
                        for item in field_value
                    ]
                    if isinstance(field_value, list)
                    else str(field_value)
                ),
            }
        )

    empty_fields_passed = empty_correct == empty_total
    
    checks["must_be_empty"] = {
        "passed": empty_fields_passed,
        "correct": empty_correct,
        "total": empty_total,
        "details": empty_details,
    }

    # 汇总整体通过与否
    overall_passed = all(
        [
            subsystem_passed,
            task_type_passed,
            severity_passed,
            raw_text_passed,
            concept_passed,
            empty_fields_passed,
        ]
    ) # 列表中所有元素都true时返回true

    checks["overall"] = {
        "passed": overall_passed,
    }

    counts = {
        "subsystem_correct": int(subsystem_passed),
        "task_type_correct": int(task_type_passed),
        "severity_correct": int(severity_passed),
        "raw_text_correct": int(raw_text_passed),
        "concept_matched": concept_matched,
        "concept_total": concept_total,
        "empty_correct": empty_correct,
        "empty_total": empty_total,
        "case_passed": int(overall_passed),
    }

    return checks, counts


# 工具函数
def safe_rate(
    numerator: int,
    denominator: int,
) -> float:
    """安全计算准确率。"""

    if denominator == 0:
        return 1.0

    return round(numerator / denominator, 4)


def build_bad_case_markdown(
    results: list[dict[str, object]],
) -> str:
    """将未通过样本整理成Markdown报告。"""

    bad_results = [
        result
        for result in results
        if not result.get("passed", False)
    ]

    lines = [
        "# PowerSystemIssueParser Bad Cases",
        "",
        "该文件由评测脚本自动生成。",
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
                f"## {result['id']}",
                "",
                "### 输入",
                "",
                result["input"],
                "",
            ]
        )

        if result.get("error"):
            lines.extend(
                [
                    "### 调用错误",
                    "",
                    "```text",
                    result["error"],
                    "```",
                    "",
                ]
            )
            continue

        failed_checks = [
            name
            for name, check in result["checks"].items()
            if (
                isinstance(check, dict)
                and "passed" in check
                and not check["passed"]
            )
        ]

        lines.extend(
            [
                "### 未通过项目",
                "",
                ", ".join(failed_checks),
                "",
                "### 预测结果",
                "",
                "```json",
                json.dumps(
                    result["prediction"],
                    ensure_ascii=False,
                    indent=2,
                ),
                "```",
                "",
                "### 检查详情",
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
                "- Prompt修改建议：",
                "",
            ]
        )

    return "\n".join(lines)


def parse_arguments() -> argparse.Namespace:
    """解析命令行参数。"""

    parser = argparse.ArgumentParser(
        description="评估动力系统问题结构化解析器",
    )

    parser.add_argument(
        "--case-file",
        type=Path,
        default=DEFAULT_CASE_FILE,
        help="测试集JSONL文件路径",
    )

    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="只运行前N条测试样本",
    )

    parser.add_argument(
        "--case-id",
        action="append",
        default=[],
        help="只运行指定case id，可重复传入",
    )

    parser.add_argument(
        "--sleep",
        type=float,
        default=0.2,
        help="两次API调用之间的等待时间",
    )

    return parser.parse_args()


def main() -> None:
    """运行完整评测。"""

    args = parse_arguments()

    cases = load_evaluation_cases(
        args.case_file,
        evaluator=EvaluatorType.ISSUE_PARSER,
        case_ids=args.case_id,
        limit=args.limit,
    )

    if not cases:
        raise ValueError("没有可运行的测试样本。")

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    parser = PowerSystemIssueParser()

    results: list[dict[str, object]] = []

    aggregate = {
        "total_cases": len(cases),
        "call_success": 0,
        "subsystem_correct": 0,
        "task_type_correct": 0,
        "severity_correct": 0,
        "raw_text_correct": 0,
        "concept_matched": 0,
        "concept_total": 0,
        "empty_correct": 0,
        "empty_total": 0,
        "case_passed": 0,
        "total_latency_seconds": 0.0,
    }

    for index, case in enumerate(cases, start=1):
        print(
            f"[{index}/{len(cases)}] "
            f"正在评估 {case.case_id}..."
        )

        start_time = time.perf_counter()

        try:
            prediction = parser.parse(case.user_input)

            latency = time.perf_counter() - start_time

            checks, counts = evaluate_prediction(
                case,
                prediction,
            )

            result = {
                "id": case.case_id,
                "input": case.user_input,
                "passed": checks["overall"]["passed"],
                "latency_seconds": round(latency, 4),
                "prediction": prediction.model_dump(
                    mode="json",
                ),
                "checks": checks,
                "error": None,
            }

            aggregate["call_success"] += 1
            aggregate["total_latency_seconds"] += latency

            for key, value in counts.items():
                aggregate[key] += value

        except (LLMClientError, ValueError) as exc:
            latency = time.perf_counter() - start_time

            result = {
                "id": case.case_id,
                "input": case.user_input,
                "passed": False,
                "latency_seconds": round(latency, 4),
                "prediction": None,
                "checks": {},
                "error": str(exc),
            }

            aggregate["total_latency_seconds"] += latency

        results.append(result)

        if args.sleep > 0 and index < len(cases):
            time.sleep(args.sleep)

    total = aggregate["total_cases"]

    summary = {
        "total_cases": total,
        "call_success_count": aggregate["call_success"],
        "call_success_rate": safe_rate(
            aggregate["call_success"],
            total,
        ),
        "subsystem_accuracy": safe_rate(
            aggregate["subsystem_correct"],
            total,
        ),
        "task_type_accuracy": safe_rate(
            aggregate["task_type_correct"],
            total,
        ),
        "severity_accuracy": safe_rate(
            aggregate["severity_correct"],
            total,
        ),
        "raw_text_accuracy": safe_rate(
            aggregate["raw_text_correct"],
            total,
        ),
        "concept_coverage": safe_rate(
            aggregate["concept_matched"],
            aggregate["concept_total"],
        ),
        "empty_field_accuracy": safe_rate(
            aggregate["empty_correct"],
            aggregate["empty_total"],
        ),
        "overall_case_pass_rate": safe_rate(
            aggregate["case_passed"],
            total,
        ),
        "average_latency_seconds": round(
            aggregate["total_latency_seconds"] / total,
            4,
        ),
        "counts": aggregate,
    }

    with RESULT_FILE.open("w", encoding="utf-8") as file:
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