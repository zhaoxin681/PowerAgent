"""校准Hash Embedding下的RAG检索参数。"""

from __future__ import annotations

import json
from pathlib import Path

from evaluation.dataset import (
    load_evaluation_cases,
)
from evaluation.evaluate_rag import (
    evaluate_retrieval,
    optional_rate,
    require_rag_expectation,
)
from evaluation.rag_fixture import (
    build_rag_evaluation_resources,
)
from evaluation.schemas import (
    EvaluatorType,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]

CASE_FILE = (
    PROJECT_ROOT
    / "evaluation"
    / "test_cases.jsonl"
)

OUTPUT_FILE = (
    PROJECT_ROOT
    / "evaluation"
    / "results"
    / "rag_retrieval_calibration.json"
)

MIN_SCORES = (
    0.00,
    0.05,
    0.10,
    0.15,
    0.20,
    0.25,
)

TOP_K_VALUES = (
    3,
    5,
)


def evaluate_configuration(
    *,
    cases,
    retriever,
    min_score: float,
    top_k: int,
) -> dict[str, object]:
    """评估一组检索参数。"""

    document_expected_total = 0
    document_hit = 0
    reciprocal_rank_sum = 0.0

    source_keyword_total = 0
    source_keyword_matched = 0

    retrieval_passed = 0
    empty_result_count = 0
    total_result_count = 0

    case_results = []

    for case in cases:
        expected = require_rag_expectation(
            case
        )

        results = retriever.retrieve(
            case.user_input,
            subsystem=(
                expected.retrieval_subsystem
            ),
            topic=expected.retrieval_topic,
            top_k=top_k,
            min_score=min_score,
        )

        if not results:
            empty_result_count += 1

        total_result_count += len(results)

        checks, counts = evaluate_retrieval(
            expected,
            results,
        )

        document_expected_total += int(
            counts["document_expected_total"]
        )
        document_hit += int(
            counts["document_hit"]
        )
        reciprocal_rank_sum += float(
            counts["reciprocal_rank_sum"]
        )
        source_keyword_total += int(
            counts["source_keyword_total"]
        )
        source_keyword_matched += int(
            counts["source_keyword_matched"]
        )
        retrieval_passed += int(
            counts["retrieval_passed"]
        )

        case_results.append(
            {
                "case_id": case.case_id,
                "retrieved": [
                    {
                        "document_id": (
                            item.document_id
                        ),
                        "section_path": (
                            item.section_path
                        ),
                        "score": round(
                            item.score,
                            4,
                        ),
                    }
                    for item in results
                ],
                "document_hit": (
                    checks[
                        "document_hit_at_k"
                    ]["passed"]
                ),
                "source_keywords_passed": (
                    checks[
                        "source_keywords"
                    ]["passed"]
                ),
                "retrieval_passed": (
                    checks[
                        "retrieval_overall"
                    ]["passed"]
                ),
            }
        )

    total_cases = len(cases)

    return {
        "min_score": min_score,
        "top_k": top_k,
        "document_hit_at_k": (
            optional_rate(
                document_hit,
                document_expected_total,
            )
        ),
        "mean_reciprocal_rank": (
            optional_rate(
                reciprocal_rank_sum,
                document_expected_total,
            )
        ),
        "source_keyword_accuracy": (
            optional_rate(
                source_keyword_matched,
                source_keyword_total,
            )
        ),
        "retrieval_case_pass_rate": (
            optional_rate(
                retrieval_passed,
                total_cases,
            )
        ),
        "empty_retrieval_rate": (
            optional_rate(
                empty_result_count,
                total_cases,
            )
        ),
        "average_result_count": round(
            total_result_count
            / total_cases,
            4,
        ),
        "cases": case_results,
    }


def main() -> None:
    """运行检索参数网格评测。"""

    cases = load_evaluation_cases(
        CASE_FILE,
        evaluator=EvaluatorType.RAG,
    )

    resources = (
        build_rag_evaluation_resources(
            reset=True
        )
    )

    configurations = []

    for top_k in TOP_K_VALUES:
        for min_score in MIN_SCORES:
            print(
                "正在评估："
                f"top_k={top_k}, "
                f"min_score={min_score:.2f}"
            )

            configurations.append(
                evaluate_configuration(
                    cases=cases,
                    retriever=(
                        resources.retriever
                    ),
                    min_score=min_score,
                    top_k=top_k,
                )
            )

    ranked = sorted(
        configurations,
        key=lambda item: (
            -float(
                item[
                    "retrieval_case_pass_rate"
                ]
                or 0.0
            ),
            -float(
                item[
                    "source_keyword_accuracy"
                ]
                or 0.0
            ),
            -float(
                item[
                    "document_hit_at_k"
                ]
                or 0.0
            ),
            float(
                item["average_result_count"]
            ),
            -float(
                item["min_score"]
            ),
        ),
    )

    output = {
        "best_configuration": ranked[0],
        "configurations": configurations,
    }

    OUTPUT_FILE.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    OUTPUT_FILE.write_text(
        json.dumps(
            output,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    best = ranked[0]

    print("\n最佳配置：")
    print(
        json.dumps(
            {
                key: value
                for key, value in best.items()
                if key != "cases"
            },
            ensure_ascii=False,
            indent=2,
        )
    )

    print(
        f"\n完整结果：{OUTPUT_FILE}"
    )


if __name__ == "__main__":
    main()