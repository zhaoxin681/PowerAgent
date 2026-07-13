"""动力系统问题结构化解析器。"""

from agent_core.llm_client import LLMClient
from agent_core.prompts import POWER_SYSTEM_ISSUE_PARSER_PROMPT
from agent_core.schemas import PowerSystemIssue


class PowerSystemIssueParser:
    """将自然语言转换为PowerSystemIssue对象。"""

    # 可以主动传入/自动创建全新，依赖注入，方便测试时不消耗api
    def __init__(self, llm_client: LLMClient | None = None) -> None:
        self.llm_client = llm_client or LLMClient()

    def parse(self, user_input: str) -> PowerSystemIssue:
        """
        解析用户输入的动力系统问题。

        Args:
            user_input:
                用户输入的异常描述、研发问题或分析请求。

        Returns:
            PowerSystemIssue:
                标准化动力系统问题对象。
        """

        return self.llm_client.parse_structured(
            developer_prompt=POWER_SYSTEM_ISSUE_PARSER_PROMPT,
            user_input=user_input,
            response_model=PowerSystemIssue,
        )