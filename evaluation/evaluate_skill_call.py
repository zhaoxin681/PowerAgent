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


DATASET_PATH = Path(
    "evaluation/skill_test_cases.jsonl"
)


def create_registry() -> SkillRegistry:
    """创建评测使用的默认Registry。"""

    registry = SkillRegistry()

    for skill in create_default_skills():
        registry.register(skill)

    return registry


def load_cases() -> list[dict[str, str]]:
    """读取JSONL评测案例。"""

    cases: list[dict[str, str]] = []

    with DATASET_PATH.open(
        "r",
        encoding="utf-8",
    ) as file:
        for line in file:
            if line.strip():
                cases.append(json.loads(line))

    return cases


def main() -> None:
    """执行真实API工具选择评测。"""

    runner = ToolCallingRunner(
        registry=create_registry(),
        client=LLMClient(),
    )

    cases = load_cases()

    successful_calls = 0
    correct_skill_calls = 0

    results: list[dict[str, object]] = []

    for case in cases:
        result = runner.run(case["user_input"])

        is_success = (
            result.status
            == ToolCallingStatus.SUCCESS
        )
        is_correct = (
            is_success
            and result.tool_name
            == case["expected_skill"]
        )

        successful_calls += int(is_success)
        correct_skill_calls += int(is_correct)

        results.append(
            {
                "case_id": case["case_id"],
                "expected_skill": (
                    case["expected_skill"]
                ),
                "actual_skill": result.tool_name,
                "status": result.status.value,
                "is_correct": is_correct,
                "error_code": result.error_code,
            }
        )

    total = len(cases)

    summary = {
        "total_cases": total,
        "successful_calls": successful_calls,
        "correct_skill_calls": (
            correct_skill_calls
        ),
        "valid_call_rate": (
            successful_calls / total
            if total
            else 0
        ),
        "skill_accuracy": (
            correct_skill_calls / total
            if total
            else 0
        ),
    }

    result_dir = Path("evaluation/results")
    result_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    result_file = (
        result_dir / "skill_eval_results.jsonl"
    )
    summary_file = (
        result_dir / "skill_eval_summary.json"
    )

    with result_file.open(
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

    summary_file.write_text(
        json.dumps(
            summary,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    print(
        json.dumps(
            summary,
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()