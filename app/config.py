"""PowerAgent FastAPI运行配置。负责统一管理服务启动所需的各项配置参数
（端口、日志、运行环境等），并支持从环境变量/.env文件加载"""

from __future__ import annotations

import os
from enum import Enum
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv
from pydantic import Field, field_validator

from agent_core.schemas import StrictBaseModel


class RuntimeEnvironment(str, Enum):
    """PowerAgent API运行环境。"""

    DEVELOPMENT = "development"
    TEST = "test"
    PRODUCTION = "production"


# 配置模型本体
class AppSettings(StrictBaseModel):
    """PowerAgent API服务配置。"""

    service_name: str = Field(
        default="PowerAgent",
        min_length=1,
        description="API服务名称",
    )

    service_version: str = Field(
        default="0.1.0",
        min_length=1,
        description="API服务版本",
    )

    environment: RuntimeEnvironment = Field(
        default=RuntimeEnvironment.DEVELOPMENT,
        description="API运行环境",
    )

    api_prefix: str = Field(
        default="/api/v1",
        min_length=1,
        description="业务接口统一前缀",
    )

    host: str = Field(
        default="127.0.0.1",  # 仅本机可访问
        min_length=1,
        description="Uvicorn监听地址",
    )

    port: int = Field(
        default=8000,
        ge=1,
        le=65535,
        description="Uvicorn监听端口",
    )

    log_level: str = Field(
        default="INFO",
        min_length=1,
        description="PowerAgent日志等级",
    )

    log_dir: Path = Field(
        default=Path("logs"),
        description="结构化日志保存目录",
    )

    # 字段校验器
    @field_validator("api_prefix")
    @classmethod
    def validate_api_prefix(
        cls,
        value: str,
    ) -> str:
        """API前缀必须以斜杠开头且不能以斜杠结尾。"""

        if not value.startswith("/"):
            raise ValueError(
                "api_prefix必须以/开头"
            )

        if len(value) > 1 and value.endswith("/"):
            raise ValueError(
                "api_prefix不能以/结尾"
            )

        return value

    @field_validator("log_level")
    @classmethod
    def validate_log_level(
        cls,
        value: str,
    ) -> str:
        """规范化并校验日志等级。"""

        normalized = value.upper()

        allowed_levels = {
            "DEBUG",
            "INFO",
            "WARNING",
            "ERROR",
            "CRITICAL",
        }

        if normalized not in allowed_levels:
            raise ValueError(
                "log_level必须是合法日志等级"
            )

        return normalized

    @classmethod
    def from_env(cls) -> "AppSettings":
        """从.env和操作系统环境变量加载配置。"""

        load_dotenv()

        return cls.model_validate(
            {
                "service_name": os.getenv(
                    "POWERAGENT_SERVICE_NAME",
                    "PowerAgent",
                ),
                "service_version": os.getenv(
                    "POWERAGENT_SERVICE_VERSION",
                    "0.1.0",
                ),
                "environment": os.getenv(
                    "POWERAGENT_ENV",
                    "development",
                ),
                "api_prefix": os.getenv(
                    "POWERAGENT_API_PREFIX",
                    "/api/v1",
                ),
                "host": os.getenv(
                    "POWERAGENT_HOST",
                    "127.0.0.1",
                ),
                "port": os.getenv(
                    "POWERAGENT_PORT",
                    "8000",
                ),
                "log_level": os.getenv(
                    "POWERAGENT_LOG_LEVEL",
                    "INFO",
                ),
                "log_dir": os.getenv(
                    "POWERAGENT_LOG_DIR",
                    "logs",
                ),
            }
        )


@lru_cache(maxsize=1)
def get_settings() -> AppSettings:
    """创建并缓存API配置。"""

    return AppSettings.from_env()