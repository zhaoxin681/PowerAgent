"""PowerAgent的DeepSeek统一LLM客户端。"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import random
import time
import uuid
from dataclasses import dataclass
from typing import Any, Callable, TypeVar

from dotenv import load_dotenv
from openai import (
    APIConnectionError,
    APIStatusError,
    APITimeoutError,
    AuthenticationError,
    OpenAI,
    RateLimitError,
)
from pydantic import BaseModel, ValidationError

from agent_core.logging_config import get_logger

from agent_core.tool_models import (
    ToolCallDecision,
    ToolSelectionResponse,
)


SchemaType = TypeVar("SchemaType", bound=BaseModel)


class LLMClientError(RuntimeError):
    """PowerAgent调用LLM时的基础异常。该类异常不建议自动重试"""
    retryable = False


class LLMAuthenticationError(LLMClientError):
    """API身份认证失败。"""


class LLMInsufficientBalanceError(LLMClientError):
    """API账户余额不足。"""


class LLMInvalidRequestError(LLMClientError):
    """LLM请求参数不合法。"""


class LLMRateLimitError(LLMClientError):
    """API调用达到频率限制或并发限制。"""
    retryable = True


class LLMConnectionError(LLMClientError):
    """无法连接到LLM服务。"""
    retryable = True


class LLMServerError(LLMClientError):
    """LLM服务端错误。"""
    retryable = True


class LLMResponseError(LLMClientError):
    """LLM返回结果无法正常使用。"""


class LLMEmptyResponseError(LLMClientError):
    """LLM服务端错误。"""
    retryable = True


class LLMValidationError(LLMResponseError):
    """LLM返回的JSON不符合Pydantic数据模型。"""
    retryable = True

class LLMTruncatedResponseError(LLMResponseError):
    """LLM输出因长度限制被截断。"""


@dataclass(frozen=True)  # 装饰器，专门用来简化“只是用来存储一组数据”的类的写法
class RetryConfig:
    """LLM调用重试配置。"""

    # 带抖动的指数退避重试策略
    max_attempts: int = 3
    base_delay_seconds: float = 1.0
    max_delay_seconds: float = 8.0
    jitter_ratio: float = 0.2 # 抖动比例

    def __post_init__(self) -> None:
        if self.max_attempts < 1:
            raise ValueError(
                "max_attempts必须大于等于1。"
            )

        if self.base_delay_seconds < 0:
            raise ValueError(
                "base_delay_seconds不能小于0。"
            )

        if self.max_delay_seconds < 0:
            raise ValueError(
                "max_delay_seconds不能小于0。"
            )

        if not 0 <= self.jitter_ratio <= 1:
            raise ValueError(
                "jitter_ratio必须位于0到1之间。"
            )

    @classmethod
    def from_env(cls) -> "RetryConfig":
        """从环境变量读取重试配置。"""

        return cls(
            max_attempts=int(
                os.getenv(
                    "LLM_MAX_ATTEMPTS",
                    "3",
                )
            ),
            base_delay_seconds=float(
                os.getenv(
                    "LLM_RETRY_BASE_DELAY",
                    "1.0",
                )
            ),
            max_delay_seconds=float(
                os.getenv(
                    "LLM_RETRY_MAX_DELAY",
                    "8.0",
                )
            ),
            jitter_ratio=float(
                os.getenv(
                    "LLM_RETRY_JITTER",
                    "0.2",
                )
            ),
        )


class LLMClient:
    """PowerAgent统一DeepSeek调用入口。"""

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        model: str | None = None,
        timeout: float = 60.0,
        max_tokens: int = 2048,
        retry_config: RetryConfig | None = None,
        client: Any | None = None,
        logger: logging.Logger | None = None,
        sleep_func: Callable[[float], None] = time.sleep,
        random_func: Callable[[], float] = random.random,
    ) -> None:
        """初始化DeepSeek客户端。
        client、sleep_func和random_func参数主要用于Mock测试。
        """

        load_dotenv()

        resolved_api_key = (
            api_key or os.getenv("DEEPSEEK_API_KEY")
        )

        resolved_base_url = (
            base_url
            or os.getenv("DEEPSEEK_BASE_URL")
            or "https://api.deepseek.com"
        )

        resolved_model = (
            model
            or os.getenv("DEEPSEEK_MODEL")
            or "deepseek-v4-flash"
        )

        if client is None and not resolved_api_key:
            raise ValueError(
                "未找到DEEPSEEK_API_KEY。"
                "请在项目根目录的.env文件中配置DeepSeek API Key。"
            )

        self.model = resolved_model
        self.max_tokens = max_tokens
        self.retry_config = (
            retry_config
            or RetryConfig.from_env()
        )

        self._sleep = sleep_func
        self._random = random_func
        self._logger = logger or get_logger(
            "llm_client"
        )

        if client is not None:
            self._client = client
        else:
            self._client = OpenAI(
                api_key=resolved_api_key,
                base_url=resolved_base_url,
                timeout=timeout,

                # 关闭SDK内部重试，统一由本类控制，
                # 避免出现两层重试叠加。
                max_retries=0,
            )

    # 带重试机制地调用LLM并返回结构化结果
    def parse_structured(
        self,
        *,
        developer_prompt: str,
        user_input: str,
        response_model: type[SchemaType],
    ) -> SchemaType:
        """
        调用DeepSeek并返回经过Pydantic校验的结构化对象。
        """
        # 前置校验
        if not developer_prompt.strip():
            raise ValueError(
                "developer_prompt不能为空。"
            )

        if not user_input.strip():
            raise ValueError(
                "user_input不能为空。"
            )

        # 生成全局唯一随机ID，作为这次调用的“请求追踪号”
        request_id = uuid.uuid4().hex
        # 把输入原文计算出SHA-256哈希值，取前12位字符作为“指纹”
        input_fingerprint = hashlib.sha256(
            user_input.encode("utf-8")
        ).hexdigest()[:12]
        # 构建系统提示词，业务提示词和JSON Schema拼接
        system_prompt = self._build_system_prompt(
            developer_prompt=developer_prompt,
            response_model=response_model,
        )

        # 重试循环
        total_start_time = time.perf_counter()

        for attempt in range(
            1,
            self.retry_config.max_attempts + 1,
        ):
            attempt_start_time = time.perf_counter()

            self._logger.info(
                "开始调用LLM结构化解析接口。",
                extra={
                    "event": "llm_request_started",
                    "request_id": request_id,
                    "model": self.model,
                    "attempt": attempt,
                    "max_attempts": (
                        self.retry_config.max_attempts
                    ),
                    "input_chars": len(user_input),
                    "input_fingerprint": input_fingerprint,
                    "response_model": response_model.__name__,   # 记录希望解析的pydantic模型类名，如PowerSystemIssue
                },
            )

            # 发起一次API请求，返回result-已经解析检验好的pydantic对象、response-原始API响应对象，用来提取额外的元数据比如token消耗
            try:
                result, response = self._call_once(
                    system_prompt=system_prompt,
                    user_input=user_input,
                    response_model=response_model,
                )

                attempt_latency_ms = round(
                    (
                        time.perf_counter()
                        - attempt_start_time
                    )
                    * 1000,
                    2,
                )

                total_latency_ms = round(
                    (
                        time.perf_counter()
                        - total_start_time
                    )
                    * 1000,
                    2,
                )

                # 记录这次调用消耗了多少token
                usage = self._extract_usage(response)

                self._logger.info(
                    "LLM结构化解析成功。",
                    extra={
                        "event": "llm_request_succeeded",
                        "request_id": request_id,
                        "api_response_id": getattr(
                            response,
                            "id",
                            None,
                        ),
                        "model": self.model,
                        "attempt": attempt,
                        "attempt_latency_ms": (
                            attempt_latency_ms
                        ),
                        "total_latency_ms": total_latency_ms,
                        "prompt_tokens": usage[
                            "prompt_tokens"
                        ],
                        "completion_tokens": usage[
                            "completion_tokens"
                        ],
                        "total_tokens": usage[
                            "total_tokens"
                        ],
                        "response_model": (
                            response_model.__name__
                        ),
                    },
                )

                return result
            # 处理失败情况：判断值不值得重试
            except LLMClientError as exc:
                retryable = exc.retryable

                attempts_exhausted = (
                    attempt
                    >= self.retry_config.max_attempts
                ) # 判断是否达到配置设定最大尝试次数上限

                should_retry = (
                    retryable
                    and not attempts_exhausted
                )
                # 不该重试的话记录错误日志并真正抛出异常
                if not should_retry:
                    total_latency_ms = round(
                        (
                            time.perf_counter()
                            - total_start_time
                        )
                        * 1000,
                        2,
                    )

                    self._logger.error(
                        "LLM结构化解析失败。",
                        extra={
                            "event": "llm_request_failed",
                            "request_id": request_id,
                            "model": self.model,
                            "attempt": attempt,
                            "max_attempts": (
                                self.retry_config.max_attempts
                            ),
                            "retryable": retryable,
                            "error_type": type(exc).__name__,
                            "total_latency_ms": (
                                total_latency_ms
                            ),
                        },
                    )

                    raise
                # 该重试计算等待时间、记录警告日志、休眠
                delay = self._calculate_retry_delay(
                    failed_attempt=attempt,
                )

                self._logger.warning(
                    "LLM调用失败，准备重试。",
                    extra={
                        "event": "llm_request_retry",
                        "request_id": request_id,
                        "model": self.model,
                        "attempt": attempt,
                        "next_attempt": attempt + 1,
                        "max_attempts": (
                            self.retry_config.max_attempts
                        ),
                        "error_type": type(exc).__name__,
                        "retry_delay_seconds": delay,
                    },
                )

                self._sleep(delay)

        raise LLMResponseError(
            "LLM调用流程异常结束。"
        )
    

    def request_tool_call(
        self,
        *,
        developer_prompt: str,
        user_input: str,
        tools: list[dict[str, Any]],
    ) -> ToolSelectionResponse:
        """调用DeepSeek并返回供应商无关的工具选择结果。"""

        if not developer_prompt.strip():
            raise ValueError(
                "developer_prompt不能为空。"
            )

        if not user_input.strip():
            raise ValueError(
                "user_input不能为空。"
            )

        if not tools:
            raise ValueError(
                "tools不能为空。"
            )

        request_id = uuid.uuid4().hex

        input_fingerprint = hashlib.sha256(
            user_input.encode("utf-8")
        ).hexdigest()[:12]

        total_start_time = time.perf_counter()

        for attempt in range(
            1,
            self.retry_config.max_attempts + 1,
        ):
            attempt_start_time = time.perf_counter()

            self._logger.info(
                "开始调用LLM工具选择接口。",
                extra={
                    "event": "llm_tool_request_started",
                    "request_id": request_id,
                    "model": self.model,
                    "attempt": attempt,
                    "max_attempts": (
                        self.retry_config.max_attempts
                    ),
                    "input_chars": len(user_input),
                    "input_fingerprint": input_fingerprint,
                    "tool_count": len(tools),
                },
            )

            try:
                result, response = self._call_tool_once(
                    developer_prompt=developer_prompt,
                    user_input=user_input,
                    tools=tools,
                )

                attempt_latency_ms = round(
                    (
                        time.perf_counter()
                        - attempt_start_time
                    )
                    * 1000,
                    2,
                )

                total_latency_ms = round(
                    (
                        time.perf_counter()
                        - total_start_time
                    )
                    * 1000,
                    2,
                )

                usage = self._extract_usage(response)

                self._logger.info(
                    "LLM工具选择成功。",
                    extra={
                        "event": "llm_tool_request_succeeded",
                        "request_id": request_id,
                        "api_response_id": getattr(
                            response,
                            "id",
                            None,
                        ),
                        "model": self.model,
                        "attempt": attempt,
                        "attempt_latency_ms": (
                            attempt_latency_ms
                        ),
                        "total_latency_ms": total_latency_ms,
                        "tool_call_count": len(
                            result.tool_calls
                        ),
                        "prompt_tokens": usage[
                            "prompt_tokens"
                        ],
                        "completion_tokens": usage[
                            "completion_tokens"
                        ],
                        "total_tokens": usage[
                            "total_tokens"
                        ],
                    },
                )

                return result

            except LLMClientError as exc:
                retryable = exc.retryable

                attempts_exhausted = (
                    attempt
                    >= self.retry_config.max_attempts
                )

                should_retry = (
                    retryable
                    and not attempts_exhausted
                )

                if not should_retry:
                    total_latency_ms = round(
                        (
                            time.perf_counter()
                            - total_start_time
                        )
                        * 1000,
                        2,
                    )

                    self._logger.error(
                        "LLM工具选择失败。",
                        extra={
                            "event": (
                                "llm_tool_request_failed"
                            ),
                            "request_id": request_id,
                            "model": self.model,
                            "attempt": attempt,
                            "max_attempts": (
                                self.retry_config.max_attempts
                            ),
                            "retryable": retryable,
                            "error_type": (
                                type(exc).__name__
                            ),
                            "total_latency_ms": (
                                total_latency_ms
                            ),
                        },
                    )

                    raise

                delay = self._calculate_retry_delay(
                    failed_attempt=attempt,
                )

                self._logger.warning(
                    "LLM工具选择失败，准备重试。",
                    extra={
                        "event": "llm_tool_request_retry",
                        "request_id": request_id,
                        "model": self.model,
                        "attempt": attempt,
                        "next_attempt": attempt + 1,
                        "max_attempts": (
                            self.retry_config.max_attempts
                        ),
                        "error_type": type(exc).__name__,
                        "retry_delay_seconds": delay,
                    },
                )

                self._sleep(delay)

        raise LLMResponseError(
            "LLM工具选择流程异常结束。"
        )


    def _create_chat_completion(
        self,
        **request_kwargs: Any,
    ) -> Any:
        """执行一次OpenAI兼容请求，并统一转换SDK异常。"""

        try:
            return self._client.chat.completions.create(
                **request_kwargs
            )
        except LLMClientError:
            # 便于Mock测试直接抛出领域异常。
            raise
        except AuthenticationError as exc:
            raise LLMAuthenticationError(
                "DeepSeek API认证失败，"
                "请检查DEEPSEEK_API_KEY。"
            ) from exc
        except RateLimitError as exc:
            raise LLMRateLimitError(
                "DeepSeek API达到频率或并发限制。"
            ) from exc
        except APITimeoutError as exc:
            raise LLMConnectionError(
                "DeepSeek请求超时。"
            ) from exc
        except APIConnectionError as exc:
            raise LLMConnectionError(
                "无法连接DeepSeek API。"
            ) from exc
        except APIStatusError as exc:
            status_code = int(
                getattr(
                    exc,
                    "status_code",
                    0,
                )
                or 0
            )
            if status_code == 402:
                raise LLMInsufficientBalanceError(
                    "DeepSeek账户余额不足。"
                ) from exc
            if status_code in {400, 422}:
                raise LLMInvalidRequestError(
                    "DeepSeek请求参数不合法。"
                ) from exc
            if status_code == 429:
                raise LLMRateLimitError(
                    "DeepSeek API达到频率限制。"
                ) from exc
            if status_code >= 500:
                raise LLMServerError(
                    f"DeepSeek服务端错误：{status_code}。"
                ) from exc
            raise LLMResponseError(
                "DeepSeek API返回异常状态码："
                f"{status_code}。"
            ) from exc


    # 负责真正发起一次API调用
    def _call_once(
        self,
        *,
        system_prompt: str,
        user_input: str,
        response_model: type[SchemaType],
    ) -> tuple[SchemaType, Any]:
        """执行一次DeepSeek结构化输出调用。"""

        response = self._create_chat_completion(
            model=self.model,
            messages=[
                {
                    "role": "system",
                    "content": system_prompt,
                },
                {
                    "role": "user",
                    "content": user_input,
                },
            ],
            response_format={
                "type": "json_object",
            },
            temperature=0.0,
            max_tokens=self.max_tokens,
            extra_body={
                "thinking": {
                    "type": "disabled",
                }
            },
        )

        if not getattr(response, "choices", None):
            raise LLMEmptyResponseError(
                "DeepSeek响应中没有choices。"
            )

        choice = response.choices[0]

        if getattr(choice, "finish_reason", None) == "length":
            raise LLMTruncatedResponseError(
                "DeepSeek输出因长度限制被截断。"
            )

        message = getattr(
            choice,
            "message",
            None,
        )

        content = getattr(
            message,
            "content",
            None,
        )

        if not content or not content.strip():
            raise LLMEmptyResponseError(
                "DeepSeek返回了空内容。"
            )

        try:
            parsed_result = (
                response_model.model_validate_json(
                    content
                )
            )
        except ValidationError as exc:
            error_count = exc.error_count()
            raise LLMValidationError(
                "DeepSeek返回了JSON，"
                "但未通过Pydantic校验；"
                f"错误数量：{error_count}。"
            ) from exc

        return parsed_result, response
    

    def _call_tool_once(
        self,
        *,
        developer_prompt: str,
        user_input: str,
        tools: list[dict[str, Any]],
    ) -> tuple[ToolSelectionResponse, Any]:
        """执行一次DeepSeek Tool Calling请求。"""

        response = self._create_chat_completion(
            model=self.model,
            messages=[
                {
                    "role": "system",
                    "content": developer_prompt,
                },
                {
                    "role": "user",
                    "content": user_input,
                },
            ],
            tools=tools,
            tool_choice="auto",
            temperature=0.0,
            max_tokens=self.max_tokens,
            stream=False,
            extra_body={
                "thinking": {
                    "type": "disabled",
                }
            },
        )

        if not getattr(response, "choices", None):
            raise LLMEmptyResponseError(
                "DeepSeek响应中没有choices。"
            )

        choice = response.choices[0]

        if getattr(choice, "finish_reason", None) == "length":
            raise LLMTruncatedResponseError(
                "DeepSeek Tool Calling输出因长度限制被截断。"
            )

        message = getattr(
            choice,
            "message",
            None,
        )

        if message is None:
            raise LLMEmptyResponseError(
                "DeepSeek响应中没有message。"
            )

        # 提取tool_calls和文本内容，做归一化处理
        raw_tool_calls = (
            getattr(
                message,
                "tool_calls",
                None,
            )
            or []
        )

        raw_content = getattr(
            message,
            "content",
            None,
        )

        assistant_content = (
            raw_content.strip()
            if isinstance(raw_content, str)
            and raw_content.strip()
            else None
        )

        # 没有工具调用时，允许模型通过普通文本说明信息不足。
        # 但工具调用和文本都为空时，视为无效响应。
        if not raw_tool_calls and assistant_content is None:
            raise LLMEmptyResponseError(
                "DeepSeek既未返回工具调用，也未返回文本内容。"
            )

        # 逐个校验并转换每一个工具调用
        decisions: list[ToolCallDecision] = []

        try:
            for tool_call in raw_tool_calls:
                function = getattr(
                    tool_call,
                    "function",
                    None,
                )

                call_id = getattr(
                    tool_call,
                    "id",
                    None,
                )
                tool_name = getattr(
                    function,
                    "name",
                    None,
                )
                arguments_json = getattr(
                    function,
                    "arguments",
                    None,
                )

                if (
                    not isinstance(call_id, str)
                    or not call_id.strip()
                    or not isinstance(tool_name, str)
                    or not tool_name.strip()
                    or not isinstance(arguments_json, str)
                ):
                    raise LLMResponseError(
                        "DeepSeek返回了不完整的工具调用数据。"
                    )

                decisions.append(
                    ToolCallDecision(
                        call_id=call_id,
                        tool_name=tool_name,
                        arguments_json=arguments_json,
                    )
                )

        except ValidationError as exc:
            raise LLMValidationError(
                "DeepSeek返回的工具调用未通过内部数据模型校验；"
                f"错误数量：{exc.error_count()}。"
            ) from exc

        return (
            ToolSelectionResponse(
                tool_calls=decisions,
                assistant_content=assistant_content,
            ),
            response,
        )

    # 解决Deepseek无法自动严格约束输出格式的问题/需要在提示词里手动、明确地告诉模型该怎么输出
    @staticmethod
    def _build_system_prompt(
        *,
        developer_prompt: str,
        response_model: type[BaseModel],
    ) -> str:
        """把业务Prompt和JSON Schema组合起来。"""

        schema_text = json.dumps(
            response_model.model_json_schema(),  # 生成完整的schema描述
            ensure_ascii=False,
            indent=2,
        )

        return f"""
{developer_prompt}

