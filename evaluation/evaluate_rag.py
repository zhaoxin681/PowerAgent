"""评估PowerAgent RAG检索和证据约束回答能力。"""

from __future__ import annotations

import argparse
import json
import re
import time
from pathlib import Path
from typing import Any

from agent_core.llm_client import LLMClient
from rag.rag_pipeline import RAGPipeline
from rag.retriever import Retriever
from rag.schemas import (
    RAGAnswer,
    RetrievedChunk,
)

from evaluation.dataset import (
    load_evaluation_cases,
)
from evaluation.rag_fixture import (
    build_rag_evaluation_resources,
)
from evaluation.schemas import (
    EvaluationCase,
    EvaluatorType,
    RAGExpectation,
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
    / "rag_eval_results.jsonl"
)

SUMMARY_FILE = (
    RESULTS_DIR
    / "rag_eval_summary.json"
)

BAD_CASE_FILE = (
    RESULTS_DIR
    / "rag_bad_cases.md"
)



class RecordingRetriever:
    """记录最近一次真实检索结果的评测包装器。"""

    def __init__(
        self,
        retriever: Retriever,
    ) -> None:
        self.retriever = retriever

        self.last_results: list[
            RetrievedChunk
        ] = []

    def retrieve(
        self,
        query: str,
        **kwargs: Any,
    ) -> list[RetrievedChunk]:
        """执行真实检索并保存结果。"""

        # 调用前先清空，防止异常时残留上一条结果。
        self.last_results = []

        results = self.retriever.retrieve(
            query,
            **kwargs,
        )

        self.last_results = list(results)
  
        return self.last_results
    

def safe_rate(
    numerator: int | float,
    denominator: int | float,
) -> float:
    """安全计算评测比例。"""

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
    """没有适用样本时返回None，而不是伪造100%。"""

    if denominator == 0:
        return None

    return round(
        numerator / denominator,
        4,
    )


def normalize_text(
    value: str,
) -> str:
    """统一用于概念和禁止结论检查的文本。"""

    return re.sub(
        r"[\s，。！？；：、,.!?;:'\"“”‘’（）()【】\[\]-]+",
        "",
        value.strip().lower(),
    )


def matches_concept_group(
    actual_text: str,
    alternatives: list[str],
) -> bool:
    """概念组中任意表达命中即通过。"""

    normalized_actual = normalize_text(
        actual_text
    )

    return any(
        normalize_text(alternative)
        in normalized_actual
        for alternative in alternatives
    )


def require_rag_expectation(
    case: EvaluationCase,
) -> RAGExpectation:
    """读取RAG期望并提供明确错误。"""

    expected = case.rag_expectation

    if expected is None:
        raise ValueError(
            f"样本{case.case_id}"
            "缺少rag_expectation"
        )

    return expected



