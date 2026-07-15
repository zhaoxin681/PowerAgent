"""PowerAgent skill system共享数据契约. 使用Pydantic来做数据校验和结构化"""

from __future__ import annotations

from typing import Any
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field

from enum import Enum


# 每次技能调用时的运行时上下文（元数据）
class SkillContext(BaseModel):
    """Runtime context passed to a skill invocation.

    The context contains invocation-level metadata rather than business input.
    Business parameters must be defined in each skill's dedicated input model.
    """

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
    )  # 不允许传入模型字段之外的额外字段

    trace_id: str = Field(
        default_factory=lambda: uuid4().hex,
        min_length=1,
        description="Unique identifier used to trace one skill invocation.",
    )  # 唯一追踪ID
    source: str = Field(
        default="direct",
        min_length=1,
        description="Source that initiated the skill invocation.",
    )  # 标识这次调用是从哪里发起的
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Optional invocation-level metadata.",
    )  # 自由格式的字典，存放额外的、非结构化的调用级元数据


# 表示一个技能的“注册信息”/静态元数据
class SkillDefinition(BaseModel):
    """Stable metadata describing a reusable skill."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
    )

    name: str = Field(
        pattern=r"^[a-z][a-z0-9_]*$",
        description="Unique snake_case name used by the registry and LLM tools.",
    ) # 唯一名字必须小写字母开头，只能包含小写字母、数字、下划线
    description: str = Field(
        min_length=1,
        description="Human-readable explanation of when the skill should be used.",
    ) # 功能描述
    version: str = Field(
        default="1.0.0",
        pattern=r"^\d+\.\d+\.\d+$",
        description="Semantic version of the skill.",
    ) # 版本号
    input_model_name: str = Field(
        min_length=1,
        description="Name of the Pydantic model used to validate skill input.",
    )
    output_model_name: str = Field(
        min_length=1,
        description="Name of the Pydantic model used to validate skill output.",
    ) # 用于校验该技能调用时传入/传出的数据结构


class RiskLevel(str, Enum):
    """Skill统一使用的风险等级。"""

    NORMAL = "normal"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class RecommendedAction(str, Enum):
    """充电分析Skill的建议动作。"""

    CONTINUE_CHARGING = "continue_charging"
    REDUCE_POWER = "reduce_power"
    STOP_CHARGING = "stop_charging"