"""构建PowerAgent统一评测看板与验收报告。
评测体系最终产出脚本：读取各模块EvaluationSummary JSON文件，计算综合评分"""

from __future__ import annotations

import argparse
import json
from datetime import (
    datetime,
    timezone,
)
from pathlib import Path
from typing import Any

from evaluation.benchmark_config import (
    CONDITIONAL_PASS_SCORE,
    MINIMUM_MODULE_SCORE,
    MODULE_CONFIGS,
    PASS_SCORE,
    QUALITY_GATES,
    SAFETY_GATES,
    GateRule,
    ModuleBenchmarkConfig,
    validate_benchmark_config,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]

RESULTS_DIR = (
    PROJECT_ROOT
    / "evaluation"
    / "results"
)

DEFAULT_DASHBOARD_FILE = (
    RESULTS_DIR
    / "evaluation_dashboard.json"
)

DEFAULT_REPORT_FILE = (
    RESULTS_DIR
    / "week7_acceptance_report.md"
)


def read_json_file(
    file_path: Path,
) -> dict[str, Any]:
    """读取并校验评测Summary文件。"""

    try:
        raw_data = file_path.read_text(
            encoding="utf-8"
        )

        parsed = json.loads(raw_data)

    except FileNotFoundError:
        raise
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"Summary不是合法JSON：{file_path}"
        ) from exc
    except OSError as exc:
        raise ValueError(
            f"读取Summary失败：{file_path}"
        ) from exc

    if not isinstance(parsed, dict):
        raise ValueError(
            f"Summary顶层必须是对象：{file_path}"
        )

    return parsed


def load_summaries(
    *,
    allow_missing: bool = False,
) -> tuple[
    dict[str, dict[str, Any]],
    list[str],
]:
    """加载全部可用评测Summary。"""

    summaries: dict[
        str,
        dict[str, Any]
    ] = {}

    missing_modules: list[str] = []

    for module_name, config in (
        MODULE_CONFIGS.items()
    ):
        if not config.summary_file.exists():
            missing_modules.append(
                module_name
            )

            if not allow_missing:
                raise FileNotFoundError(
                    "缺少评测Summary："
                    f"{config.summary_file}"
                )

            continue

        summaries[module_name] = (
            read_json_file(
                config.summary_file
            )
        )

    return summaries, missing_modules


def require_numeric_metric(
    *,
    summary: dict[str, Any],
    module_name: str,
    metric_name: str,
) -> float:
    """读取必须存在的数值指标。"""

    value = summary.get(metric_name)

    if (
        not isinstance(value, (int, float))
        or isinstance(value, bool)
    ):
        raise ValueError(
            f"模块{module_name}缺少有效指标"
            f"{metric_name}；actual={value!r}"
        )

    numeric_value = float(value)

    if not 0.0 <= numeric_value <= 1.0:
        raise ValueError(
            f"模块{module_name}指标"
            f"{metric_name}必须位于0到1；"
            f"actual={numeric_value}"
        )

    return numeric_value


def calculate_module_score(
    *,
    module_name: str,
    config: ModuleBenchmarkConfig,
    summary: dict[str, Any],
) -> dict[str, Any]:
    """根据配置计算单个模块得分。"""

    weighted_score = 0.0

    metric_details: list[
        dict[str, Any]
    ] = []

    for metric in config.metrics:
        value = require_numeric_metric(
            summary=summary,
            module_name=module_name,
            metric_name=metric.name,
        )

        contribution = (
            value * metric.weight
        )

        weighted_score += contribution

        metric_details.append(
            {
                "metric": metric.name,
                "value": value,
                "weight": metric.weight,
                "contribution": round(
                    contribution * 100,
                    4,
                ),
            }
        )

    return {
        "module": module_name,
        "label": config.label,
        "score": round(
            weighted_score * 100,
            2,
        ),
        "overall_weight": (
            config.overall_weight
        ),
        "total_cases": summary.get(
            "total_cases"
        ),
        "metrics": metric_details,
    }


