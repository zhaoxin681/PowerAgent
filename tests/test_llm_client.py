"""LLMClient可靠性和重试机制测试。Mock(模拟)测试"""

from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from agent_core.llm_client import (
    LLMAuthenticationError,
    LLMClient,
    LLMValidationError,
    RetryConfig,
)
from agent_core.schemas import PowerSystemIssue

# 准备测试数据
USER_INPUT = (
    "车辆行驶过程中，第36号单体电压"
    "比其他单体低180 mV。"
)


VALID_RESULT = {
    "raw_text": USER_INPUT,
    "subsystem": "battery",
    "task_type": "fault_diagnosis",
    "symptoms": [
        "第36号单体电压比其他单体低180 mV"
    ],
    "operating_conditions": [],
    "user_hypotheses": [],
    "requested_outputs": [],
    "missing_information": [
        "其他单体电压",
        "电池包电流",
        "SOC",
    ],
    "severity": "medium",
    "confidence": 0.92,
}


def make_response(
    content: str | None,
    *,
    finish_reason: str = "stop",
) -> SimpleNamespace:
    """构造假的DeepSeek响应。"""

    return SimpleNamespace(
        id="mock-response-id",
        choices=[
            SimpleNamespace(
                finish_reason=finish_reason,
                message=SimpleNamespace(
                    content=content,
                ),
            )
        ],
        usage=SimpleNamespace(
            prompt_tokens=100,
            completion_tokens=50,
            total_tokens=150,
        ),
    )


def make_fake_api_client(
    *,
    return_value: object | None = None,
    side_effect: object | None = None,
) -> SimpleNamespace:
    """
    构造具有chat.completions.create的Mock客户端。

    return_value:
        每次调用都返回同一个结果。

    side_effect:
        可以是异常、函数或多个返回结果组成的列表。
    """

    create_mock = Mock(
        return_value=return_value,
        side_effect=side_effect,
    )

    return SimpleNamespace(
        chat=SimpleNamespace(
            completions=SimpleNamespace(
                create=create_mock,
            )
        )
    )


def make_llm_client(
    fake_api_client: SimpleNamespace,
    *,
    max_attempts: int = 3,
    sleep_mock: Mock | None = None,
) -> LLMClient:
    """构造用于测试的LLMClient。"""

    return LLMClient(
        client=fake_api_client,
        model="deepseek-v4-flash",
        retry_config=RetryConfig(
            max_attempts=max_attempts,
            base_delay_seconds=0.01,
            max_delay_seconds=0.1,
            jitter_ratio=0.0,
        ),
        sleep_func=sleep_mock or Mock(),
        random_func=lambda: 0.5,
    )


# 第一个测试：验证“正常成功”路径
def test_parse_structured_success() -> None:
    """合法响应应直接转换为Pydantic对象。"""

    response = make_response(
        json.dumps(
            VALID_RESULT,
            ensure_ascii=False,
        )
    )

    fake_api_client = make_fake_api_client(
        return_value=response,
    )

    client = make_llm_client(
        fake_api_client,
    )

    result = client.parse_structured(
        developer_prompt="输出JSON。",
        user_input=USER_INPUT,
        response_model=PowerSystemIssue,
    )

    assert isinstance(
        result,
        PowerSystemIssue,
    )

    assert result.subsystem.value == "battery"
    assert result.confidence == 0.92

    create_mock = (
        fake_api_client
        .chat
        .completions
        .create
    )

    assert create_mock.call_count == 1


# 第二个测试：验证“空响应会触发重试，重试后成功”
def test_empty_response_is_retried() -> None:
    """第一次为空时，应等待后进行第二次调用。"""

    empty_response = make_response("")
    valid_response = make_response(
        json.dumps(
            VALID_RESULT,
            ensure_ascii=False,
        )
    )

    fake_api_client = make_fake_api_client(
        side_effect=[
            empty_response,
            valid_response,
        ],
    )

    sleep_mock = Mock()

    client = make_llm_client(
        fake_api_client,
        max_attempts=3,
        sleep_mock=sleep_mock,
    )

    result = client.parse_structured(
        developer_prompt="输出JSON。",
        user_input=USER_INPUT,
        response_model=PowerSystemIssue,
    )

    assert result.subsystem.value == "battery"

    create_mock = (
        fake_api_client
        .chat
        .completions
        .create
    )

    assert create_mock.call_count == 2
    sleep_mock.assert_called_once_with(0.01)


# 第三个测试：验证“重试次数用完后最终失败”
def test_validation_error_retries_then_fails() -> None:
    """连续Schema错误达到上限后，应抛出异常。"""

    invalid_json = json.dumps(
        {
            "raw_text": USER_INPUT
        },
        ensure_ascii=False,
    )

    invalid_response_1 = make_response(
        invalid_json
    )

    invalid_response_2 = make_response(
        invalid_json
    )

    fake_api_client = make_fake_api_client(
        side_effect=[
            invalid_response_1,
            invalid_response_2,
        ],
    )

    sleep_mock = Mock()

    client = make_llm_client(
        fake_api_client,
        max_attempts=2,
        sleep_mock=sleep_mock,
    )

    with pytest.raises(
        LLMValidationError
    ):
        client.parse_structured(
            developer_prompt="输出JSON。",
            user_input=USER_INPUT,
            response_model=PowerSystemIssue,
        )

    create_mock = (
        fake_api_client
        .chat
        .completions
        .create
    )

    assert create_mock.call_count == 2
    assert sleep_mock.call_count == 1

# 第四个测试：验证“不可重试的错误不会被重试”
def test_authentication_error_is_not_retried() -> None:
    """认证错误属于配置错误，不应重复调用。"""

    fake_api_client = make_fake_api_client(
        side_effect=LLMAuthenticationError(
            "认证失败"
        ),
    )

    sleep_mock = Mock()

    client = make_llm_client(
        fake_api_client,
        max_attempts=3,
        sleep_mock=sleep_mock,
    )

    with pytest.raises(
        LLMAuthenticationError
    ):
        client.parse_structured(
            developer_prompt="输出JSON。",
            user_input=USER_INPUT,
            response_model=PowerSystemIssue,
        )

    create_mock = (
        fake_api_client
        .chat
        .completions
        .create
    )

    assert create_mock.call_count == 1
    sleep_mock.assert_not_called()