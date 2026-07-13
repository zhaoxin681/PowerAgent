"""PowerAgent的DeepSeek统一LLM客户端。"""

from __future__ import annotations

import json
import os
from typing import TypeVar

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


SchemaType = TypeVar("SchemaType", bound=BaseModel)


class LLMClientError(RuntimeError):
    """PowerAgent调用LLM时的基础异常。"""


class LLMAuthenticationError(LLMClientError):
    """API身份认证失败。"""


class LLMRateLimitError(LLMClientError):
    """API调用达到频率限制或账户额度不足。"""


class LLMConnectionError(LLMClientError):
    """无法连接到LLM服务。"""


class LLMResponseError(LLMClientError):
    """LLM返回结果无法正常使用。"""


class LLMValidationError(LLMResponseError):
    """LLM返回的JSON不符合Pydantic数据模型。"""


class LLMClient:
    """PowerAgent统一DeepSeek调用入口。"""

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        model: str | None = None,
        timeout: float = 60.0,
        max_retries: int = 2,
    ) -> None:
        """初始化DeepSeek客户端。"""

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

        if not resolved_api_key:
            raise ValueError(
                "未找到DEEPSEEK_API_KEY。"
                "请在项目根目录的.env文件中配置DeepSeek API Key。"
            )

        self.model = resolved_model

        self._client = OpenAI(
            api_key=resolved_api_key,
            base_url=resolved_base_url,
            timeout=timeout,
            max_retries=max_retries,
        )

    def parse_structured(
        self,
        *,
        developer_prompt: str,
        user_input: str,
        response_model: type[SchemaType],
    ) -> SchemaType:
        """
        调用DeepSeek，并将输出校验为指定Pydantic模型。

        DeepSeek负责生成JSON字符串，
        Pydantic负责验证字段、类型、枚举和数值范围。
        """

        if not developer_prompt.strip():
            raise ValueError("developer_prompt不能为空。")

        if not user_input.strip():
            raise ValueError("user_input不能为空。")

        # 将Pydantic模型转换成JSON Schema，
        # 并放入系统Prompt中约束模型输出。
        json_schema = response_model.model_json_schema()

        schema_text = json.dumps(
            json_schema,
            ensure_ascii=False,
            indent=2,
        )

        system_prompt = f"""
{developer_prompt}

请仅返回一个合法的JSON对象，不要输出解释、前言、结尾或Markdown代码块。

输出必须符合以下JSON Schema：

{schema_text}

重要要求：

1. 必须返回JSON。
2. 不得使用```json代码块。
3. 不得输出JSON之外的任何文字。
4. 所有Schema要求的字段都必须出现。
5. 没有内容的列表字段返回空列表[]。
6. 无法判断的枚举字段使用unknown。
7. 不得增加Schema中不存在的字段。
""".strip()

        try:
            response = self._client.chat.completions.create(
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
                max_tokens=4096,
                # 结构化抽取任务不需要复杂推理，
                # 关闭thinking可以降低延迟。
                extra_body={
                    "thinking": {
                        "type": "disabled",
                    }
                },
            )

        except AuthenticationError as exc:
            raise LLMAuthenticationError(
                "DeepSeek API认证失败，"
                "请检查DEEPSEEK_API_KEY是否正确。"
            ) from exc

        except RateLimitError as exc:
            raise LLMRateLimitError(
                "DeepSeek API达到频率限制或账户余额不足，"
                "请检查调用频率和账户余额。"
            ) from exc

        except APITimeoutError as exc:
            raise LLMConnectionError(
                "DeepSeek请求超时，"
                "请检查网络或增大timeout参数。"
            ) from exc

        except APIConnectionError as exc:
            raise LLMConnectionError(
                "无法连接DeepSeek API，"
                "请检查网络、代理和DEEPSEEK_BASE_URL。"
            ) from exc

        except APIStatusError as exc:
            raise LLMResponseError(
                "DeepSeek API返回异常状态码："
                f"{exc.status_code}；"
                f"request_id={exc.request_id}"
            ) from exc

        if not response.choices:
            raise LLMResponseError(
                "DeepSeek响应中没有choices结果。"
            )

        choice = response.choices[0]

        if choice.finish_reason == "length":
            raise LLMResponseError(
                "DeepSeek输出因长度限制被截断，"
                "请增大max_tokens或缩短Prompt。"
            )

        content = choice.message.content

        if not content or not content.strip():
            raise LLMResponseError(
                "DeepSeek返回了空内容，请重新调用。"
            )

        try:
            parsed_result = response_model.model_validate_json(
                content
            )

        except ValidationError as exc:
            raise LLMValidationError(
                "DeepSeek返回了JSON，"
                "但内容不符合Pydantic数据模型。\n"
                f"原始输出：{content}\n"
                f"校验错误：{exc}"
            ) from exc

        return parsed_result