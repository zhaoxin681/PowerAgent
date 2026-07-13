"""检查PowerSystemIssue是否满足结构化输出要求。"""

from agent_core.schemas import PowerSystemIssue


# 检验必填字段集合和全部字段集合完全相等
def test_all_root_fields_are_required() -> None:
    schema = PowerSystemIssue.model_json_schema()

    property_names = set(schema["properties"].keys())
    required_names = set(schema["required"])

    assert required_names == property_names


# 禁止额外字段
def test_extra_fields_are_forbidden() -> None:   
    schema = PowerSystemIssue.model_json_schema()

    assert schema["additionalProperties"] is False


# 针对嵌套模型再测试一遍
def test_operating_condition_fields_are_required() -> None:
    schema = PowerSystemIssue.model_json_schema()
    operating_condition_schema = schema["$defs"]["OperatingCondition"]

    property_names = set(
        operating_condition_schema["properties"].keys()
    )
    required_names = set(
        operating_condition_schema["required"]
    )

    assert required_names == property_names
    assert operating_condition_schema["additionalProperties"] is False