def evaluate_retrieval(
    expected: RAGExpectation,
    retrieved_chunks: list[RetrievedChunk],
) -> tuple[
    dict[str, Any],
    dict[str, int | float],
]:
    """评估检索文档、Chunk、来源和排名。"""

    retrieved_document_ids = [
        chunk.document_id
        for chunk in retrieved_chunks
    ]

    retrieved_chunk_ids = [
        chunk.chunk_id
        for chunk in retrieved_chunks
    ]

    document_hit_applicable = bool(
        expected.expected_document_ids
    )

    document_hit = (
        any(
            document_id
            in expected.expected_document_ids
            for document_id
            in retrieved_document_ids
        )
        if document_hit_applicable
        else True
    )

    reciprocal_rank = 0.0

    if document_hit_applicable:
        for rank, document_id in enumerate(
            retrieved_document_ids,
            start=1,
        ):
            if (
                document_id
                in expected.expected_document_ids
            ):
                reciprocal_rank = 1.0 / rank
                break

    chunk_hit_applicable = bool(
        expected.expected_chunk_ids
    )

    chunk_hit = (
        any(
            chunk_id
            in expected.expected_chunk_ids
            for chunk_id in retrieved_chunk_ids
        )
        if chunk_hit_applicable
        else True
    )

    source_text = "\n".join(
        (
            f"{chunk.document_id}\n"
            f"{chunk.title}\n"
            f"{chunk.section_path}\n"
            f"{chunk.source_path}"
        )
        for chunk in retrieved_chunks
    )

    matched_source_keywords = [
        keyword
        for keyword
        in expected.expected_source_keywords
        if (
            normalize_text(keyword)
            in normalize_text(source_text)
        )
    ]

    source_keywords_passed = (
        len(matched_source_keywords)
        == len(
            expected.expected_source_keywords
        )
    )

    retrieval_passed = all(
        [
            document_hit,
            chunk_hit,
            source_keywords_passed,
        ]
    )

    checks = {
        "document_hit_at_k": {
            "passed": document_hit,
            "expected": (
                expected.expected_document_ids
            ),
            "actual": retrieved_document_ids,
        },
        "chunk_hit_at_k": {
            "passed": chunk_hit,
            "expected": (
                expected.expected_chunk_ids
            ),
            "actual": retrieved_chunk_ids,
            "applicable": (
                chunk_hit_applicable
            ),
        },
        "reciprocal_rank": {
            "passed": (
                reciprocal_rank > 0
                if document_hit_applicable
                else True
            ),
            "expected": (
                expected.expected_document_ids
            ),
            "actual": round(
                reciprocal_rank,
                4,
            ),
        },
        "source_keywords": {
            "passed": (
                source_keywords_passed
            ),
            "expected": (
                expected
                .expected_source_keywords
            ),
            "matched": (
                matched_source_keywords
            ),
        },
        "retrieval_overall": {
            "passed": retrieval_passed,
        },
    }

    counts: dict[str, int | float] = {
        "document_expected_total": int(
            document_hit_applicable
        ),
        "document_hit": int(
            document_hit_applicable
            and document_hit
        ),
        "reciprocal_rank_sum": (
            reciprocal_rank
        ),
        "chunk_expected_total": int(
            chunk_hit_applicable
        ),
        "chunk_hit": int(
            chunk_hit_applicable
            and chunk_hit
        ),
        "source_keyword_total": len(
            expected.expected_source_keywords
        ),
        "source_keyword_matched": len(
            matched_source_keywords
        ),
        "retrieval_passed": int(
            retrieval_passed
        ),
    }

    return checks, counts


def evaluate_citations(
    answer: RAGAnswer,
    retrieved_chunks: list[RetrievedChunk],
) -> tuple[
    bool,
    list[dict[str, Any]],
    int,
]:
    """检查引用是否来自本次Retriever结果。"""

    retrieved_by_id = {
        chunk.chunk_id: chunk
        for chunk in retrieved_chunks
    }

    citation_details: list[
        dict[str, Any]
    ] = []

    valid_count = 0

    for citation in answer.citations:
        source_chunk = retrieved_by_id.get(
            citation.chunk_id
        )

        valid = (
            source_chunk is not None
            and citation.document_id
            == source_chunk.document_id
            and citation.title
            == source_chunk.title
            and citation.section_path
            == source_chunk.section_path
        )

        if valid:
            valid_count += 1

        citation_details.append(
            {
                "chunk_id": (
                    citation.chunk_id
                ),
                "document_id": (
                    citation.document_id
                ),
                "valid": valid,
            }
        )

    all_valid = (
        valid_count
        == len(answer.citations)
    )

    return (
        all_valid,
        citation_details,
        valid_count,
    )


