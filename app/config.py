"""PowerAgent FastAPI运行配置。负责统一管理服务启动所需的各项配置参数
（端口、日志、运行环境等），并支持从环境变量/.env文件加载"""

from __future__ import annotations

import os
from enum import Enum
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv
from pydantic import (
    Field,
    field_validator,
    model_validator,
)

from agent_core.schemas import StrictBaseModel


class RuntimeEnvironment(str, Enum):
    """PowerAgent API运行环境。"""

    DEVELOPMENT = "development"
    TEST = "test"
    PRODUCTION = "production"

class EmbeddingBackend(str, Enum):
    """PowerAgent知识库使用的Embedding类型。"""

    CHROMA_DEFAULT = "chroma_default"  # 供本地真实知识查询使用
    HASH = "hash"    # 供离线测试和确定性验证使用

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

    chroma_path: Path = Field(
        default=Path("data/chroma"),
        description="生产Chroma向量知识库目录",
    )

    chroma_collection: str = Field(
        default="poweragent_knowledge",
        min_length=1,
        description="生产知识库集合名称",
    )

    embedding_backend: EmbeddingBackend = Field(
        default=EmbeddingBackend.CHROMA_DEFAULT,
        description="知识库使用的Embedding实现",
    )

    hash_embedding_dimension: int = Field(
        default=256,
        ge=32,
        le=4096,
        description="Hash Embedding向量维度",
    )

    max_replans: int = Field(
        default=1,
        ge=0,
        le=5,
        description="工作流允许的最大重新规划次数",
    )

    llm_max_tokens: int = Field(
        default=4096,
        ge=512,
        le=32768,
        description="LLM单次结构化输出允许的最大token数",
    )

    max_upload_mb: int = Field(
        default=20,
        ge=1,
        le=200,
        description="单个上传文件的最大体积，单位MB",
    )

    upload_temp_dir: Path = Field(
        default=Path("data/uploads/tmp"),
        description="上传文件的受控临时目录",
    )

    document_chunk_size: int = Field(
        default=600,
        ge=100,
        le=5000,
        description="知识文档切分块的最大字符数",
    )

    document_chunk_overlap: int = Field(
        default=80,
        ge=0,
        le=1000,
        description="相邻知识块的重叠字符数",
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

    @model_validator(mode="after")
    def validate_document_split_settings(
        self,
    ) -> "AppSettings":
        """文档重叠长度必须小于单块长度。"""

        if (
            self.document_chunk_overlap
            >= self.document_chunk_size
        ):
            raise ValueError(
                "document_chunk_overlap必须小于"
                "document_chunk_size"
            )

        return self

    @property
    def max_upload_bytes(self) -> int:
        """将上传文件上限转换为字节。"""

        return (
            self.max_upload_mb
            * 1024
            * 1024
        )

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
                "chroma_path": os.getenv(
                    "POWERAGENT_CHROMA_PATH",
                    "data/chroma",
                ),
                "chroma_collection": os.getenv(
                    "POWERAGENT_CHROMA_COLLECTION",
                    "poweragent_knowledge",
                ),
                "embedding_backend": os.getenv(
                    "POWERAGENT_EMBEDDING_BACKEND",
                    "chroma_default",
                ),
                "hash_embedding_dimension": os.getenv(
                    "POWERAGENT_HASH_EMBEDDING_DIMENSION",
                    "256",
                ),
                "max_replans": os.getenv(
                    "POWERAGENT_MAX_REPLANS",
                    "1",
                ),
                "llm_max_tokens": os.getenv(
                    "POWERAGENT_LLM_MAX_TOKENS",
                    "4096",
                ),
                "max_upload_mb": os.getenv(
                    "POWERAGENT_MAX_UPLOAD_MB",
                    "20",
                ),
                "upload_temp_dir": os.getenv(
                    "POWERAGENT_UPLOAD_TEMP_DIR",
                    "data/uploads/tmp",
                ),
                "document_chunk_size": os.getenv(
                    "POWERAGENT_DOCUMENT_CHUNK_SIZE",
                    "600",
                ),
                "document_chunk_overlap": os.getenv(
                    "POWERAGENT_DOCUMENT_CHUNK_OVERLAP",
                    "80",
                ),
            }
        )


@lru_cache(maxsize=1)
def get_settings() -> AppSettings:
    """创建并缓存API配置。"""

    return AppSettings.from_env()
