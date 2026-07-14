"""结构化日志格式测试。"""

import json
import logging

from agent_core.logging_config import JsonFormatter

# 重点验证“自定义扩展字段（extra部分）能否被正确捕获”
def test_json_formatter_returns_valid_json() -> None:
    """日志输出必须是合法JSON。"""

    # 单独测试“格式化器”这一环节，选择绕过整个logger系统，直接手工构造一个LogRecord专门喂给JsonFormatter测试
    record = logging.LogRecord(
        name="poweragent.test",
        level=logging.INFO,
        pathname=__file__,
        lineno=10,
        msg="测试日志",
        args=(),
        exc_info=None,
    )

    record.event = "unit_test"
    record.request_id = "request-001"
    record.latency_ms = 125.5

    output = JsonFormatter().format(record) # 创建一个JsonFormatter实例，得到一个JSON格式的字符串

    payload = json.loads(output) # 将JSON字符串反过来解析成一个Python字典，方便后面断言检查

    assert payload["level"] == "INFO"
    assert payload["message"] == "测试日志"
    assert payload["event"] == "unit_test"
    assert payload["request_id"] == "request-001"
    assert payload["latency_ms"] == 125.5

# 重点测试时间戳格式是否符合规范
def test_json_formatter_contains_timestamp() -> None:
    """每条日志都必须包含时间戳。"""

    record = logging.LogRecord(
        name="poweragent.test",
        level=logging.WARNING,
        pathname=__file__,
        lineno=20,
        msg="重试测试",
        args=(),
        exc_info=None,
    )

    output = JsonFormatter().format(record)
    payload = json.loads(output)

    assert "timestamp" in payload
    assert payload["timestamp"].endswith("Z")