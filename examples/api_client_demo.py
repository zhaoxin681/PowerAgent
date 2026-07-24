"""PowerAgent FastAPI命令行演示客户端。"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from typing import Any

import httpx


DEFAULT_BASE_URL = (
    "http://127.0.0.1:8000"
)

DEFAULT_TIMEOUT_SECONDS = 30.0

REQUEST_ID_HEADER = "X-Request-ID"


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
        )

    def close(self) -> None:
        """关闭HTTP连接资源。"""

        self._client.close()

    def __enter__(
        self,
    ) -> "PowerAgentApiClient":
        return self

    def __exit__(
        self,
        exc_type: object,
        exc: object,
        traceback: object,
    ) -> None:
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

        trace_id = (
            payload.get("trace_id")
            if isinstance(payload, dict)
            else None
        )

        request_id = (
            response.headers.get(
                REQUEST_ID_HEADER
            )
        )

        return ApiClientResult(
            method=method,
            url=str(response.url),
            status_code=(
                response.status_code
            ),
            request_id=request_id,
            trace_id=(
                trace_id
                if isinstance(
                    trace_id,
                    str,
                )
                else None
            ),
            payload=payload,
        )

    @staticmethod
    def _parse_payload(
        response: httpx.Response,
    ) -> Any:
        """解析JSON响应并安全回退到文本。"""

        try:
            return response.json()
        except json.JSONDecodeError:
            return {
                "raw_text": response.text,
            }


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
            "可选的客户端Request ID，"
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

    return parser


def execute_command(
    client: PowerAgentApiClient,
    command: str,
) -> ApiClientResult:
    """执行指定客户端命令。"""

    if command == "health":
        return client.get(
            "/health/live"
        )

    if command == "ready":
        return client.get(
            "/health/ready"
        )

    if command == "skills":
        return client.get(
            "/api/v1/skills"
        )

    raise ValueError(
        f"不支持的客户端命令：{command}"
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


def main() -> int:
    """运行PowerAgent API客户端。"""

    parser = build_parser()
    args = parser.parse_args()

    if args.timeout <= 0:
        parser.error(
            "--timeout必须大于0"
        )

    try:
        with PowerAgentApiClient(
            base_url=args.base_url,
            timeout_seconds=args.timeout,
            request_id=args.request_id,
        ) as client:
            result = execute_command(
                client,
                args.command,
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