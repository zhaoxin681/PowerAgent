"""补充RAG评测样本所需的目标章节。"""

from __future__ import annotations

from pathlib import Path

from evaluation.dataset import (
    load_evaluation_cases,
    write_evaluation_cases,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]

CASE_FILE = (
    PROJECT_ROOT
    / "evaluation"
    / "test_cases.jsonl"
)


SECTION_EXPECTATIONS = {
    "RAG-001": [
        "典型现象",
    ],
    "RAG-002": [
        "定义",
        "适用边界",
    ],
    "RAG-003": [
        "可能原因",
    ],
    "RAG-004": [
        "所需数据",
        "验证步骤",
    ],
    "RAG-005": [
        "定义",
        "典型现象",
    ],
    "RAG-006": [
        "验证步骤",
        "处置建议",
    ],
    "RAG-007": [
        "可能原因",
    ],
    "RAG-008": [
        "处置建议",
        "适用边界",
    ],
    "RAG-009": [
        "验证步骤",
    ],
    "RAG-010": [
        "典型现象",
    ],
    "RAG-011": [
        "适用边界",
    ],
    "RAG-012": [
        "适用边界",
    ],
    "RAG-013": [
        "定义",
        "适用边界",
    ],
}


def main() -> None:
    """更新RAG样本章节期望。"""

    cases = load_evaluation_cases(
        CASE_FILE
    )

    updated_cases = []
    updated_count = 0

    for case in cases:
        expected_sections = (
            SECTION_EXPECTATIONS.get(
                case.case_id
            )
        )

        if expected_sections is None:
            updated_cases.append(case)
            continue

        if case.rag_expectation is None:
            raise ValueError(
                f"{case.case_id}"
                "缺少rag_expectation"
            )

        updated_expectation = (
            case.rag_expectation.model_copy(
                update={
                    "expected_source_keywords": (
                        expected_sections
                    ),
                }
            )
        )

        updated_case = case.model_copy(
            update={
                "rag_expectation": (
                    updated_expectation
                ),
            }
        )

        updated_cases.append(
            updated_case
        )

        updated_count += 1

    write_evaluation_cases(
        CASE_FILE,
        updated_cases,
    )

    print(
        f"已更新RAG样本：{updated_count}"
    )


if __name__ == "__main__":
    main()