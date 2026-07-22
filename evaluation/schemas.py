"""PowerAgent统一评测数据契约。"""

from __future__ import annotations

from enum import Enum
from typing import Any, Literal

from pydantic import (
    Field,
    field_validator,
    model_validator,
)

from agent_core.schemas import (
    Severity,
    StrictBaseModel,
    Subsystem,
    TaskType,
)
from agent_core.workflow_models import (
    ReportStatus,
    ReviewStatus,
)

from agent_core.router_agent import RouteStatus


# 字段名字面量类型
IssueListField = Literal[
    "symptoms",
    "operating_conditions",
    "user_hypotheses",
    "requested_outputs",
    "missing_information",
]


# 评测器类型枚举
class EvaluatorType(str, Enum):
    """统一测试集支持的评测器类型。"""

    ISSUE_PARSER = "issue_parser"
    ROUTER = "router"
    SKILL_CALL = "skill_call"
    RAG = "rag"
    REPORT = "report"


# 概念期望
class ConceptExpectation(StrictBaseModel):
    """某个结构化字段必须覆盖的一组同义表达。"""

    field_name: IssueListField

    alternatives: list[str] = Field(
        min_length=1,
        description=(
            "同一概念允许出现的不同表达；"
            "命中任意一个即认为该概念通过"
        ),
    )

    @field_validator("alternatives")
    @classmethod
    def validate_alternatives(
        cls,
        value: list[str],
    ) -> list[str]:
        """禁止空字符串和重复表达污染评测结果。"""

        if any(not item.strip() for item in value):
            raise ValueError(
                "alternatives不能包含空字符串"
            )

        if len(set(value)) != len(value):
            raise ValueError(
                "alternatives不能包含重复表达"
            )

        return value


# 问题解析的整体期望
class IssueExpectation(StrictBaseModel):
    """PowerSystemIssue结构化解析的期望结果。"""

    subsystem: Subsystem

    task_type: TaskType

    severity_allowed: list[Severity] = Field(
        min_length=1,
        description="允许接受的严重程度结果",
    )

    required_concepts: list[
        ConceptExpectation
    ] = Field(
        default_factory=list,
        description="各结构化字段必须覆盖的关键概念",
    )

    must_be_empty: list[IssueListField] = Field(
        default_factory=list,
        description="必须保持为空列表的字段",
    )

    exact_raw_text: bool = Field(
        default=True,
        description="是否要求raw_text完全保留原始输入",
    )

    @model_validator(mode="after") # 所有字段检验完之后再执行
    def validate_unique_fields(
        self,
    ) -> "IssueExpectation":
        """禁止重复声明空字段。"""

        if (
            len(set(self.must_be_empty))
            != len(self.must_be_empty)
        ):
            raise ValueError(
                "must_be_empty不能包含重复字段"
            )

        return self


class RouterIssueInput(StrictBaseModel):
    """Router评测使用的最小结构化问题输入。"""

    subsystem: Subsystem

    task_type: TaskType

    severity: Severity = Severity.LOW

    missing_information: list[str] = Field(
        default_factory=list,
        description="进入Router前已经识别出的缺失信息",
    )


# 路由期望
class RouteExpectation(StrictBaseModel):
    """Router Agent输入和期望输出。"""

    issue: RouterIssueInput

    route: TaskType

    status: RouteStatus

    needs_human_review: bool

    required_missing_information: list[str] = Field(
        default_factory=list,
        description=(
            "Router输出中必须出现的新增或保留缺失信息"
        ),
    )

    @field_validator(
        "required_missing_information"
    )
    @classmethod
    def validate_required_missing_information(
        cls,
        value: list[str],
    ) -> list[str]:
        """缺失信息要求不能包含空值或重复值。"""

        if any(not item.strip() for item in value):
            raise ValueError(
                "required_missing_information"
                "不能包含空字符串"
            )

        if len(set(value)) != len(value):
            raise ValueError(
                "required_missing_information"
                "不能包含重复项"
            )

        return value
    