def evaluate_gate(
    gate: GateRule,
    summaries: dict[
        str,
        dict[str, Any]
    ],
) -> dict[str, Any]:
    """评估一条安全或质量门槛。"""

    summary = summaries.get(
        gate.module
    )

    if summary is None:
        return {
            "gate_id": gate.gate_id,
            "level": gate.level,
            "module": gate.module,
            "metric": gate.metric,
            "operator": gate.operator,
            "threshold": gate.threshold,
            "actual": None,
            "passed": False,
            "evaluated": False,
            "description": gate.description,
            "reason": "缺少模块Summary",
        }

    value = summary.get(gate.metric)

    if (
        not isinstance(value, (int, float))
        or isinstance(value, bool)
    ):
        return {
            "gate_id": gate.gate_id,
            "level": gate.level,
            "module": gate.module,
            "metric": gate.metric,
            "operator": gate.operator,
            "threshold": gate.threshold,
            "actual": value,
            "passed": False,
            "evaluated": True,
            "description": gate.description,
            "reason": "指标不存在或不是数值",
        }

    actual = float(value)

    if gate.operator == "min":
        passed = actual >= gate.threshold

    elif gate.operator == "max":
        passed = actual <= gate.threshold

    else:
        raise ValueError(
            f"未知门槛运算符："
            f"{gate.operator}"
        )

    return {
        "gate_id": gate.gate_id,
        "level": gate.level,
        "module": gate.module,
        "metric": gate.metric,
        "operator": gate.operator,
        "threshold": gate.threshold,
        "actual": actual,
        "passed": passed,
        "evaluated": True,
        "description": gate.description,
        "reason": None,
    }


def determine_acceptance_status(
    *,
    overall_score: float,
    module_scores: dict[str, float],
    safety_gate_passed: bool,
    quality_gate_passed: bool,
    missing_modules: list[str],
) -> str:
    """根据总分和门槛确定最终验收状态。"""

    if missing_modules:
        return "incomplete"

    if (
        not safety_gate_passed
        or overall_score
        < CONDITIONAL_PASS_SCORE
    ):
        return "fail"

    all_modules_passed = all(
        score >= MINIMUM_MODULE_SCORE
        for score in module_scores.values()
    )

    if (
        overall_score >= PASS_SCORE
        and quality_gate_passed
        and all_modules_passed
    ):
        return "pass"

    return "conditional_pass"


def build_dashboard_from_summaries(
    summaries: dict[
        str,
        dict[str, Any]
    ],
    *,
    missing_modules: list[str] | None = None,
) -> dict[str, Any]:
    """根据已加载Summary构建统一看板。"""

    validate_benchmark_config()

    missing = list(
        missing_modules or []
    )

    module_results: dict[
        str,
        dict[str, Any]
    ] = {}

    module_scores: dict[
        str,
        float
    ] = {}

    weighted_score_sum = 0.0
    available_weight_sum = 0.0

    total_cases = 0

    for module_name, config in (
        MODULE_CONFIGS.items()
    ):
        summary = summaries.get(
            module_name
        )

        if summary is None:
            continue

        module_result = calculate_module_score(
            module_name=module_name,
            config=config,
            summary=summary,
        )

        module_results[module_name] = (
            module_result
        )

        module_score = float(
            module_result["score"]
        )

        module_scores[module_name] = (
            module_score
        )

        weighted_score_sum += (
            module_score
            * config.overall_weight
        )

        available_weight_sum += (
            config.overall_weight
        )

        case_count = summary.get(
            "total_cases",
            0,
        )

        if isinstance(case_count, int):
            total_cases += case_count

    if available_weight_sum == 0:
        raise ValueError(
            "没有可用于生成看板的评测Summary"
        )

    overall_score = round(
        weighted_score_sum
        / available_weight_sum,
        2,
    )

    safety_gate_results = [
        evaluate_gate(
            gate,
            summaries,
        )
        for gate in SAFETY_GATES
    ]

    quality_gate_results = [
        evaluate_gate(
            gate,
            summaries,
        )
        for gate in QUALITY_GATES
    ]

    safety_gate_passed = (
        not missing
        and all(
            result["passed"]
            for result
            in safety_gate_results
        )
    )

    quality_gate_passed = (
        not missing
        and all(
            result["passed"]
            for result
            in quality_gate_results
        )
    )

    status = determine_acceptance_status(
        overall_score=overall_score,
        module_scores=module_scores,
        safety_gate_passed=(
            safety_gate_passed
        ),
        quality_gate_passed=(
            quality_gate_passed
        ),
        missing_modules=missing,
    )

    blocking_issues = [
        result
        for result
        in safety_gate_results
        if not result["passed"]
    ]

    quality_issues = [
        result
        for result
        in quality_gate_results
        if not result["passed"]
    ]

    low_score_modules = [
        {
            "module": module_name,
            "score": score,
            "required": (
                MINIMUM_MODULE_SCORE
            ),
        }
        for module_name, score
        in module_scores.items()
        if score < MINIMUM_MODULE_SCORE
    ]

    return {
        "generated_at": (
            datetime.now(
                timezone.utc
            ).isoformat()
        ),
        "status": status,
        "overall_score": overall_score,
        "total_cases": total_cases,
        "available_weight": round(
            available_weight_sum,
            4,
        ),
        "missing_modules": missing,
        "module_scores": (
            module_scores
        ),
        "module_results": (
            module_results
        ),
        "safety_gate_passed": (
            safety_gate_passed
        ),
        "quality_gate_passed": (
            quality_gate_passed
        ),
        "safety_gates": (
            safety_gate_results
        ),
        "quality_gates": (
            quality_gate_results
        ),
        "blocking_issues": (
            blocking_issues
        ),
        "quality_issues": (
            quality_issues
        ),
        "low_score_modules": (
            low_score_modules
        ),
        "thresholds": {
            "pass_score": PASS_SCORE,
            "conditional_pass_score": (
                CONDITIONAL_PASS_SCORE
            ),
            "minimum_module_score": (
                MINIMUM_MODULE_SCORE
            ),
        },
    }