def evaluate_answer(
    expected: RAGExpectation,
    answer: RAGAnswer,
    retrieved_chunks: list[RetrievedChunk],
    *,
    original_question: str,
) -> tuple[
    dict[str, Any],
    dict[str, int | float],
]:
    """评估RAG回答、拒答、证据和安全边界。"""

    actual_refused = (
        not answer.sufficient_evidence
    )

    answer_mode_passed = (
        (
            expected.should_answer
            and not actual_refused
        )
        or (
            expected.should_refuse
            and actual_refused
        )
    )

    sufficient_evidence_passed = (
        answer.sufficient_evidence
        == expected.expected_sufficient_evidence
    )

    question_preserved = (
        answer.question
        == original_question
    )

    citation_count_passed = (
        len(answer.citations)
        >= expected.min_citation_count
    )

    (
        citations_valid,
        citation_details,
        valid_citation_count,
    ) = evaluate_citations(
        answer,
        retrieved_chunks,
    )

    citation_case_applicable = bool(
        answer.citations
    )

    answer_text = answer.answer

    concept_details: list[
        dict[str, Any]
    ] = []

    concept_matched = 0

    for alternatives in (
        expected.required_answer_concepts
    ):
        matched = matches_concept_group(
            answer_text,
            alternatives,
        )

        if matched:
            concept_matched += 1

        concept_details.append(
            {
                "alternatives": alternatives,
                "matched": matched,
            }
        )

    concept_total = len(
        expected.required_answer_concepts
    )

    concepts_passed = (
        concept_matched == concept_total
    )

    matched_forbidden_claims = [
        claim
        for claim in expected.forbidden_claims
        if (
            normalize_text(claim)
            in normalize_text(answer_text)
        )
    ]

    forbidden_claims_passed = (
        not matched_forbidden_claims
    )

    if (
        expected
        .expected_needs_human_review
        is None
    ):
        human_review_passed = True
        human_review_applicable = False
    else:
        human_review_passed = (
            answer.needs_human_review
            == expected
            .expected_needs_human_review
        )
        human_review_applicable = True

    answer_passed = all(
        [
            answer_mode_passed,
            sufficient_evidence_passed,
            question_preserved,
            citation_count_passed,
            citations_valid,
            concepts_passed,
            forbidden_claims_passed,
            human_review_passed,
        ]
    )

    checks = {
        "answer_mode": {
            "passed": answer_mode_passed,
            "expected": (
                "answer"
                if expected.should_answer
                else "refuse"
            ),
            "actual": (
                "refuse"
                if actual_refused
                else "answer"
            ),
        },
        "sufficient_evidence": {
            "passed": (
                sufficient_evidence_passed
            ),
            "expected": (
                expected
                .expected_sufficient_evidence
            ),
            "actual": (
                answer.sufficient_evidence
            ),
        },
        "question_preserved": {
            "passed": question_preserved,
            "expected": original_question,
            "actual": answer.question,
        },
        "citation_count": {
            "passed": (
                citation_count_passed
            ),
            "expected_minimum": (
                expected.min_citation_count
            ),
            "actual": len(
                answer.citations
            ),
        },
        "citation_validity": {
            "passed": citations_valid,
            "details": citation_details,
        },
        "answer_concepts": {
            "passed": concepts_passed,
            "matched": concept_matched,
            "total": concept_total,
            "details": concept_details,
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
        "human_review": {
            "passed": human_review_passed,
            "applicable": (
                human_review_applicable
            ),
            "expected": (
                expected
                .expected_needs_human_review
            ),
            "actual": (
                answer.needs_human_review
            ),
        },
        "answer_overall": {
            "passed": answer_passed,
        },
    }

    counts: dict[str, int | float] = {
        "answer_mode_correct": int(
            answer_mode_passed
        ),
        "sufficient_evidence_correct": int(
            sufficient_evidence_passed
        ),
        "question_preserved": int(
            question_preserved
        ),
        "citation_count_correct": int(
            citation_count_passed
        ),
        "citation_total": len(
            answer.citations
        ),
        "citation_valid": (
            valid_citation_count
        ),
        "citation_case_total": int(
            citation_case_applicable
        ),
        "citation_case_valid": int(
            citation_case_applicable
            and citations_valid
        ),
        "answer_concept_total": (
            concept_total
        ),
        "answer_concept_matched": (
            concept_matched
        ),
        "forbidden_claim_total": len(
            expected.forbidden_claims
        ),
        "forbidden_claim_absent": (
            len(expected.forbidden_claims)
            - len(matched_forbidden_claims)
        ),
        "human_review_total": int(
            human_review_applicable
        ),
        "human_review_correct": int(
            human_review_applicable
            and human_review_passed
        ),
        "answer_passed": int(
            answer_passed
        ),
    }

    return checks, counts


def evaluate_rag_case(
    case: EvaluationCase,
    *,
    pipeline: RAGPipeline,
    recording_retriever: RecordingRetriever,
) -> tuple[
    RAGAnswer,
    list[RetrievedChunk],
    dict[str, Any],
    dict[str, int | float],
]:
    """运行并评估一条RAG样本。"""

    expected = require_rag_expectation(
        case
    )

    answer = pipeline.answer(
        case.user_input,
        subsystem=(
            expected.retrieval_subsystem
        ),
        topic=expected.retrieval_topic,
        top_k=expected.top_k,
        min_score=expected.min_score,
    )

    retrieved_chunks = list(
        recording_retriever.last_results
    )

    retrieval_checks, retrieval_counts = (
        evaluate_retrieval(
            expected,
            retrieved_chunks,
        )
    )

    answer_checks, answer_counts = (
        evaluate_answer(
            expected,
            answer,
            retrieved_chunks,
            original_question=(
                case.user_input
            ),
        )
    )

    overall_passed = all(
        [
            retrieval_checks[
                "retrieval_overall"
            ]["passed"],
            answer_checks[
                "answer_overall"
            ]["passed"],
        ]
    )

    checks = {
        **retrieval_checks,
        **answer_checks,
        "overall": {
            "passed": overall_passed,
        },
    }

    counts = {
        **retrieval_counts,
        **answer_counts,
        "case_passed": int(
            overall_passed
        ),
    }

    return (
        answer,
        retrieved_chunks,
        checks,
        counts,
    )



def build_bad_case_markdown(
    results: list[dict[str, Any]],
) -> str:
    """生成RAG独立Bad Case报告。"""

    bad_results = [
        result
        for result in results
        if not result["passed"]
    ]

    lines = [
        "# RAG Bad Cases",
        "",
        "该文件由RAG自动评测脚本生成。",
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
                "### 用户问题",
                "",
                result["user_input"],
                "",
                "### 检索结果",
                "",
                "```json",
                json.dumps(
                    result["retrieved_chunks"],
                    ensure_ascii=False,
                    indent=2,
                ),
                "```",
                "",
                "### RAG回答",
                "",
                "```json",
                json.dumps(
                    result["answer"],
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
                "- 错误层级：检索 / 生成 / 引用 / 标注",
                "- 错误类型：",
                "- 可能原因：",
                "- 修复建议：",
                "- 回归状态：待修复",
                "",
                "### 自动分类",
                "",
                ", ".join(
                    result["failure_types"]
                ),
                "",
            ]
        )

    return "\n".join(lines)


def parse_arguments() -> argparse.Namespace:
    """解析命令行参数。"""

    parser = argparse.ArgumentParser(
        description=(
            "评估PowerAgent RAG检索和回答能力"
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
        help="只运行前N条RAG样本",
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
        help="两次真实LLM调用之间的等待时间",
    )

    return parser.parse_args()


def classify_rag_failure(
    *,
    error: str | None,
    retrieved_chunks: list[dict[str, Any]],
    checks: dict[str, Any],
) -> list[str]:
    """根据评测结果识别RAG失败类型。"""

    if error is not None:
        return [
            "PIPELINE_ERROR",
        ]

    failure_types: list[str] = []

    if not retrieved_chunks:
        failure_types.append(
            "NO_RETRIEVAL_RESULTS"
        )

        return failure_types

    if not checks[
        "document_hit_at_k"
    ]["passed"]:
        failure_types.append(
            "WRONG_DOCUMENT"
        )

    if not checks[
        "source_keywords"
    ]["passed"]:
        failure_types.append(
            "EVIDENCE_SECTION_MISS"
        )

    if not checks[
        "answer_mode"
    ]["passed"]:
        failure_types.append(
            "WRONG_ANSWER_MODE"
        )

    if not checks[
        "citation_count"
    ]["passed"]:
        failure_types.append(
            "INSUFFICIENT_CITATIONS"
        )

    if not checks[
        "citation_validity"
    ]["passed"]:
        failure_types.append(
            "INVALID_CITATION"
        )

    if not checks[
        "answer_concepts"
    ]["passed"]:
        failure_types.append(
            "ANSWER_CONCEPT_MISS"
        )

    if not checks[
        "forbidden_claims"
    ]["passed"]:
        failure_types.append(
            "UNSUPPORTED_CLAIM"
        )

    if not checks[
        "human_review"
    ]["passed"]:
        failure_types.append(
            "HUMAN_REVIEW_MISMATCH"
        )

    return failure_types


def main() -> None:
    """运行完整RAG自动评测。"""

    args = parse_arguments()

    cases = load_evaluation_cases(
        args.case_file,
        evaluator=EvaluatorType.RAG,
        case_ids=args.case_id,
        limit=args.limit,
    )

    if not cases:
        raise ValueError(
            "没有可运行的RAG评测样本。"
        )

    RESULTS_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    resources = (
        build_rag_evaluation_resources(
            reset=True
        )
    )

    recording_retriever = (
        RecordingRetriever(
            resources.retriever
        )
    )

    pipeline = RAGPipeline(
        retriever=recording_retriever,
        llm_client=LLMClient(),
    )

    results: list[
        dict[str, Any]
    ] = []

    aggregate: dict[
        str,
        int | float
    ] = {
        "total_cases": len(cases),
        "document_expected_total": 0,
        "document_hit": 0,
        "reciprocal_rank_sum": 0.0,
        "chunk_expected_total": 0,
        "chunk_hit": 0,
        "source_keyword_total": 0,
        "source_keyword_matched": 0,
        "retrieval_passed": 0,
        "answer_mode_correct": 0,
        "sufficient_evidence_correct": 0,
        "question_preserved": 0,
        "citation_count_correct": 0,
        "citation_total": 0,
        "citation_valid": 0,
        "citation_case_valid": 0,
        "answer_concept_total": 0,
        "answer_concept_matched": 0,
        "forbidden_claim_total": 0,
        "forbidden_claim_absent": 0,
        "human_review_total": 0,
        "human_review_correct": 0,
        "answer_passed": 0,
        "case_passed": 0,
        "pipeline_error_count": 0,
        "total_latency_seconds": 0.0,
        "citation_case_total": 0,
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
                answer,
                retrieved_chunks,
                checks,
                counts,
            ) = evaluate_rag_case(
                case,
                pipeline=pipeline,
                recording_retriever=(
                    recording_retriever
                ),
            )

            latency = (
                time.perf_counter()
                - start_time
            )

            failure_types = classify_rag_failure(
                error=None,
                retrieved_chunks=[
                    chunk.model_dump(
                        mode="json"
                    )
                    for chunk in retrieved_chunks
                ],
                checks=checks,
            )

            result = {
                "case_id": case.case_id,
                "user_input": (
                    case.user_input
                ),
                "passed": (
                    checks["overall"]["passed"]
                ),
                "latency_seconds": round(
                    latency,
                    4,
                ),
                "expected": (
                    require_rag_expectation(
                        case
                    ).model_dump(
                        mode="json"
                    )
                ),
                "retrieved_chunks": [
                    chunk.model_dump(
                        mode="json"
                    )
                    for chunk
                    in retrieved_chunks
                ],
                "answer": (
                    answer.model_dump(
                        mode="json"
                    )
                ),
                "checks": checks,
                "error": None,
                "failure_types": failure_types,
            }

            for key, value in counts.items():
                aggregate[key] += value

        except Exception as exc:
            latency = (
                time.perf_counter()
                - start_time
            )

            aggregate[
                "pipeline_error_count"
            ] += 1

            result = {
                "case_id": case.case_id,
                "user_input": (
                    case.user_input
                ),
                "passed": False,
                "latency_seconds": round(
                    latency,
                    4,
                ),
                "expected": (
                    require_rag_expectation(
                        case
                    ).model_dump(
                        mode="json"
                    )
                ),
                "retrieved_chunks": [
                    chunk.model_dump(
                        mode="json"
                    )
                    for chunk
                    in recording_retriever
                    .last_results
                ],
                "answer": None,
                "checks": {},
                "error": (
                    f"{type(exc).__name__}: "
                    f"{exc}"
                ),
                "failure_types": [
                    "PIPELINE_ERROR",
                ],
            }

        aggregate[
            "total_latency_seconds"
        ] += latency

        results.append(result)

        if (
            args.sleep > 0
            and index < len(cases)
        ):
            time.sleep(args.sleep)

    total = int(
        aggregate["total_cases"]
    )

    summary = {
        "total_cases": total,
        "document_hit_at_k": safe_rate(
            aggregate["document_hit"],
            aggregate[
                "document_expected_total"
            ],
        ),
        "mean_reciprocal_rank": safe_rate(
            aggregate[
                "reciprocal_rank_sum"
            ],
            aggregate[
                "document_expected_total"
            ],
        ),
        "chunk_hit_at_k": optional_rate(
            aggregate["chunk_hit"],
            aggregate["chunk_expected_total"],
        ),
        "source_keyword_accuracy": optional_rate(
            aggregate["source_keyword_matched"],
            aggregate["source_keyword_total"],
        ),
        "retrieval_case_pass_rate": (
            safe_rate(
                aggregate[
                    "retrieval_passed"
                ],
                total,
            )
        ),
        "answer_mode_accuracy": safe_rate(
            aggregate[
                "answer_mode_correct"
            ],
            total,
        ),
        "sufficient_evidence_accuracy": (
            safe_rate(
                aggregate[
                    "sufficient_evidence_correct"
                ],
                total,
            )
        ),
        "question_preservation_rate": (
            safe_rate(
                aggregate[
                    "question_preserved"
                ],
                total,
            )
        ),
        "citation_count_accuracy": (
            safe_rate(
                aggregate[
                    "citation_count_correct"
                ],
                total,
            )
        ),
        "citation_validity_rate": optional_rate(
            aggregate["citation_valid"],
            aggregate["citation_total"],
        ),
        "citation_case_validity_rate": (
            optional_rate(
                aggregate[
                    "citation_case_valid"
                ],
                aggregate[
                    "citation_case_total"
                ],
            )
        ),
        "answer_concept_coverage": (
            safe_rate(
                aggregate[
                    "answer_concept_matched"
                ],
                aggregate[
                    "answer_concept_total"
                ],
            )
        ),
        "forbidden_claim_avoidance_rate":  optional_rate(
            aggregate["forbidden_claim_absent"],
            aggregate["forbidden_claim_total"],
        ),
        "human_review_accuracy": optional_rate(
            aggregate["human_review_correct"],
            aggregate["human_review_total"],
        ),
        "answer_case_pass_rate": (
            safe_rate(
                aggregate["answer_passed"],
                total,
            )
        ),
        "overall_case_pass_rate": (
            safe_rate(
                aggregate["case_passed"],
                total,
            )
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
            4,
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

    print(f"\n详细结果：{RESULT_FILE}")
    print(f"汇总结果：{SUMMARY_FILE}")
    print(f"Bad Case：{BAD_CASE_FILE}")


if __name__ == "__main__":
    main()