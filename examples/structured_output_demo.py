"""PowerAgent结构化输出校验示例。"""

from pydantic import ValidationError

from agent_core.schemas import PowerSystemIssue


VALID_DATA = {
    "raw_text": (
        "车辆快充过程中，电池最高温度从35℃上升到48℃，"
        "充电功率随后下降。请分析可能原因并生成诊断建议。"
    ),
    "subsystem": "thermal",
    "task_type": "fault_diagnosis",
    "symptoms": [
        "快充过程中电池最高温度快速上升",
        "充电功率下降",
    ],
    "operating_conditions": [
        {
            "name": "初始最高温度",
            "value": "35",
            "unit": "℃",
        },
        {
            "name": "异常最高温度",
            "value": "48",
            "unit": "℃",
        },
        {
            "name": "运行场景",
            "value": "直流快充",
            "unit": "",
        },
    ],
    "user_hypotheses": [],
    "requested_outputs": [
        "异常原因分析",
        "补充检查项目",
        "诊断建议",
    ],
    "missing_information": [
        "冷却液入口温度",
        "冷却液流量",
        "各电池模组温差",
    ],
    "severity": "high",
    "confidence": 0.88,
} # 普通字典


INVALID_DATA = {
    **VALID_DATA,
    "confidence": 1.25,
    "unexpected_field": "该字段不应被接受",
} # 字典解包


def validate_issue(data: dict) -> None:
    """校验并打印动力系统问题对象。"""

    try:
        issue = PowerSystemIssue.model_validate(data)

        print("数据校验通过：")
        print(issue.model_dump_json(indent=2))

    except ValidationError as exc:
        print("数据校验失败：")
        print(exc)


if __name__ == "__main__":
    print("=" * 60)
    print("测试1：合法数据")
    print("=" * 60)
    validate_issue(VALID_DATA)

    print("\n" + "=" * 60)
    print("测试2：非法数据")
    print("=" * 60)
    validate_issue(INVALID_DATA)