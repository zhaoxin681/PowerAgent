"""真实LLM Tool Calling评测脚本。"""

from __future__ import annotations

import json
from pathlib import Path

from agent_core import (
    SkillRegistry,
    ToolCallingRunner,
    ToolCallingStatus,
)
from agent_core.llm_client import LLMClient
from skills import create_default_skills

import argparse
import time
from typing import Any

from evaluation.dataset import (
    load_evaluation_cases,
)
from evaluation.schemas import (
    EvaluationCase,
    EvaluatorType,
    SkillCallExpectation,
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
    / "skill_eval_results.jsonl"
)

SUMMARY_FILE = (
    RESULTS_DIR
    / "skill_eval_summary.json"
)

BAD_CASE_FILE = (
    RESULTS_DIR
    / "skill_bad_cases.md"
)


def create_registry() -> SkillRegistry:
    """创建评测使用的默认Registry。"""

    registry = SkillRegistry()

    for skill in create_default_skills():
        registry.register(skill)

    return registry

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

def evaluate_argument_keys(
    actual_arguments: dict[str, Any] | None,
    expected_keys: list[str],
) -> tuple[bool, list[str]]:
    """检查Tool Calling是否生成全部必要参数。"""

    arguments = actual_arguments or {}

    missing_keys = [
        key
        for key in expected_keys
        if key not in arguments
    ]

    return not missing_keys, missing_keys


def evaluate_skill_result(
    case: EvaluationCase,
    result: Any,
) -> tuple[dict[str, Any], dict[str, int]]:
    """比较单条Tool Calling结果与人工标注。"""

    expected = case.skill_expectation

    if expected is None:
        raise ValueError(
            f"样本{case.case_id}"
            "缺少skill_expectation"
        )

    actual_status = result.status.value

    status_passed = (
        actual_status
        == expected.expected_status
    )

    if expected.should_call_tool:
        skill_passed = (
            result.tool_name
            == expected.expected_skill
        )
    else:
        skill_passed = (
            result.tool_name is None
        )

    (
        arguments_passed,
        missing_argument_keys,
    ) = evaluate_argument_keys(
        result.arguments,
        expected.expected_argument_keys,
    )

    successful_execution = (
        result.status
        == ToolCallingStatus.SUCCESS
    )

    expected_tool_call = (
        expected.should_call_tool
    )

    execution_passed = (
        successful_execution
        if expected_tool_call
        else True
    )

    no_tool_correct = (
        not expected_tool_call
        and status_passed
        and skill_passed
    )

    overall_passed = all(
        [
            status_passed,
            skill_passed,
            arguments_passed,
        ]
    )

    checks = {
        "status": {
            "passed": status_passed,
            "expected": (
                expected.expected_status
            ),
            "actual": actual_status,
        },
        "skill": {
            "passed": skill_passed,
            "expected": (
                expected.expected_skill
            ),
            "actual": result.tool_name,
        },
        "required_arguments": {
            "passed": arguments_passed,
            "expected": (
                expected.expected_argument_keys
            ),
            "actual": sorted(
                (result.arguments or {}).keys()
            ),
            "missing": missing_argument_keys,
        },
        "execution": {
            "passed": execution_passed,
            "expected": (
                "success"
                if expected_tool_call
                else "not_applicable"
            ),
            "actual": actual_status,
        },
        "overall": {
            "passed": overall_passed,
        },
    }

    counts = {
        "status_correct": int(
            status_passed
        ),
        "skill_correct": int(
            skill_passed
        ),
        "argument_case_complete": int(
            arguments_passed
        ),
        "required_argument_correct": (
            len(
                expected.expected_argument_keys
            )
            - len(missing_argument_keys)
        ),
        "required_argument_total": len(
            expected.expected_argument_keys
        ),
        "expected_tool_call": int(
            expected_tool_call
        ),
        "execution_success": int(
            expected_tool_call
            and successful_execution
        ),
        "no_tool_total": int(
            not expected_tool_call
        ),
        "no_tool_correct": int(
            no_tool_correct
        ),
        "case_passed": int(
            overall_passed
        ),
    }

    return checks, counts


