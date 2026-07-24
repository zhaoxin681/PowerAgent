"""PowerAgent API外部HTTP Smoke Test。"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any
from uuid import uuid4

import httpx

from examples.api_client_demo import (
    DEFAULT_BASE_URL,
    DEFAULT_TIMEOUT_SECONDS,
    ApiClientResult,
    PowerAgentApiClient,
)


class SmokeTestFailure(RuntimeError):
    """Smoke Test核心步骤未通过。"""


def require_status(
    result: ApiClientResult,
    *,
    step: str,
    expected_status: int,
) -> None:
    """检查步骤返回的HTTP状态。"""

    print(
        f"[{step}] "
        f"HTTP {result.status_code} | "
        f"request_id={result.request_id or '-'} | "
        f"trace_id={result.trace_id or '-'}"
    )

    if (
        result.status_code
        != expected_status
    ):
        raise SmokeTestFailure(
            f"{step}预期HTTP "
            f"{expected_status}，"
            f"实际为{result.status_code}；"
            f"响应：{result.payload}"
        )


def require_api_success(
    result: ApiClientResult,
    *,
    step: str,
) -> dict[str, Any]:
    """检查统一API成功响应。"""

    require_status(
        result,
        step=step,
        expected_status=200,
    )

    if not isinstance(
        result.payload,
        dict,
    ):
        raise SmokeTestFailure(
            f"{step}没有返回JSON对象"
        )

    if (
        result.payload.get("status")
        != "success"
    ):
        raise SmokeTestFailure(
            f"{step}没有返回success状态："
            f"{result.payload}"
        )

    return result.payload


def run_smoke_test(
    *,
    client: PowerAgentApiClient,
    working_directory: Path,
    include_workflows: bool,
) -> None:
    """执行PowerAgent核心HTTP闭环。"""

    document_id: str | None = None
    document_deleted = False

    try:
        health_result = client.get(
            "/health/live"
        )

        require_status(
            health_result,
            step="health",
            expected_status=200,
        )

        ready_result = client.get(
            "/health/ready"
        )

        require_status(
            ready_result,
            step="ready",
            expected_status=200,
        )

        docs_result = client.get(
            "/docs"
        )

        require_status(
            docs_result,
            step="docs",
            expected_status=200,
        )

        openapi_result = client.get(
            "/openapi.json"
        )

        require_status(
            openapi_result,
            step="openapi",
            expected_status=200,
        )

        if not isinstance(
            openapi_result.payload,
            dict,
        ):
            raise SmokeTestFailure(
                "OpenAPI没有返回JSON对象"
            )

        openapi_paths = (
            openapi_result
            .payload
            .get("paths")
        )

        if not isinstance(
            openapi_paths,
            dict,
        ):
            raise SmokeTestFailure(
                "OpenAPI缺少paths字段"
            )

        required_paths = {
            "/api/v1/skills",
            "/api/v1/knowledge/status",
            (
                "/api/v1/knowledge/"
                "documents"
            ),
            "/api/v1/workflows/analyze",
            "/api/v1/rnd/analyze",
        }

        missing_paths = (
            required_paths
            - set(openapi_paths)
        )

        if missing_paths:
            raise SmokeTestFailure(
                "OpenAPI缺少接口："
                f"{sorted(missing_paths)}"
            )

        skills_payload = (
            require_api_success(
                client.get(
                    "/api/v1/skills"
                ),
                step="skills",
            )
        )

        skill_count = (
            skills_payload
            .get("data", {})
            .get("count")
        )

        if (
            not isinstance(
                skill_count,
                int,
            )
            or skill_count <= 0
        ):
            raise SmokeTestFailure(
                "Skill目录为空"
            )

        unique_suffix = (
            uuid4().hex[:8]
        )

        document_path = (
            working_directory
            / (
                "smoke_charging_"
                f"{unique_suffix}.txt"
            )
        )

        document_path.write_text(
            (
                "高SOC快充阶段出现限流时，"
                "应检查最高温度、单体电压、"
                "单体压差和热管理冷却能力。"
            ),
            encoding="utf-8",
        )

        upload_payload = (
            require_api_success(
                client.post_document(
                    path=(
                        "/api/v1/knowledge/"
                        "documents"
                    ),
                    file_path=document_path,
                    form_data={
                        "topic": (
                            "高SOC快充限流"
                        ),
                        "subsystem": (
                            "charging"
                        ),
                        "overwrite": "false",
                    },
                ),
                step="document-upload",
            )
        )

        upload_data = (
            upload_payload.get("data")
        )

        if not isinstance(
            upload_data,
            dict,
        ):
            raise SmokeTestFailure(
                "上传响应缺少data对象"
            )

        returned_document_id = (
            upload_data.get(
                "document_id"
            )
        )

        if not isinstance(
            returned_document_id,
            str,
        ):
            raise SmokeTestFailure(
                "上传响应缺少document_id"
            )

        document_id = (
            returned_document_id
        )

        status_payload = (
            require_api_success(
                client.get(
                    (
                        "/api/v1/"
                        "knowledge/status"
                    )
                ),
                step="knowledge-status",
            )
        )

        chunk_count = (
            status_payload
            .get("data", {})
            .get("chunk_count")
        )

        if (
            not isinstance(
                chunk_count,
                int,
            )
            or chunk_count <= 0
        ):
            raise SmokeTestFailure(
                "文档上传后知识块数量没有增加"
            )

        if include_workflows:
            workflow_trace_id = (
                "smoke_workflow_"
                f"{unique_suffix}"
            )

            workflow_payload = (
                require_api_success(
                    client.post_json(
                        (
                            "/api/v1/"
                            "workflows/analyze"
                        ),
                        {
                            "raw_input": (
                                "分析动力电池"
                                "单体压差扩大问题"
                            ),
                            "trace_id": (
                                workflow_trace_id
                            ),
                            "max_retries": 1,
                            "skill_inputs": None,
                            "include_trace": True,
                            (
                                "include_"
                                "intermediate_results"
                            ): False,
                        },
                    ),
                    step="workflow-analyze",
                )
            )

            if (
                workflow_payload.get(
                    "trace_id"
                )
                != workflow_trace_id
            ):
                raise SmokeTestFailure(
                    "通用工作流Trace ID不一致"
                )

            rnd_trace_id = (
                "smoke_rnd_"
                f"{unique_suffix}"
            )

            rnd_payload = (
                require_api_success(
                    client.post_json(
                        "/api/v1/rnd/analyze",
                        {
                            "raw_input": (
                                "分析高SOC快充"
                                "限流问题"
                            ),
                            "trace_id": (
                                rnd_trace_id
                            ),
                            "affected_scope": [
                                "部分车辆"
                            ],
                            "available_data": [
                                "充电电流",
                                "单体电压",
                            ],
                            (
                                "operating_"
                                "conditions"
                            ): [],
                            (
                                "requested_"
                                "deliverables"
                            ): [
                                "候选根因",
                                "验证实验",
                            ],
                            "max_retries": 1,
                            "skill_inputs": {},
                        },
                    ),
                    step="rnd-analyze",
                )
            )

            if (
                rnd_payload.get("trace_id")
                != rnd_trace_id
            ):
                raise SmokeTestFailure(
                    "研发分析Trace ID不一致"
                )

        delete_payload = (
            require_api_success(
                client.delete(
                    (
                        "/api/v1/knowledge/"
                        "documents/"
                        f"{document_id}"
                    )
                ),
                step="document-delete",
            )
        )

        if (
            delete_payload
            .get("data", {})
            .get("deleted")
            is not True
        ):
            raise SmokeTestFailure(
                "文档删除结果不正确"
            )

        document_deleted = True

        missing_result = client.delete(
            (
                "/api/v1/knowledge/"
                "documents/"
                f"{document_id}"
            )
        )

        require_status(
            missing_result,
            step="document-delete-missing",
            expected_status=404,
        )

        if (
            not isinstance(
                missing_result.payload,
                dict,
            )
            or (
                missing_result.payload
                .get("error", {})
                .get("code")
                != "resource_not_found"
            )
        ):
            raise SmokeTestFailure(
                "重复删除没有返回"
                "resource_not_found"
            )

    finally:
        if (
            document_id is not None
            and not document_deleted
        ):
            try:
                client.delete(
                    (
                        "/api/v1/knowledge/"
                        "documents/"
                        f"{document_id}"
                    )
                )
            except httpx.HTTPError:
                pass


def build_parser() -> argparse.ArgumentParser:
    """构造Smoke Test命令行。"""

    parser = argparse.ArgumentParser(
        description=(
            "执行PowerAgent API外部"
            "HTTP Smoke Test"
        )
    )

    parser.add_argument(
        "--base-url",
        default=DEFAULT_BASE_URL,
        help=(
            "PowerAgent API地址，默认："
            f"{DEFAULT_BASE_URL}"
        ),
    )

    parser.add_argument(
        "--timeout",
        type=float,
        default=(
            DEFAULT_TIMEOUT_SECONDS
        ),
        help="单次HTTP请求超时时间",
    )

    parser.add_argument(
        "--include-workflows",
        action="store_true",
        help=(
            "额外调用真实通用工作流"
            "和研发分析工作流"
        ),
    )

    return parser


def main(
    argv: list[str] | None = None,
) -> int:
    """运行外部HTTP Smoke Test。"""

    parser = build_parser()
    args = parser.parse_args(argv)

    if args.timeout <= 0:
        parser.error(
            "--timeout必须大于0"
        )

    try:
        with TemporaryDirectory(
            prefix="poweragent_smoke_"
        ) as temporary_directory:
            with PowerAgentApiClient(
                base_url=args.base_url,
                timeout_seconds=args.timeout,
            ) as client:
                run_smoke_test(
                    client=client,
                    working_directory=Path(
                        temporary_directory
                    ),
                    include_workflows=(
                        args.include_workflows
                    ),
                )

    except SmokeTestFailure as exc:
        print(
            f"Smoke Test失败：{exc}",
            file=sys.stderr,
        )
        return 1

    except httpx.ConnectError:
        print(
            "无法连接PowerAgent API。",
            file=sys.stderr,
        )
        return 2

    except httpx.TimeoutException:
        print(
            "PowerAgent API请求超时。",
            file=sys.stderr,
        )
        return 3

    except (
        httpx.HTTPError,
        OSError,
    ) as exc:
        print(
            "Smoke Test执行异常："
            f"{type(exc).__name__}: {exc}",
            file=sys.stderr,
        )
        return 4

    print(
        "PowerAgent API Smoke Test通过。"
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())