def format_percent(
    value: float | int | None,
) -> str:
    """将0到1指标转换成百分比文本。"""

    if value is None:
        return "N/A"

    return f"{float(value) * 100:.2f}%"


def build_acceptance_markdown(
    dashboard: dict[str, Any],
) -> str:
    """生成统一评测验收报告。"""

    status_mapping = {
        "pass": "PASS",
        "conditional_pass": (
            "CONDITIONAL PASS"
        ),
        "fail": "FAIL",
        "incomplete": "INCOMPLETE",
    }

    status_text = status_mapping[
        dashboard["status"]
    ]

    lines = [
        "# PowerAgent统一评测验收报告",
        "",
        "## 一、验收概览",
        "",
        f"- 验收状态：**{status_text}**",
        (
            f"- 加权总分："
            f"**{dashboard['overall_score']:.2f} / 100**"
        ),
        (
            f"- 评测样本总数："
            f"**{dashboard['total_cases']}**"
        ),
        (
            "- 安全硬门槛："
            + (
                "**通过**"
                if dashboard[
                    "safety_gate_passed"
                ]
                else "**未通过**"
            )
        ),
        (
            "- 质量门槛："
            + (
                "**通过**"
                if dashboard[
                    "quality_gate_passed"
                ]
                else "**部分未通过**"
            )
        ),
        "",
        "## 二、模块评分",
        "",
        "| 模块 | 得分 | 权重 | 样本数 |",
        "|---|---:|---:|---:|",
    ]

    for module_name, result in (
        dashboard["module_results"].items()
    ):
        lines.append(
            "| "
            f"{result['label']} | "
            f"{result['score']:.2f} | "
            f"{result['overall_weight'] * 100:.0f}% | "
            f"{result['total_cases']} |"
        )

    lines.extend(
        [
            "",
            "## 三、安全硬门槛",
            "",
            (
                "| 门槛 | 模块 | 指标 | "
                "实际值 | 要求 | 结果 |"
            ),
            "|---|---|---|---:|---:|---|",
        ]
    )

    for gate in dashboard["safety_gates"]:
        operator_text = (
            "≥"
            if gate["operator"] == "min"
            else "≤"
        )

        lines.append(
            "| "
            f"{gate['description']} | "
            f"{gate['module']} | "
            f"{gate['metric']} | "
            f"{format_percent(gate['actual'])} | "
            f"{operator_text}"
            f"{format_percent(gate['threshold'])} | "
            + (
                "通过 |"
                if gate["passed"]
                else "未通过 |"
            )
        )

    lines.extend(
        [
            "",
            "## 四、质量门槛",
            "",
            (
                "| 门槛 | 模块 | 指标 | "
                "实际值 | 要求 | 结果 |"
            ),
            "|---|---|---|---:|---:|---|",
        ]
    )

    for gate in dashboard["quality_gates"]:
        operator_text = (
            "≥"
            if gate["operator"] == "min"
            else "≤"
        )

        lines.append(
            "| "
            f"{gate['description']} | "
            f"{gate['module']} | "
            f"{gate['metric']} | "
            f"{format_percent(gate['actual'])} | "
            f"{operator_text}"
            f"{format_percent(gate['threshold'])} | "
            + (
                "通过 |"
                if gate["passed"]
                else "未通过 |"
            )
        )

    lines.extend(
        [
            "",
            "## 五、当前优势",
            "",
        ]
    )

    passed_modules = [
        (
            module_name,
            score,
        )
        for module_name, score
        in dashboard["module_scores"].items()
        if score >= 95.0
    ]

    if passed_modules:
        for module_name, score in (
            passed_modules
        ):
            lines.append(
                f"- {module_name}模块得分"
                f"{score:.2f}，"
                "核心状态和字段契约表现稳定。"
            )
    else:
        lines.append(
            "- 暂无得分达到95分的模块。"
        )

    lines.extend(
        [
            "",
            "## 六、主要改进项",
            "",
        ]
    )

    quality_issues = dashboard[
        "quality_issues"
    ]

    if quality_issues:
        for issue in quality_issues:
            lines.append(
                f"- `{issue['module']}` 的"
                f"`{issue['metric']}`"
                f"为{format_percent(issue['actual'])}，"
                "要求"
                f"{format_percent(issue['threshold'])}。"
            )
    else:
        lines.append(
            "- 当前质量门槛全部通过。"
        )

    lines.extend(
        [
            "",
            "## 七、验收结论",
            "",
        ]
    )

    if dashboard["status"] == "pass":
        lines.append(
            "第七周统一评测体系已达到正式验收标准。"
            "各核心模块得分、端到端质量指标和"
            "安全硬门槛均满足要求。"
        )

    elif (
        dashboard["status"]
        == "conditional_pass"
    ):
        lines.append(
            "第七周统一评测体系已完成工程闭环，"
            "安全硬门槛全部通过，"
            "但部分端到端质量指标仍低于目标值。"
            "当前可判定为有条件通过，"
            "后续应优先修复Parser字段完整性"
            "和RAG证据章节召回及回答概念覆盖。"
        )

    elif dashboard["status"] == "fail":
        lines.append(
            "当前评测结果未达到验收标准。"
            "需要优先处理安全阻断项或"
            "总分不足问题后重新执行完整评测。"
        )

    else:
        lines.append(
            "当前缺少部分模块Summary，"
            "无法完成正式验收。"
        )

    lines.extend(
        [
            "",
            "## 八、简历项目描述",
            "",
            (
                "构建面向动力系统多Agent工作流的"
                "统一评测与可靠性治理体系，"
                "覆盖结构化问题解析、确定性路由、"
                "LLM Tool Calling、RAG证据链、"
                "结果审核与结构化报告生成，"
                "通过模块加权评分、安全硬门槛、"
                "Bad Case归因和自动化验收报告，"
                "实现多Agent系统从功能开发到"
                "可量化质量验证的工程闭环。"
            ),
            "",
        ]
    )

    return "\n".join(lines)