# 工具调用期望
class SkillCallExpectation(StrictBaseModel):
    """Tool Calling期望结果。"""

    should_call_tool: bool = Field(
        default=True,
        description="当前问题是否应该调用Skill",
    )

    expected_skill: str | None = Field(
        default=None,
        min_length=1,
        description=(
            "期望调用的Skill名称；"
            "不应调用Skill时为None"
        ),
    )

    expected_argument_keys: list[str] = Field(
        default_factory=list,
        description="期望生成的必要参数名称",
    )

    expected_status: str = Field(
        min_length=1,
        description="期望的Tool Calling状态",
    )

    @model_validator(mode="after")
    def validate_call_expectation(
        self,
    ) -> "SkillCallExpectation":
        """校验调用状态与期望Skill的一致性。"""

        if (
            self.should_call_tool
            and self.expected_skill is None
        ):
            raise ValueError(
                "should_call_tool为true时"
                "必须提供expected_skill"
            )

        if (
            not self.should_call_tool
            and self.expected_skill is not None
        ):
            raise ValueError(
                "should_call_tool为false时"
                "expected_skill必须为None"
            )

        if (
            not self.should_call_tool
            and self.expected_argument_keys
        ):
            raise ValueError(
                "不调用工具时不能声明"
                "expected_argument_keys"
            )

        if (
            len(set(self.expected_argument_keys))
            != len(self.expected_argument_keys)
        ):
            raise ValueError(
                "expected_argument_keys不能重复"
            )

        return self

# 检索增强生成期望
class RAGExpectation(StrictBaseModel):
    """RAG检索与回答的期望结果。"""

    should_answer: bool

    should_refuse: bool

    top_k: int = Field(
        default=3,
        ge=1,
        le=20,
        description="计算知识命中率时使用的K值",
    )

    expected_chunk_ids: list[str] = Field(
        default_factory=list,
        description="期望命中的知识块ID",
    )

    expected_source_keywords: list[str] = Field(
        default_factory=list,
        description="期望来源中包含的关键词",
    )

    required_answer_concepts: list[
        list[str]
    ] = Field(
        default_factory=list,
        description=(
            "回答必须覆盖的概念组；"
            "每组命中任意表达即可"
        ),
    )

    forbidden_claims: list[str] = Field(
        default_factory=list,
        description="回答中禁止出现的无证据结论",
    )

    @field_validator("required_answer_concepts")
    @classmethod
    def validate_answer_concepts(
        cls,
        value: list[list[str]],
    ) -> list[list[str]]:
        """概念组必须包含至少一个有效表达。"""

        for group in value:
            if (
                not group
                or any(
                    not item.strip()
                    for item in group
                )
            ):
                raise ValueError(
                    "required_answer_concepts中的"
                    "每组概念都必须包含非空表达"
                )

        return value

    @model_validator(mode="after")
    def validate_answer_mode(
        self,
    ) -> "RAGExpectation":
        """RAG必须明确选择回答或拒答。"""

        if self.should_answer == self.should_refuse:
            raise ValueError(
                "should_answer与should_refuse"
                "必须且只能有一个为true"
            )

        return self

# 报告/复核阶段期望
class ReportExpectation(StrictBaseModel):
    """Review和Report阶段的期望结果。"""

    should_generate: bool

    expected_review_status: (
        ReviewStatus | None
    ) = None

    expected_report_status: (
        ReportStatus | None
    ) = None

    needs_human_review: bool | None = None

    required_fields: list[str] = Field(
        default_factory=list,
        description="报告必须包含的结构化字段",
    )

    required_concepts: list[list[str]] = Field(
        default_factory=list,
        description="最终报告必须覆盖的概念组",
    )

    forbidden_claims: list[str] = Field(
        default_factory=list,
        description="报告中禁止出现的无依据结论",
    )

    @field_validator("required_concepts")
    @classmethod
    def validate_required_concepts(
        cls,
        value: list[list[str]],
    ) -> list[list[str]]:
        """禁止空概念组。"""

        for group in value:
            if (
                not group
                or any(
                    not item.strip()
                    for item in group
                )
            ):
                raise ValueError(
                    "required_concepts中的"
                    "每组概念都必须包含非空表达"
                )

        return value

    @model_validator(mode="after")
    def validate_report_status(
        self,
    ) -> "ReportExpectation":
        """报告生成标志必须与报告状态一致。"""

        if (
            self.should_generate
            and self.expected_report_status
            == ReportStatus.BLOCKED
        ):
            raise ValueError(
                "应生成报告时不能期望blocked状态"
            )

        if (
            not self.should_generate
            and self.expected_report_status
            == ReportStatus.GENERATED
        ):
            raise ValueError(
                "不应生成报告时不能期望generated状态"
            )

        return self
    

