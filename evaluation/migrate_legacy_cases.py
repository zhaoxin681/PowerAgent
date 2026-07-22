"""将旧评测数据(Parser测试集、Skill测试集)迁移为统一格式。"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from evaluation.dataset import (
    write_evaluation_cases,
)
from evaluation.schemas import (
    ConceptExpectation,
    EvaluationCase,
    EvaluatorType,
    IssueExpectation,
    SkillCallExpectation,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]

PARSER_CASE_FILE = (
    PROJECT_ROOT
    / "evaluation"
    / "parser_test_cases.jsonl"
)

SKILL_CASE_FILE = (
    PROJECT_ROOT
    / "evaluation"
    / "skill_test_cases.jsonl"
)

OUTPUT_FILE = (
    PROJECT_ROOT
    / "evaluation"
    / "test_cases.jsonl"
)


def load_legacy_jsonl(
    path: Path,
) -> list[dict[str, Any]]:
    """读取旧版JSONL数据。"""

    cases: list[dict[str, Any]] = []

    with path.open("r", encoding="utf-8") as file:
        for line_number, line in enumerate(
            file,
            start=1,
        ):
            stripped_line = line.strip()

            if not stripped_line:
                continue

            try:
                cases.append(
                    json.loads(stripped_line)
                )
            except json.JSONDecodeError as exc:
                raise ValueError(
                    f"{path.name}第{line_number}行"
                    f"不是合法JSON：{exc}"
                ) from exc

    return cases


def clean_alternatives(
    alternatives: list[str],
) -> list[str]:
    """清理空字符串并保持同义表达顺序。"""

    cleaned: list[str] = []

    for item in alternatives:
        stripped_item = item.strip()

        if (
            stripped_item
            and stripped_item not in cleaned
        ):
            cleaned.append(stripped_item)

    return cleaned

def unique_strings(
    values: list[str],
) -> list[str]:
    """去除重复字符串，同时保持原有顺序。"""

    unique_values: list[str] = []

    for value in values:
        cleaned_value = value.strip()

        if (
            cleaned_value
            and cleaned_value not in unique_values
        ):
            unique_values.append(cleaned_value)

    return unique_values


def convert_parser_case(
    legacy_case: dict[str, Any],
) -> EvaluationCase:
    """将一条旧Parser样本转换为统一样本。"""

    expected = legacy_case["expected"]

    concepts: list[
        ConceptExpectation
    ] = []

    for (
        field_name,
        concept_groups,
    ) in expected.get(
        "required_concepts",
        {},
    ).items():
        for alternatives in concept_groups:
            cleaned = clean_alternatives(
                alternatives
            )

            # 旧数据中的[""]不具备评测意义，
            # 清理后为空的概念组直接删除。
            if not cleaned:
                continue

            concepts.append(
                ConceptExpectation(
                    field_name=field_name,
                    alternatives=cleaned,
                )
            )

    return EvaluationCase(
        case_id=legacy_case["id"],
        user_input=legacy_case["input"],
        evaluators=[
            EvaluatorType.ISSUE_PARSER,
        ],
        tags=unique_strings(
            [
                expected["subsystem"],
                expected["task_type"],
                "legacy_parser",
            ]
        ),
        issue_expectation=IssueExpectation(
            subsystem=expected["subsystem"],
            task_type=expected["task_type"],
            severity_allowed=(
                expected["severity_allowed"]
            ),
            required_concepts=concepts,
            must_be_empty=expected.get(
                "must_be_empty",
                [],
            ),
            exact_raw_text=True,
        ),
        notes="由第一周Parser测试集迁移。",
    )


def convert_skill_case(
    legacy_case: dict[str, Any],
) -> EvaluationCase:
    """将一条旧Skill样本转换为统一样本。"""

    return EvaluationCase(
        case_id=legacy_case["case_id"],
        user_input=legacy_case["user_input"],
        evaluators=[
            EvaluatorType.SKILL_CALL,
        ],
        tags=unique_strings(
            [
                legacy_case["expected_skill"],
                "legacy_skill",
            ]
        ),
        skill_expectation=(
            SkillCallExpectation(
                should_call_tool=True,
                expected_skill=(
                    legacy_case[
                        "expected_skill"
                    ]
                ),
                expected_argument_keys=(
                    legacy_case.get(
                        "expected_argument_keys",
                        [],
                    )
                ),
                expected_status=(
                    legacy_case[
                        "expected_status"
                    ]
                ),
            )
        ),
        notes=legacy_case.get(
            "notes",
            "由第二周Skill测试集迁移。",
        ),
    )


def main() -> None:
    """执行旧数据迁移。"""

    parser_cases = [
        convert_parser_case(case)
        for case in load_legacy_jsonl(
            PARSER_CASE_FILE
        )
    ]

    skill_cases = [
        convert_skill_case(case)
        for case in load_legacy_jsonl(
            SKILL_CASE_FILE
        )
    ]

    all_cases = [
        *parser_cases,
        *skill_cases,
    ]

    write_evaluation_cases(
        OUTPUT_FILE,
        all_cases,
    )

    print(
        f"Parser样本：{len(parser_cases)}"
    )
    print(
        f"Skill样本：{len(skill_cases)}"
    )
    print(
        f"统一样本总数：{len(all_cases)}"
    )
    print(
        f"输出文件：{OUTPUT_FILE}"
    )


if __name__ == "__main__":
    main()