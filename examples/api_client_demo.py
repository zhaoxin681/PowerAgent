"""PowerAgent FastAPI命令行演示客户端。"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import quote

import httpx


DEFAULT_BASE_URL = (
    "http://127.0.0.1:8000"
)

DEFAULT_TIMEOUT_SECONDS = 30.0

REQUEST_ID_HEADER = "X-Request-ID"

DOCUMENT_MIME_TYPES = {
    ".txt": "text/plain",
    ".md": "text/markdown",
    ".pdf": "application/pdf",
}


@dataclass(frozen=True, slots=True)
class ApiClientResult:
    """一次API请求的统一客户端结果。"""

    method: str
    url: str
    status_code: int
    request_id: str | None
    trace_id: str | None
    payload: Any


class PowerAgentApiClient:
    """PowerAgent FastAPI同步客户端。"""

    def __init__(
        self,
        *,
        base_url: str,
        timeout_seconds: float,
        request_id: str | None = None,
        transport: (
            httpx.BaseTransport | None
        ) = None,
    ) -> None:
        """初始化API客户端。"""

        normalized_base_url = (
            base_url.rstrip("/")
        )

        headers: dict[str, str] = {
            "Accept": "application/json",
        }

        if request_id:
            headers[
                REQUEST_ID_HEADER
            ] = request_id

        self._client = httpx.Client(
            base_url=normalized_base_url,
            timeout=timeout_seconds,
            headers=headers,
            transport=transport,
        )

    def close(self) -> None:
        """关闭HTTP连接资源。"""

        self._client.close()

    def __enter__(
        self,
    ) -> "PowerAgentApiClient":
        """进入客户端上下文。"""

        return self

    def __exit__(
        self,
        exc_type: object,
        exc: object,
        traceback: object,
    ) -> None:
        """退出客户端上下文。"""

        self.close()

    def get(
        self,
        path: str,
    ) -> ApiClientResult:
        """发送GET请求。"""

        return self._send(
            method="GET",
            path=path,
        )

    def delete(
        self,
        path: str,
    ) -> ApiClientResult:
        """发送DELETE请求。"""

        return self._send(
            method="DELETE",
            path=path,
        )

    def post_json(
        self,
        path: str,
        payload: dict[str, Any],
    ) -> ApiClientResult:
        """发送JSON格式POST请求。"""

        return self._send(
            method="POST",
            path=path,
            json=payload,
        )

    def post_document(
        self,
        *,
        path: str,
        file_path: Path,
        form_data: dict[str, str],
    ) -> ApiClientResult:
        """以multipart/form-data上传文档。"""

        mime_type = (
            DOCUMENT_MIME_TYPES.get(
                file_path.suffix.lower(),
                "application/octet-stream",
            )
        )

        with file_path.open(
            "rb"
        ) as file_stream:
            return self._send(
                method="POST",
                path=path,
                files={
                    "file": (
                        file_path.name,
                        file_stream,
                        mime_type,
                    )
                },
                data=form_data,
            )

    def _send(
        self,
        *,
        method: str,
        path: str,
        **request_kwargs: Any,
    ) -> ApiClientResult:
        """发送请求并归一化响应结果。"""

        response = self._client.request(
            method=method,
            url=path,
            **request_kwargs,
        )

        payload = self._parse_payload(
            response
        )

        payload_request_id = (
            payload.get("request_id")
            if isinstance(payload, dict)
            else None
        )

        header_request_id = (
            response.headers.get(
                REQUEST_ID_HEADER
            )
        )

        request_id = (
            header_request_id
            or (
                payload_request_id
                if isinstance(
                    payload_request_id,
                    str,
                )
                else None
            )
        )

        payload_trace_id = (
            payload.get("trace_id")
            if isinstance(payload, dict)
            else None
        )

        trace_id = (
            payload_trace_id
            if isinstance(
                payload_trace_id,
                str,
            )
            else None
        )

        return ApiClientResult(
            method=method,
            url=str(response.url),
            status_code=(
                response.status_code
            ),
            request_id=request_id,
            trace_id=trace_id,
            payload=payload,
        )

    @staticmethod
    def _parse_payload(
        response: httpx.Response,
    ) -> Any:
        """解析JSON响应并安全回退到文本。"""

        try:
            return response.json()
        except ValueError:
            return {
                "raw_text": response.text,
            }


def parse_retry_count(
    value: str,
) -> int:
    """解析0至5范围内的重试次数。"""

    try:
        parsed_value = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            "重试次数必须为整数"
        ) from exc

    if not 0 <= parsed_value <= 5:
        raise argparse.ArgumentTypeError(
            "重试次数必须处于0至5之间"
        )

    return parsed_value


def load_json_object(
    path: Path,
    *,
    label: str,
) -> dict[str, Any]:
    """从文件加载JSON对象。"""

    try:
        content = path.read_text(
            encoding="utf-8"
        )
    except OSError as exc:
        raise ValueError(
            f"无法读取{label}文件：{path}"
        ) from exc

    try:
        payload = json.loads(content)
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"{label}文件不是合法JSON："
            f"{path}"
        ) from exc

    if not isinstance(payload, dict):
        raise ValueError(
            f"{label}文件顶层必须是JSON对象"
        )

    return payload


def load_json_list(
    path: Path,
    *,
    label: str,
) -> list[Any]:
    """从文件加载JSON数组。"""

    try:
        content = path.read_text(
            encoding="utf-8"
        )
    except OSError as exc:
        raise ValueError(
            f"无法读取{label}文件：{path}"
        ) from exc

    try:
        payload = json.loads(content)
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"{label}文件不是合法JSON："
            f"{path}"
        ) from exc

    if not isinstance(payload, list):
        raise ValueError(
            f"{label}文件顶层必须是JSON数组"
        )

    return payload


def build_parser() -> argparse.ArgumentParser:
    """构造命令行参数解析器。"""

    parser = argparse.ArgumentParser(
        description=(
            "调用PowerAgent FastAPI服务"
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
        help="HTTP请求超时时间，单位为秒",
    )

    parser.add_argument(
        "--request-id",
        default=None,
        help=(
            "可选客户端Request ID，"
            "服务端会校验并透传"
        ),
    )

    subparsers = parser.add_subparsers(
        dest="command",
        required=True,
    )

    subparsers.add_parser(
        "health",
        help="检查服务进程是否存活",
    )

    subparsers.add_parser(
        "ready",
        help="检查核心依赖是否完成初始化",
    )

    subparsers.add_parser(
        "skills",
        help="查询已注册Skill目录",
    )

    subparsers.add_parser(
        "knowledge-status",
        help="查询当前知识库状态",
    )

    upload_parser = (
        subparsers.add_parser(
            "document-upload",
            help="上传知识文档并更新知识库",
        )
    )

    upload_parser.add_argument(
        "--file",
        type=Path,
        required=True,
        help="需要上传的md、txt或pdf文件",
    )

    upload_parser.add_argument(
        "--topic",
        default=None,
        help="可选知识主题",
    )

    upload_parser.add_argument(
        "--subsystem",
        default=None,
        help=(
            "可选动力系统类型，"
            "例如battery或charging"
        ),
    )

    upload_parser.add_argument(
        "--overwrite",
        action="store_true",
        help="允许覆盖相同document_id的文档",
    )

    delete_parser = (
        subparsers.add_parser(
            "document-delete",
            help="根据document_id删除知识文档",
        )
    )

    delete_parser.add_argument(
        "--document-id",
        required=True,
        help="需要删除的文档稳定标识",
    )

    workflow_parser = (
        subparsers.add_parser(
            "workflow-analyze",
            help="执行通用PowerAgent工作流",
        )
    )

    workflow_parser.add_argument(
        "--input",
        dest="raw_input",
        required=True,
        help="需要分析的动力系统问题",
    )

    workflow_parser.add_argument(
        "--trace-id",
        default=None,
        help="可选工作流Trace ID",
    )

    workflow_parser.add_argument(
        "--max-retries",
        type=parse_retry_count,
        default=2,
        help="单个工作流步骤最大重试次数",
    )

    workflow_parser.add_argument(
        "--skill-inputs-json",
        type=Path,
        default=None,
        help=(
            "可选Skill输入JSON对象文件"
        ),
    )

    workflow_parser.add_argument(
        "--include-trace",
        action="store_true",
        help="在响应中返回工作流执行轨迹",
    )

    workflow_parser.add_argument(
        "--include-intermediate-results",
        action="store_true",
        help="返回Tool、RAG和错误等中间结果",
    )

    rnd_parser = (
        subparsers.add_parser(
            "rnd-analyze",
            help="执行研发问题分析工作流",
        )
    )

    rnd_parser.add_argument(
        "--input",
        dest="raw_input",
        required=True,
        help="需要分析的研发问题",
    )

    rnd_parser.add_argument(
        "--trace-id",
        default=None,
        help="可选研发分析Trace ID",
    )

    rnd_parser.add_argument(
        "--affected-scope",
        action="append",
        default=[],
        help=(
            "已知影响范围，可重复提供"
        ),
    )

    rnd_parser.add_argument(
        "--available-data",
        action="append",
        default=[],
        help=(
            "当前可用数据，可重复提供"
        ),
    )

    rnd_parser.add_argument(
        "--operating-conditions-json",
        type=Path,
        default=None,
        help=(
            "运行条件JSON数组文件"
        ),
    )

    rnd_parser.add_argument(
        "--deliverable",
        action="append",
        default=[],
        help=(
            "需要的研发交付物，可重复提供"
        ),
    )

    rnd_parser.add_argument(
        "--max-retries",
        type=parse_retry_count,
        default=2,
        help="基础工作流最大重试次数",
    )

    rnd_parser.add_argument(
        "--skill-inputs-json",
        type=Path,
        default=None,
        help=(
            "可选Skill输入JSON对象文件"
        ),
    )

    return parser


def build_workflow_payload(
    args: argparse.Namespace,
) -> dict[str, Any]:
    """构造通用工作流请求体。"""

    skill_inputs = (
        load_json_object(
            args.skill_inputs_json,
            label="Skill输入",
        )
        if args.skill_inputs_json
        is not None
        else None
    )

    payload: dict[str, Any] = {
        "raw_input": args.raw_input,
        "max_retries": args.max_retries,
        "skill_inputs": skill_inputs,
        "include_trace": (
            args.include_trace
        ),
        "include_intermediate_results": (
            args.include_intermediate_results
        ),
    }

    if args.trace_id:
        payload["trace_id"] = (
            args.trace_id
        )

    return payload


def build_rnd_payload(
    args: argparse.Namespace,
) -> dict[str, Any]:
    """构造研发分析请求体。"""

    operating_conditions = (
        load_json_list(
            args.operating_conditions_json,
            label="运行条件",
        )
        if args.operating_conditions_json
        is not None
        else []
    )

    skill_inputs = (
        load_json_object(
            args.skill_inputs_json,
            label="Skill输入",
        )
        if args.skill_inputs_json
        is not None
        else {}
    )

    payload: dict[str, Any] = {
        "raw_input": args.raw_input,
        "affected_scope": list(
            args.affected_scope
        ),
        "available_data": list(
            args.available_data
        ),
        "operating_conditions": (
            operating_conditions
        ),
        "requested_deliverables": list(
            args.deliverable
        ),
        "max_retries": args.max_retries,
        "skill_inputs": skill_inputs,
    }

    if args.trace_id:
        payload["trace_id"] = (
            args.trace_id
        )

    return payload


def execute_command(
    client: PowerAgentApiClient,
    args: argparse.Namespace,
) -> ApiClientResult:
    """执行指定客户端命令。"""

    if args.command == "health":
        return client.get(
            "/health/live"
        )

    if args.command == "ready":
        return client.get(
            "/health/ready"
        )

    if args.command == "skills":
        return client.get(
            "/api/v1/skills"
        )

    if (
        args.command
        == "knowledge-status"
    ):
        return client.get(
            "/api/v1/knowledge/status"
        )

    if (
        args.command
        == "document-upload"
    ):
        file_path: Path = args.file

        if not file_path.is_file():
            raise ValueError(
                f"上传文件不存在：{file_path}"
            )

        form_data = {
            "overwrite": (
                "true"
                if args.overwrite
                else "false"
            )
        }

        if args.topic:
            form_data["topic"] = (
                args.topic
            )

        if args.subsystem:
            form_data["subsystem"] = (
                args.subsystem
            )

        return client.post_document(
            path=(
                "/api/v1/knowledge/"
                "documents"
            ),
            file_path=file_path,
            form_data=form_data,
        )

    if (
        args.command
        == "document-delete"
    ):
        document_id = (
            args.document_id.strip()
        )

        if not document_id:
            raise ValueError(
                "document_id不能为空"
            )

        encoded_document_id = quote(
            document_id,
            safe="",
        )

        return client.delete(
            (
                "/api/v1/knowledge/"
                f"documents/"
                f"{encoded_document_id}"
            )
        )

    if (
        args.command
        == "workflow-analyze"
    ):
        return client.post_json(
            "/api/v1/workflows/analyze",
            build_workflow_payload(args),
        )

    if args.command == "rnd-analyze":
        return client.post_json(
            "/api/v1/rnd/analyze",
            build_rnd_payload(args),
        )

    raise ValueError(
        "不支持的客户端命令："
        f"{args.command}"
    )


def print_result(
    result: ApiClientResult,
) -> None:
    """以统一格式输出API调用结果。"""

    print(
        f"HTTP方法: {result.method}"
    )

    print(
        f"请求地址: {result.url}"
    )

    print(
        "HTTP状态: "
        f"{result.status_code}"
    )

    print(
        "Request ID: "
        f"{result.request_id or '-'}"
    )

    print(
        "Trace ID: "
        f"{result.trace_id or '-'}"
    )

    print("\n响应内容：")

    print(
        json.dumps(
            result.payload,
            ensure_ascii=False,
            indent=2,
        )
    )


def main(
    argv: list[str] | None = None,
) -> int:
    """运行PowerAgent API客户端。"""

    parser = build_parser()
    args = parser.parse_args(argv)

    if args.timeout <= 0:
        parser.error(
            "--timeout必须大于0"
        )

    if not args.base_url.strip():
        parser.error(
            "--base-url不能为空"
        )

    try:
        with PowerAgentApiClient(
            base_url=args.base_url,
            timeout_seconds=args.timeout,
            request_id=args.request_id,
        ) as client:
            result = execute_command(
                client,
                args,
            )

    except httpx.ConnectError:
        print(
            "无法连接PowerAgent API，"
            "请确认服务已经启动。",
            file=sys.stderr,
        )
        return 2

    except httpx.TimeoutException:
        print(
            "PowerAgent API请求超时。",
            file=sys.stderr,
        )
        return 3

    except httpx.HTTPError as exc:
        print(
            "PowerAgent API请求失败："
            f"{type(exc).__name__}",
            file=sys.stderr,
        )
        return 4

    except (
        ValueError,
        OSError,
    ) as exc:
        print(
            f"客户端输入无效：{exc}",
            file=sys.stderr,
        )
        return 5

    print_result(result)

    return (
        0
        if 200
        <= result.status_code
        < 400
        else 1
    )


if __name__ == "__main__":
    raise SystemExit(main())