# 将前面的期望结果组装成完整的测试样本，并定义了跑完测评后如何记录单条结果和汇总统计
class EvaluationCase(StrictBaseModel):
    """PowerAgent统一评测样本。"""

    case_id: str = Field(
        min_length=1,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9_-]*$",
        description="测试样本唯一标识",
    )

    user_input: str = Field(
        min_length=1,
        description="输入PowerAgent的原始问题",
    )

    evaluators: list[EvaluatorType] = Field(
        min_length=1,
        description="需要执行该样本的评测器",
    )

    tags: list[str] = Field(
        default_factory=list,
        description="用于筛选和统计的场景标签",
    )

    issue_expectation: (
        IssueExpectation | None
    ) = None

    route_expectation: (
        RouteExpectation | None
    ) = None

    skill_expectation: (
        SkillCallExpectation | None
    ) = None

    rag_expectation: (
        RAGExpectation | None
    ) = None

    report_expectation: (
        ReportExpectation | None
    ) = None

    notes: str = Field(
        default="",
        description="人工标注说明",
    )

    @model_validator(mode="after")
    def validate_expectations(
        self,
    ) -> "EvaluationCase":
        """每个评测器必须具备对应期望结果。"""

        if (
            len(set(self.evaluators))
            != len(self.evaluators)
        ):
            raise ValueError(
                "evaluators不能包含重复值"
            )

        if len(set(self.tags)) != len(self.tags):
            raise ValueError(
                "tags不能包含重复值"
            )

        expectation_by_evaluator = {
            EvaluatorType.ISSUE_PARSER: (
                self.issue_expectation
            ),
            EvaluatorType.ROUTER: (
                self.route_expectation
            ),
            EvaluatorType.SKILL_CALL: (
                self.skill_expectation
            ),
            EvaluatorType.RAG: (
                self.rag_expectation
            ),
            EvaluatorType.REPORT: (
                self.report_expectation
            ),
        }

        missing = [
            evaluator.value
            for evaluator in self.evaluators
            if (
                expectation_by_evaluator[evaluator]
                is None
            )
        ]

        if missing:
            raise ValueError(
                "以下评测器缺少期望结果："
                + ", ".join(missing)
            )

        unexpected = [
            evaluator.value
            for evaluator, expectation
            in expectation_by_evaluator.items()
            if (
                expectation is not None
                and evaluator not in self.evaluators
            )
        ]

        if unexpected:
            raise ValueError(
                "以下期望结果未声明对应评测器："
                + ", ".join(unexpected)
            )

        return self

# 单项检查结果-最小粒度
class EvaluationCheck(StrictBaseModel):
    """单个指标或字段的检查结果。"""

    passed: bool

    expected: Any = None

    actual: Any = None

    detail: str = ""


class EvaluationCaseResult(StrictBaseModel):
    """单个评测器对单条样本的结果。"""

    case_id: str = Field(
        min_length=1,
    )

    evaluator: EvaluatorType

    passed: bool

    latency_seconds: float = Field(
        ge=0.0,
    )

    checks: dict[
        str,
        EvaluationCheck,
    ] = Field(
        default_factory=dict,
    )

    error_code: str | None = Field(
        default=None,
        min_length=1,
    )

    error_message: str | None = Field(
        default=None,
        min_length=1,
    )

    @model_validator(mode="after")
    def validate_error_state(
        self,
    ) -> "EvaluationCaseResult":
        """成功样本不能同时携带错误。"""

        if self.passed and (
            self.error_code is not None
            or self.error_message is not None
        ):
            raise ValueError(
                "通过样本不能包含错误信息"
            )

        return self

# 单个评测器的汇总统计
class EvaluationSummary(StrictBaseModel):
    """单个评测器的汇总结果。"""

    evaluator: EvaluatorType

    total_cases: int = Field(
        ge=0,
    )

    passed_cases: int = Field(
        ge=0,
    )

    pass_rate: float = Field(
        ge=0.0,
        le=1.0,
    )

    metrics: dict[str, float] = Field(
        default_factory=dict,
        description="准确率、召回率等指标",
    )

    counts: dict[str, int] = Field(
        default_factory=dict,
        description="正确数、失败数等原始计数",
    )

    @model_validator(mode="after")
    def validate_counts(
        self,
    ) -> "EvaluationSummary":
        """通过数不能超过总样本数。"""

        if self.passed_cases > self.total_cases:
            raise ValueError(
                "passed_cases不能大于total_cases"
            )

        return self