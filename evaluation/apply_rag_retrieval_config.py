"""向现有RAG样本应用校准后的检索配置。"""

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

CALIBRATED_TOP_K = 5
CALIBRATED_MIN_SCORE = 0.10


def main() -> None:
    """更新全部RAG评测样本的检索参数。"""

    cases = load_evaluation_cases(
        CASE_FILE
    )

    updated_cases = []

    for case in cases:
        if case.rag_expectation is None:
            updated_cases.append(case)
            continue

        expectation = (
            case.rag_expectation.model_copy(
                update={
                    "top_k": (
                        CALIBRATED_TOP_K
                    ),
                    "min_score": (
                        CALIBRATED_MIN_SCORE
                    ),
                }
            )
        )

        updated_cases.append(
            case.model_copy(
                update={
                    "rag_expectation": (
                        expectation
                    ),
                }
            )
        )

    write_evaluation_cases(
        CASE_FILE,
        updated_cases,
    )


if __name__ == "__main__":
    main()