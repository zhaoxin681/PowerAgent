"""PowerAgent核心结构化数据模型。(用大模型做结构化信息抽取)"""

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class StrictBaseModel(BaseModel):
    """PowerAgent所有结构化模型的基础类。"""

    model_config = ConfigDict(
        extra="forbid",     # 禁止传入模型里没有定义过的多余字段
        str_strip_whitespace=True,     # 所有字符串字段在赋值时，会自动去除首尾空格
        validate_assignment=True,    # 每次修改字段值重新检验
    )  # 统一定义严格规则，之后所有模型都继承这个类

"""
三个枚举类，定义只能是其中之一。枚举从根据上保证数据一致性
"""
class Subsystem(str, Enum):
    """动力系统子系统。"""

    BATTERY = "battery"
    ELECTRIC_DRIVE = "electric_drive"
    THERMAL = "thermal"
    CHARGING = "charging"
    MULTI_SYSTEM = "multi_system"
    UNKNOWN = "unknown"


class TaskType(str, Enum):
    """用户请求对应的Agent任务类型。"""

    KNOWLEDGE_QUERY = "knowledge_query"
    DATA_ANALYSIS = "data_analysis"
    FAULT_DIAGNOSIS = "fault_diagnosis"
    PARAMETER_OPTIMIZATION = "parameter_optimization"
    RND_ANALYSIS = "rnd_analysis"
    REPORT_GENERATION = "report_generation"
    UNKNOWN = "unknown"


class Severity(str, Enum):
    """问题严重程度。"""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"
    UNKNOWN = "unknown"


class OperatingCondition(StrictBaseModel):
    """动力系统运行条件。"""

    name: str = Field(
        min_length=1,
        description="运行条件名称，例如环境温度、SOC或充电倍率",
    )
    value: str = Field(
        min_length=1,
        description="运行条件数值，统一保留为字符串",
    )
    unit: str = Field(
        default="",
        description="运行条件单位，例如℃、A、V或%",
    )


class PowerSystemIssue(StrictBaseModel):
    """用户输入经过解析后形成的动力系统问题对象。"""

    raw_text: str = Field(
        min_length=1,
        description="用户原始问题或异常现象描述",
    )

    subsystem: Subsystem = Field(
        description="异常所属的动力系统子系统",
    )

    task_type: TaskType = Field(
        description="用户希望PowerAgent执行的任务类型",
    )

    symptoms: list[str] = Field(
        default_factory=list,
        description="从用户输入中提取出的异常现象",
    )

    operating_conditions: list[OperatingCondition] = Field(
        default_factory=list,
        description="异常发生时的运行条件",
    )

    user_hypotheses: list[str] = Field(
        default_factory=list,
        description="用户明确提出的可能原因，不是Agent生成的诊断结论",
    )

    requested_outputs: list[str] = Field(
        default_factory=list,
        description="用户要求生成的分析结果或交付物",
    )

    missing_information: list[str] = Field(
        default_factory=list,
        description="完成任务仍然缺少的信息",
    )

    severity: Severity = Field(
        default=Severity.UNKNOWN,
        description="异常严重程度",
    )

    confidence: float = Field(
        ge=0.0,
        le=1.0,
        description="结构化解析结果的置信度",
    )