def parse_arguments() -> argparse.Namespace:
    """解析命令行参数。"""

    parser = argparse.ArgumentParser(
        description=(
            "构建PowerAgent统一评测看板"
        ),
    )

    parser.add_argument(
        "--dashboard-file",
        type=Path,
        default=DEFAULT_DASHBOARD_FILE,
        help="JSON看板输出路径",
    )

    parser.add_argument(
        "--report-file",
        type=Path,
        default=DEFAULT_REPORT_FILE,
        help="Markdown验收报告输出路径",
    )

    parser.add_argument(
        "--allow-missing",
        action="store_true",
        help=(
            "允许缺少部分Summary，"
            "此时状态为incomplete"
        ),
    )

    return parser.parse_args()


def main() -> None:
    """读取Summary并生成统一看板。"""

    args = parse_arguments()

    summaries, missing_modules = (
        load_summaries(
            allow_missing=(
                args.allow_missing
            )
        )
    )

    dashboard = (
        build_dashboard_from_summaries(
            summaries,
            missing_modules=missing_modules,
        )
    )

    args.dashboard_file.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    args.dashboard_file.write_text(
        json.dumps(
            dashboard,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    report_content = (
        build_acceptance_markdown(
            dashboard
        )
    )

    args.report_file.write_text(
        report_content,
        encoding="utf-8",
    )

    print("=" * 72)
    print("PowerAgent统一评测看板生成完成")
    print("=" * 72)
    print(
        f"验收状态："
        f"{dashboard['status']}"
    )
    print(
        f"加权总分："
        f"{dashboard['overall_score']:.2f}"
    )
    print(
        f"评测样本数："
        f"{dashboard['total_cases']}"
    )
    print(
        f"安全硬门槛："
        f"{dashboard['safety_gate_passed']}"
    )
    print(
        f"质量门槛："
        f"{dashboard['quality_gate_passed']}"
    )
    print(
        f"JSON看板："
        f"{args.dashboard_file}"
    )
    print(
        f"验收报告："
        f"{args.report_file}"
    )


if __name__ == "__main__":
    main()