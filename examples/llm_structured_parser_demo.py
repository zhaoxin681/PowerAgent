"""调用真实LLM解析动力系统问题。"""

import json

from agent_core.issue_parser import PowerSystemIssueParser
from agent_core.llm_client import LLMClientError


DEMO_INPUT = """
车辆行驶过程中，第36号单体电压比其他单体低180 mV，
且压差持续扩大。请分析可能的问题，并给出需要补充的数据。
""".strip()


def main() -> None:
    parser = PowerSystemIssueParser()

    try:
        issue = parser.parse(DEMO_INPUT)

    except ValueError as exc:
        print(f"配置错误：{exc}")
        return

    except LLMClientError as exc:
        print(f"LLM调用失败：{exc}")
        return

    output = issue.model_dump(mode="json")

    print("结构化解析成功：")
    print(json.dumps(output, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()