请仅输出一个合法的JSON对象。

必须遵守：

1. 输出中必须包含JSON。
2. 不得输出Markdown代码块。
3. 不得输出JSON之外的解释文字。
4. 所有Schema要求的字段都必须出现。
5. 没有内容的列表字段返回空列表[]。
6. 无法判断的枚举字段使用unknown。
7. 不得增加Schema中不存在的字段。
8. 不得虚构用户没有提供的测量数据。

输出必须符合以下JSON Schema：

{schema_text}
""".strip()

    def _calculate_retry_delay(
        self,
        *,
        failed_attempt: int,
    ) -> float:
        """计算指数退避与随机抖动后的等待时间。"""

        exponential_delay = (
            self.retry_config.base_delay_seconds
            * (2 ** (failed_attempt - 1))
        )

        capped_delay = min(
            exponential_delay,
            self.retry_config.max_delay_seconds,
        )

        jitter_factor = (
            1
            + self.retry_config.jitter_ratio
            * (2 * self._random() - 1)
        )

        return round(
            max(
                0.0,
                capped_delay * jitter_factor,
            ),
            3,
        )

    @staticmethod
    def _extract_usage(
        response: Any,
    ) -> dict[str, int | None]:
        """提取Token消耗。"""

        usage = getattr(
            response,
            "usage",
            None,
        )

        if usage is None:
            return {
                "prompt_tokens": None,
                "completion_tokens": None,
                "total_tokens": None,
            }

        return {
            "prompt_tokens": getattr(
                usage,
                "prompt_tokens",
                None,
            ),
            "completion_tokens": getattr(
                usage,
                "completion_tokens",
                None,
            ),
            "total_tokens": getattr(
                usage,
                "total_tokens",
                None,
            ),
        }