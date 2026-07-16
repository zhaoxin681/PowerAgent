"""单轮Tool Calling闭环演示。
展示一次完整的“用户提问->大模型选工具->”
"""

from __future__ import annotations

import argparse

from agent_core import (
    SkillRegistry,
    ToolCallDecision,
    ToolCallingRunner,
    ToolSelectionResponse,
)
from skills import create_default_skills


class DemoMockClient:
    """固定选择battery_analysis的演示客户端。"""

    def request_tool_call(
        self,
        *,
        developer_prompt: str,
        user_input: str,
        tools: list[dict[str, object]],
    ) -> ToolSelectionResponse:
        return ToolSelectionResponse(
            tool_calls=[
                ToolCallDecision(
                    call_id="mock-call-001",
                    tool_name="battery_analysis",
                    arguments_json=(
                        '{"cell_voltages_v":'
                        '[3.652,3.648,3.571,3.655],'
                        '"spread_threshold_v":0.05}'
                    ),
                )
            ]
        )


def create_registry() -> SkillRegistry:
    """创建包含默认动力系统Skills的Registry。"""

    registry = SkillRegistry()

    for skill in create_default_skills():
        registry.register(skill)

    return registry


def create_client(mode: str) -> object:
    """根据模式创建Mock或真实LLM客户端。"""

    if mode == "mock":
        return DemoMockClient()

    from agent_core.llm_client import LLMClient

    return LLMClient()


def main() -> None:
    """运行Tool Calling演示。"""

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--mode",
        choices=("mock", "real"),
        default="mock",
    ) # 限制智能传入mock或real之一
    args = parser.parse_args()

    runner = ToolCallingRunner(
        registry=create_registry(),
        client=create_client(args.mode),
    )

    result = runner.run(
        "请分析单体电压3.652、3.648、3.571和3.655 V，"
        "压差阈值设为0.05 V。"
    )

    print(result.model_dump_json(indent=2))


if __name__ == "__main__":
    main()