"""PowerAgent统一评测数据集读写工具。负责把测试样本以JSONL格式读写到磁盘"""

from __future__ import annotations

import json
from collections.abc import Iterable
from pathlib import Path

from pydantic import ValidationError

from evaluation.schemas import (
    EvaluationCase,
    EvaluatorType,
)


# 读取、校验、筛选评测数据
def load_evaluation_cases(
    path: Path,
    *,
    evaluator: EvaluatorType | None = None,  # 指定评测器样本
    case_ids: Iterable[str] | None = None,   # 指定ID样本
    limit: int | None = None,   # 最多返回多少条
) -> list[EvaluationCase]:
    """读取、校验并筛选统一JSONL评测数据。"""

    # 参数合法性前置检查
    if limit is not None and limit <= 0:
        raise ValueError("limit必须大于0")

    requested_ids = set(case_ids or [])

    all_cases: list[EvaluationCase] = []
    seen_ids: set[str] = set()

    # 打开文件（区分“文件打不开”和“内容有问题”两类错误）
    try:
        file = path.open("r", encoding="utf-8")
    except OSError as exc:
        raise ValueError(
            f"无法读取评测数据集：{path}"
        ) from exc
    # 逐行解析JSONL 
    with file:
        for line_number, line in enumerate(
            file,
            start=1,
        ):
            stripped_line = line.strip()

            if not stripped_line:
                continue
            # JSON解析
            try:
                raw_case = json.loads(stripped_line)
            except json.JSONDecodeError as exc:
                raise ValueError(
                    f"评测数据第{line_number}行"
                    f"不是合法JSON：{exc}"
                ) from exc
            # Schema校验
            try:
                case = EvaluationCase.model_validate(
                    raw_case
                )
            except ValidationError as exc:
                raise ValueError(
                    f"评测数据第{line_number}行"
                    f"未通过Schema校验：{exc}"
                ) from exc
            # 重复ID检测
            if case.case_id in seen_ids:
                raise ValueError(
                    f"发现重复case_id：{case.case_id}"
                )

            seen_ids.add(case.case_id)
            all_cases.append(case)

    # 校验“指定要找的case_id是否都存在”
    if requested_ids:
        available_ids = {
            case.case_id
            for case in all_cases
        }

        missing_ids = (
            requested_ids - available_ids
        )

        if missing_ids:
            missing_text = ", ".join(
                sorted(missing_ids)
            )

            raise ValueError(
                f"未找到指定测试样本：{missing_text}"
            )

    # 组合筛选条件
    selected_cases = [
        case
        for case in all_cases
        if (
            evaluator is None
            or evaluator in case.evaluators
        )
        and (
            not requested_ids
            or case.case_id in requested_ids
        )
    ]

    # 应用数量上限
    if limit is not None:
        selected_cases = selected_cases[:limit]

    return selected_cases


# 检验并原子写入
def write_evaluation_cases(
    path: Path,
    cases: Iterable[EvaluationCase],
) -> None:
    """校验并以原子写入方式保存统一JSONL数据。"""

    # 先做全量校验，再落盘
    validated_cases: list[EvaluationCase] = []
    seen_ids: set[str] = set()

    for case in cases:
        validated = EvaluationCase.model_validate(
            case
        )

        if validated.case_id in seen_ids:
            raise ValueError(
                "写入数据中存在重复case_id："
                f"{validated.case_id}"
            )

        seen_ids.add(validated.case_id)
        validated_cases.append(validated)

    # 确保目录存在
    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    # 原子写入模式（先写临时文件，再原子替换）
    temporary_path = path.with_suffix(
        path.suffix + ".tmp"
    )

    try:
        with temporary_path.open(
            "w",
            encoding="utf-8",
        ) as file:
            for case in validated_cases:
                payload = case.model_dump(
                    mode="json",
                    exclude_none=True,
                )

                file.write(
                    json.dumps(
                        payload,
                        ensure_ascii=False,
                        separators=(",", ":"),
                    )
                    + "\n"
                )

        temporary_path.replace(path)

    except OSError as exc:
        if temporary_path.exists():
            temporary_path.unlink()

        raise ValueError(
            f"无法写入评测数据集：{path}"
        ) from exc