"""评测工具函数测试。"""

from evaluation.evaluate_issue_parser import (
    matches_concept_group,
    normalize_text,
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