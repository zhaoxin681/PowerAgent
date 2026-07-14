"""PowerAgent结构化日志配置。遵循统一的结构化JSON格式"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any


LOGGER_NAME = "poweragent"  # 全局常量，项目日志系统根名字


STANDARD_LOG_RECORD_FIELDS = {
    "name",
    "msg",
    "args",
    "levelname",
    "levelno",
    "pathname",
    "filename",
    "module",
    "exc_info",
    "exc_text",
    "stack_info",
    "lineno",
    "funcName",
    "created",
    "msecs",
    "relativeCreated",
    "thread",
    "threadName",
    "processName",
    "process",
    "taskName",
    "message",
    "asctime",
}


def make_json_safe(value: Any) -> Any:
    """将日志扩展字段转换为可JSON序列化的值。"""

    try:
        json.dumps(value, ensure_ascii=False)
        return value
    except TypeError:
        return str(value)


class JsonFormatter(logging.Formatter):
    """将Python日志记录格式化为单行JSON。"""

    def format(self, record: logging.LogRecord) -> str:
        timestamp = datetime.fromtimestamp(
            record.created,  # 日志记录创建时时间戳
            tz=timezone.utc,  # 指定UTC时区
        ).isoformat(timespec="milliseconds").replace(
            "+00:00",
            "Z",
        ) # 转换成标准字符串

        # 构造一个字典，最终JSON输出基础骨架
        payload: dict[str, Any] = {
            "timestamp": timestamp,
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        # 日志调用时附加自定义扩展字段也补充进最终JSON
        for key, value in record.__dict__.items():
            if key in STANDARD_LOG_RECORD_FIELDS:
                continue

            if key.startswith("_"):
                continue

            payload[key] = make_json_safe(value)

        if record.exc_info:
            payload["exception"] = self.formatException(
                record.exc_info
            ) # 异常处理

        return json.dumps(
            payload,
            ensure_ascii=False,
            separators=(",", ":"),
        )


# 搭建整个日志系统：创建logger-配置格式-绑定输出目的地。
def configure_logging(
    *,
    log_dir: str | Path | None = None,
    level: str | None = None,
    force: bool = False,
) -> logging.Logger:
    """
    配置PowerAgent日志。

    日志同时输出到：
    1. 控制台；
    2. logs/poweragent.jsonl。
    """

    resolved_log_dir = Path(
        log_dir
        or os.getenv("POWERAGENT_LOG_DIR")
        or "logs"
    ) # 目录

    level_name = (
        level
        or os.getenv("POWERAGENT_LOG_LEVEL")
        or "INFO"
    ).upper() # 日志级别

    level_value = getattr(
        logging,
        level_name,
        logging.INFO,
    )  # 安全兜底

    # 创建logger对象
    logger = logging.getLogger(LOGGER_NAME)

    if force:
        for handler in logger.handlers[:]:
            handler.close()
            logger.removeHandler(handler)

        setattr(logger, "_poweragent_configured", False)
    # 防重复配置
    if getattr(logger, "_poweragent_configured", False):
        return logger

    # 创建handler并绑定
    resolved_log_dir.mkdir(
        parents=True,
        exist_ok=True,
    ) # 确保日志目录存在

    formatter = JsonFormatter() # 创建实例，作为格式化器

    console_handler = logging.StreamHandler() # 默认会把日志输出到终端
    console_handler.setLevel(level_value)
    console_handler.setFormatter(formatter)

    file_handler = RotatingFileHandler(
        filename=resolved_log_dir / "poweragent.jsonl",
        maxBytes=5 * 1024 * 1024,
        backupCount=3,
        encoding="utf-8",
    ) # 滚动文件处理器，限制日志文件总体积上限20MB

    file_handler.setLevel(level_value)  # 低于该级别的日志会丢弃，不传给任何hanlder
    file_handler.setFormatter(formatter)

    logger.setLevel(level_value)
    logger.propagate = False # 防止重复输出

    logger.addHandler(console_handler) # 每条日志会同时被这两个handler处理
    logger.addHandler(file_handler)

    setattr(logger, "_poweragent_configured", True)  # 防重复

    return logger


def get_logger(module_name: str) -> logging.Logger:
    """获取PowerAgent子模块日志对象。简化调用入口"""

    root_logger = configure_logging()  # 配置好日志系统
    return root_logger.getChild(module_name) # 支持显示日志来源模块