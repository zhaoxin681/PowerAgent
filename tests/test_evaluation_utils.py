"""评测工具函数测试。"""

from evaluation.evaluate_issue_parser import (
    matches_concept_group,
    normalize_text,
)
import pytest
from pydantic import ValidationError

from agent_core.schemas import (
    Severity,
    Subsystem,
    TaskType,
)
from evaluation.schemas import (
    ConceptExpectation,
    EvaluationCase,
    EvaluatorType,
    IssueExpectation,
    SkillCallExpectation,
)
from pathlib import Path

from evaluation.dataset import (
    load_evaluation_cases,
    write_evaluation_cases,
)
from types import SimpleNamespace

from agent_core import ToolCallingStatus
from evaluation.evaluate_skill_call import (
    evaluate_argument_keys,
    evaluate_skill_result,
)


def test_normalize_text_removes_spaces_and_punctuation() -> None:
    actual = normalize_text("低 180 mV，压差扩大。")

    assert actual == "低180mv压差扩大"


def test_matches_concept_group_with_synonym() -> None:
    actual_text = "第36号单体的压差持续扩大"

    alternatives = [
        "压差扩大",
        "压差持续增大",
        "压差持续扩大",
    ]

    assert matches_concept_group(
        actual_text,
        alternatives,
    )


def test_matches_concept_group_returns_false() -> None:
    actual_text = "冷却液温度升高"

    alternatives = [
        "单体电压下降",
        "电压压差扩大",
    ]

    assert not matches_concept_group(
        actual_text,
        alternatives,
    )


def test_evaluation_case_supports_multiple_evaluators() -> None:
    """同一条样本应能够服务多个评测器。"""

    case = EvaluationCase(
        case_id="battery_001",
        user_input="请分析四个单体的电压一致性。",
        evaluators=[
            EvaluatorType.ISSUE_PARSER,
            EvaluatorType.SKILL_CALL,
        ],
        tags=[
            "battery",
            "data_analysis",
        ],
        issue_expectation=IssueExpectation(
            subsystem=Subsystem.BATTERY,
            task_type=TaskType.DATA_ANALYSIS,
            severity_allowed=[
                Severity.LOW,
                Severity.UNKNOWN,
            ],
            required_concepts=[
                ConceptExpectation(
                    field_name="requested_outputs",
                    alternatives=[
                        "电压一致性",
                        "压差分析",
                    ],
                )
            ],
            must_be_empty=[
                "user_hypotheses",
            ],
        ),
        skill_expectation=(
            SkillCallExpectation(
                should_call_tool=True,
                expected_skill="battery_analysis",
                expected_argument_keys=[
                    "cell_voltages_v",
                ],
                expected_status="success",
            )
        ),
    )

    assert case.case_id == "battery_001"

    assert case.evaluators == [
        EvaluatorType.ISSUE_PARSER,
        EvaluatorType.SKILL_CALL,
    ]


def test_concept_expectation_rejects_empty_text() -> None:
    """空字符串不能作为概念匹配占位符。"""

    with pytest.raises(
        ValidationError,
        match="alternatives不能包含空字符串",
    ):
        ConceptExpectation(
            field_name="requested_outputs",
            alternatives=[""],
        )


def test_evaluation_case_requires_matching_expectation() -> None:
    """声明评测器时必须提供对应期望结果。"""

    with pytest.raises(
        ValidationError,
        match="skill_call",
    ):
        EvaluationCase(
            case_id="invalid_001",
            user_input="请分析电池电压。",
            evaluators=[
                EvaluatorType.SKILL_CALL,
            ],
        )


def test_evaluation_dataset_round_trip(
    tmp_path: Path,
) -> None:
    """统一样本写入后应能完整读取。"""

    case = EvaluationCase(
        case_id="round_trip_001",
        user_input="SOC是什么意思？",
        evaluators=[
            EvaluatorType.SKILL_CALL,
        ],
        skill_expectation=(
            SkillCallExpectation(
                should_call_tool=True,
                expected_skill="knowledge_lookup",
                expected_argument_keys=["term"],
                expected_status="success",
            )
        ),
    )

    case_file = tmp_path / "cases.jsonl"

    write_evaluation_cases(
        case_file,
        [case],
    )

    loaded_cases = load_evaluation_cases(
        case_file
    )

    assert loaded_cases == [case]