def write_skill_bad_cases(
    results: list[dict[str, Any]],
) -> None:
    """将失败的Skill评测样本写入独立报告。"""

    bad_results = [
        item
        for item in results
        if not item["passed"]
    ]

    lines = [
        "# Tool Calling Bad Cases",
        "",
        "该文件由Skill评测脚本自动生成。",
        "",
        f"Bad Case数量：{len(bad_results)}",
        "",
    ]

    for item in bad_results:
        lines.extend(
            [
                f"## {item['case_id']}",
                "",
                "### 输入",
                "",
                item["user_input"],
                "",
                "### 期望结果",
                "",
                "```json",
                json.dumps(
                    item["expected"],
                    ensure_ascii=False,
                    indent=2,
                ),
                "```",
                "",
                "### 实际结果",
                "",
                "```json",
                json.dumps(
                    item["actual"],
                    ensure_ascii=False,
                    indent=2,
                ),
                "```",
                "",
                "### 检查结果",
                "",
                "```json",
                json.dumps(
                    item["checks"],
                    ensure_ascii=False,
                    indent=2,
                ),
                "```",
                "",
                "### 人工分析",
                "",
                "- 错误类型：",
                "- 可能原因：",
                "- Prompt或代码修改建议：",
                "- 回归状态：待修复",
                "",
            ]
        )

    if not bad_results:
        lines.extend(
            [
                "当前测试集中没有发现Bad Case。",
                "",
            ]
        )

    BAD_CASE_FILE.write_text(
        "\n".join(lines),
        encoding="utf-8",
    )


def parse_arguments() -> argparse.Namespace:
    """解析命令行参数。"""

    parser = argparse.ArgumentParser(
        description="评估PowerAgent Tool Calling能力",
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
        help="只运行前N条Skill样本",
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
        help="两次真实API调用之间的等待时间",
    )

    return parser.parse_args()


def main() -> None:
    """执行真实API Tool Calling评测。"""

    args = parse_arguments()

    cases = load_evaluation_cases(
        args.case_file,
        evaluator=EvaluatorType.SKILL_CALL,
        case_ids=args.case_id,
        limit=args.limit,
    )

    if not cases:
        raise ValueError(
            "没有可运行的Skill评测样本。"
        )

    runner = ToolCallingRunner(
        registry=create_registry(),
        client=LLMClient(),
    )

    RESULTS_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    results: list[dict[str, Any]] = []

    aggregate = {
        "total_cases": len(cases),
        "status_correct": 0,
        "skill_correct": 0,
        "argument_case_complete": 0,
        "required_argument_correct": 0,
        "required_argument_total": 0,
        "execution_success": 0,
        "expected_tool_call": 0,
        "no_tool_total": 0,
        "no_tool_correct": 0,
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
            result = runner.run(
                case.user_input
            )

            latency = (
                time.perf_counter()
                - start_time
            )

            checks, counts = (
                evaluate_skill_result(
                    case,
                    result,
                )
            )

            item = {
                "case_id": case.case_id,
                "user_input": case.user_input,
                "passed": (
                    checks["overall"]["passed"]
                ),
                "latency_seconds": round(
                    latency,
                    4,
                ),
                "expected": (
                    case.skill_expectation.model_dump(
                        mode="json"
                    )
                    if case.skill_expectation
                    else None
                ),
                "actual": {
                    "status": result.status.value,
                    "tool_name": (
                        result.tool_name
                    ),
                    "arguments": (
                        result.arguments
                    ),
                    "error_code": (
                        result.error_code
                    ),
                    "error_message": (
                        result.error_message
                    ),
                },
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

            item = {
                "case_id": case.case_id,
                "user_input": case.user_input,
                "passed": False,
                "latency_seconds": round(
                    latency,
                    4,
                ),
                "expected": (
                    case.skill_expectation.model_dump(
                        mode="json"
                    )
                    if case.skill_expectation
                    else None
                ),
                "actual": None,
                "checks": {},
                "error": str(exc),
            }

        aggregate[
            "total_latency_seconds"
        ] += latency

        results.append(item)

        if (
            args.sleep > 0
            and index < len(cases)
        ):
            time.sleep(args.sleep)

    total = aggregate["total_cases"]

    summary = {
        "total_cases": total,
        "status_accuracy": safe_rate(
            aggregate["status_correct"],
            total,
        ),
        "skill_accuracy": safe_rate(
            aggregate["skill_correct"],
            total,
        ),
        "argument_case_complete_rate": (
            safe_rate(
                aggregate[
                    "argument_case_complete"
                ],
                total,
            )
        ),
        "required_argument_completeness": (
            safe_rate(
                aggregate[
                    "required_argument_correct"
                ],
                aggregate[
                    "required_argument_total"
                ],
            )
        ),
        "execution_success_rate": safe_rate(
            aggregate["execution_success"],
            aggregate["expected_tool_call"],
        ), # 应调用工具的样本中，实际成功执行的比例
        "no_tool_accuracy": safe_rate(
            aggregate["no_tool_correct"],
            aggregate["no_tool_total"],
        ),  # 不应调用工具的样本中，正确保持不调用的比例
        "overall_case_pass_rate": safe_rate(
            aggregate["case_passed"],
            total,
        ),
        "average_latency_seconds": round(
            aggregate[
                "total_latency_seconds"
            ]
            / total,
            4,
        ),
        "counts": aggregate,
    }

    with RESULT_FILE.open(
        "w",
        encoding="utf-8",
    ) as file:
        for item in results:
            file.write(
                json.dumps(
                    item,
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

    write_skill_bad_cases(
        results
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