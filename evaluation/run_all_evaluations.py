"""一键运行PowerAgent全部评测并生成统一看板。
编排器：按照顺序调用各个模块的独立评测脚本，再调用看板生成代码，
最后把整次运行的执行情况记录成一份运行清单。是整套评测流水线
的总指挥。"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import (
    datetime,
    timezone,
)
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]

RESULTS_DIR = (
    PROJECT_ROOT
    / "evaluation"
    / "results"
)

RUN_MANIFEST_FILE = (
    RESULTS_DIR
    / "evaluation_run_manifest.json"
)


EVALUATION_COMMANDS: dict[
    str,
    str,
] = {
    "router": (
        "evaluation.evaluate_router"
    ),
    "report": (
        "evaluation.evaluate_report"
    ),
    "issue_parser": (
        "evaluation.evaluate_issue_parser"
    ),
    "skill_call": (
        "evaluation.evaluate_skill_call"
    ),
    "rag": (
        "evaluation.evaluate_rag"
    ),
}


EXECUTION_ORDER = (
    "router",
    "report",
    "issue_parser",
    "skill_call",
    "rag",
)  # 固定的执行顺序


ONLINE_MODULES = {
    "issue_parser",
    "skill_call",
    "rag",
}


# 执行单个子进行命令并计时
def run_command(
    command: list[str],
) -> dict[str, Any]:
    """同步执行一个评测命令。"""

    print("\n" + "=" * 72)
    print(
        "正在执行："
        + " ".join(command)
    )
    print("=" * 72)

    start_time = datetime.now(
        timezone.utc
    )

    completed = subprocess.run(
        command,
        cwd=PROJECT_ROOT,
        check=False,
    ) # 用标准库同步执行一条命令

    end_time = datetime.now(
        timezone.utc
    )

    return {
        "command": command,
        "return_code": (
            completed.returncode
        ),
        "success": (
            completed.returncode == 0
        ),
        "started_at": (
            start_time.isoformat()
        ),
        "finished_at": (
            end_time.isoformat()
        ),
        "duration_seconds": round(
            (
                end_time
                - start_time
            ).total_seconds(),
            4,
        ),
    }


# 构造单个模块的完整命令
def build_module_command(
    *,
    module_name: str,
    sleep_seconds: float,
) -> list[str]:
    """构造单个评测模块命令。"""

    module_path = (
        EVALUATION_COMMANDS[
            module_name
        ]
    )

    command = [
        sys.executable,
        "-m",
        module_path,
    ]

    if module_name in ONLINE_MODULES:
        command.extend(
            [
                "--sleep",
                str(sleep_seconds),
            ]
        )

    return command


def select_modules(
    *,
    offline_only: bool,
    skip_rag: bool,
) -> list[str]:
    """根据命令行参数选择评测模块。"""

    if offline_only:
        return [
            module_name
            for module_name
            in EXECUTION_ORDER
            if module_name
            not in ONLINE_MODULES
        ]

    selected = list(
        EXECUTION_ORDER
    )

    if skip_rag:
        selected = [
            module_name
            for module_name
            in selected
            if module_name != "rag"
        ]

    return selected


def parse_arguments() -> argparse.Namespace:
    """解析命令行参数。"""

    parser = argparse.ArgumentParser(
        description=(
            "一键执行PowerAgent全部评测"
        ),
    )

    parser.add_argument(
        "--offline-only",
        action="store_true",
        help=(
            "只重新运行Router和Report"
        ),
    )

    parser.add_argument(
        "--skip-rag",
        action="store_true",
        help="跳过RAG重新评测",
    )

    parser.add_argument(
        "--build-only",
        action="store_true",
        help=(
            "不运行模块评测，"
            "只读取现有Summary生成看板"
        ),
    )

    parser.add_argument(
        "--continue-on-error",
        action="store_true",
        help=(
            "某个评测失败后继续执行后续模块"
        ),
    )

    parser.add_argument(
        "--sleep",
        type=float,
        default=0.2,
        help=(
            "真实LLM评测调用之间的等待时间"
        ),
    )

    return parser.parse_args()


def main() -> None:
    """运行全部评测并生成看板。"""

    args = parse_arguments()

    RESULTS_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    run_started_at = datetime.now(
        timezone.utc
    )

    execution_results: list[
        dict[str, Any]
    ] = []

    selected_modules = select_modules(
        offline_only=args.offline_only,
        skip_rag=args.skip_rag,
    )

    if not args.build_only:
        for module_name in selected_modules:
            command = build_module_command(
                module_name=module_name,
                sleep_seconds=args.sleep,
            )

            result = run_command(
                command
            )

            result["module"] = (
                module_name
            )

            execution_results.append(
                result
            )

            if (
                not result["success"]
                and not args.continue_on_error
            ):
                print(
                    "\n评测执行失败，"
                    "已停止后续模块。"
                )
                break

    dashboard_command = [
        sys.executable,
        "-m",
        (
            "evaluation"
            ".build_evaluation_dashboard"
        ),
    ]

    if (
        args.offline_only
        or args.skip_rag
    ):
        dashboard_command.append(
            "--allow-missing"
        )

    dashboard_result = run_command(
        dashboard_command
    )

    dashboard_result["module"] = (
        "dashboard"
    )

    execution_results.append(
        dashboard_result
    )

    run_finished_at = datetime.now(
        timezone.utc
    )

    manifest = {
        "started_at": (
            run_started_at.isoformat()
        ),
        "finished_at": (
            run_finished_at.isoformat()
        ),
        "build_only": args.build_only,
        "offline_only": (
            args.offline_only
        ),
        "skip_rag": args.skip_rag,
        "continue_on_error": (
            args.continue_on_error
        ),
        "sleep_seconds": args.sleep,
        "selected_modules": (
            selected_modules
        ),
        "executions": (
            execution_results
        ),
        "success": all(
            result["success"]
            for result in execution_results
        ),
    }

    RUN_MANIFEST_FILE.write_text(
        json.dumps(
            manifest,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    print("\n" + "=" * 72)
    print("统一评测执行结束")
    print("=" * 72)
    print(
        f"运行清单："
        f"{RUN_MANIFEST_FILE}"
    )

    if not manifest["success"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()