def test_evaluation_dataset_filters_by_evaluator(
    tmp_path: Path,
) -> None:
    """加载器应支持按评测器筛选样本。"""

    parser_case = EvaluationCase(
        case_id="parser_001",
        user_input="什么是SOC？",
        evaluators=[
            EvaluatorType.ISSUE_PARSER,
        ],
        issue_expectation=IssueExpectation(
            subsystem=Subsystem.BATTERY,
            task_type=TaskType.KNOWLEDGE_QUERY,
            severity_allowed=[
                Severity.UNKNOWN,
                Severity.LOW,
            ],
        ),
    )

    skill_case = EvaluationCase(
        case_id="skill_001",
        user_input="SOC是什么意思？",
        evaluators=[
            EvaluatorType.SKILL_CALL,
        ],
        skill_expectation=(
            SkillCallExpectation(
                should_call_tool=True,
                expected_skill="knowledge_lookup",
                expected_argument_keys=["term"],
                expected_status="success",
            )
        ),
    )

    case_file = tmp_path / "cases.jsonl"

    write_evaluation_cases(
        case_file,
        [
            parser_case,
            skill_case,
        ],
    )

    selected = load_evaluation_cases(
        case_file,
        evaluator=EvaluatorType.SKILL_CALL,
    )

    assert [
        case.case_id
        for case in selected
    ] == ["skill_001"]


def test_evaluation_dataset_rejects_duplicate_ids(
    tmp_path: Path,
) -> None:
    """统一数据集不能包含重复case_id。"""

    case = EvaluationCase(
        case_id="duplicate_001",
        user_input="BMS是什么？",
        evaluators=[
            EvaluatorType.SKILL_CALL,
        ],
        skill_expectation=(
            SkillCallExpectation(
                should_call_tool=True,
                expected_skill="knowledge_lookup",
                expected_argument_keys=["term"],
                expected_status="success",
            )
        ),
    )

    case_file = tmp_path / "cases.jsonl"

    with pytest.raises(
        ValueError,
        match="重复case_id",
    ):
        write_evaluation_cases(
            case_file,
            [
                case,
                case,
            ],
        )


def test_evaluate_argument_keys_reports_missing_keys() -> None:
    """参数检查应返回缺失的必要字段。"""

    passed, missing = evaluate_argument_keys(
        {
            "cell_voltages_v": [
                3.61,
                3.59,
            ]
        },
        [
            "cell_voltages_v",
            "warning_threshold_v",
        ],
    )

    assert not passed

    assert missing == [
        "warning_threshold_v",
    ]



def test_evaluate_skill_result_checks_arguments() -> None:
    """Skill评测应同时检查名称、状态和参数。"""

    case = EvaluationCase(
        case_id="skill_eval_001",
        user_input="分析单体电压。",
        evaluators=[
            EvaluatorType.SKILL_CALL,
        ],
        skill_expectation=(
            SkillCallExpectation(
                should_call_tool=True,
                expected_skill="battery_analysis",
                expected_argument_keys=[
                    "cell_voltages_v",
                ],
                expected_status="success",
            )
        ),
    )

    result = SimpleNamespace(
        status=ToolCallingStatus.SUCCESS,
        tool_name="battery_analysis",
        arguments={
            "cell_voltages_v": [
                3.61,
                3.59,
            ]
        },
        error_code=None,
        error_message=None,
    )

    checks, counts = evaluate_skill_result(
        case,
        result,
    )

    assert checks["overall"]["passed"]

    assert counts["skill_correct"] == 1

    assert (
        counts["required_argument_correct"]
        == 1
    )


def test_evaluate_skill_result_fails_when_argument_missing() -> None:
    """缺少必要参数时样本不能整体通过。"""

    case = EvaluationCase(
        case_id="skill_eval_002",
        user_input="分析电池电压。",
        evaluators=[
            EvaluatorType.SKILL_CALL,
        ],
        skill_expectation=(
            SkillCallExpectation(
                should_call_tool=True,
                expected_skill="battery_analysis",
                expected_argument_keys=[
                    "cell_voltages_v",
                ],
                expected_status="success",
            )
        ),
    )

    result = SimpleNamespace(
        status=ToolCallingStatus.SUCCESS,
        tool_name="battery_analysis",
        arguments={},
        error_code=None,
        error_message=None,
    )

    checks, _ = evaluate_skill_result(
        case,
        result,
    )

    assert not checks[
        "required_arguments"
    ]["passed"]

    assert not checks["overall"]["passed"]