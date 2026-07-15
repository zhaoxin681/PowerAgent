"""动力系统基础知识查询Skill。"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from skills.base_skill import BaseSkill
from skills.schemas import SkillContext


class KnowledgeLookupInput(BaseModel):
    """知识查询输入。"""

    model_config = ConfigDict(extra="forbid")

    term: str = Field(
        min_length=1,
        description="需要查询的动力系统术语。",
    )


class KnowledgeLookupOutput(BaseModel):
    """知识查询输出。"""

    model_config = ConfigDict(extra="forbid")

    found: bool
    canonical_term: str | None
    category: str | None
    explanation: str | None
    source: str


# 内置知识库（私有常量）
_KNOWLEDGE_BASE: dict[str, dict[str, Any]] = {
    "soc": {
        "aliases": ["荷电状态", "state of charge"],
        "category": "battery_state",
        "explanation": (
            "SOC表示电池剩余可用容量与当前可用总容量的比值，"
            "通常以百分比表示。"
        ),
    },
    "soh": {
        "aliases": ["健康状态", "state of health"],
        "category": "battery_state",
        "explanation": (
            "SOH用于描述电池相对于初始状态的健康程度，"
            "常结合容量和内阻等指标评估。"
        ),
    },
    "bms": {
        "aliases": ["电池管理系统", "battery management system"],
        "category": "battery_management",
        "explanation": (
            "BMS负责电池状态监测、状态估计、安全保护、"
            "均衡控制和通信管理。"
        ),
    },
    "thermal_runaway": {
        "aliases": ["热失控", "thermal runaway"],
        "category": "battery_safety",
        "explanation": (
            "热失控是电池内部放热反应持续加速并导致温度"
            "快速升高的危险状态。"
        ),
    },
}


# 技能实现
class KnowledgeLookupSkill(
    BaseSkill[KnowledgeLookupInput, KnowledgeLookupOutput]
):
    """查询内置动力系统基础知识。"""

    name = "knowledge_lookup"
    description = "查询动力系统基础术语的定义和所属类别。"

    input_model = KnowledgeLookupInput
    output_model = KnowledgeLookupOutput

    def execute(
        self,
        skill_input: KnowledgeLookupInput,
        context: SkillContext,
    ) -> dict[str, Any]:
        # 1. 归一化输入
        normalized_term = skill_input.term.strip().lower()
        # 2. 遍历知识库，逐条构建候选匹配集合
        for canonical_term, item in _KNOWLEDGE_BASE.items():
            candidates = {
                canonical_term.lower(),
                *(
                    alias.lower()
                    for alias in item["aliases"]
                ),
            } # 对知识库中的每个条目构建一个集合
            # 3. 命中判断
            if normalized_term in candidates:
                return {
                    "found": True,
                    "canonical_term": canonical_term,
                    "category": item["category"],
                    "explanation": item["explanation"],
                    "source": "built_in_dictionary",
                }
        # 4. 遍历完没匹配到，返回未找到
        return {
            "found": False,
            "canonical_term": None,
            "category": None,
            "explanation": None,
            "source": "built_in_dictionary",
        }