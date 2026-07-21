"""研发问题分析工作流的数据契约。"""

from __future__ import annotations

from enum import Enum
from uuid import uuid4

from pydantic import Field, model_validator

from agent_core.schemas import (
    OperatingCondition,
    PowerSystemIssue,
    Severity,
    StrictBaseModel,
    Subsystem,
    TaskType,
)

from skills.schemas import RiskLevel


class EvidenceSource(str, Enum):
    """研发分析中已知事实的来源。"""

    USER_INPUT = "user_input"
    SKILL_RESULT = "skill_result"
    RAG_EVIDENCE = "rag_evidence"
    WORKFLOW_REVIEW = "workflow_review"
    EXPERIMENT_RESULT = "experiment_result"


class RootCauseStatus(str, Enum):
    """候选根因当前所处的证据状态。"""

    CONFIRMED = "confirmed"            # 已经得到足够的已验证事实或实验结果
    SUPPORTED = "supported_hypothesis" # 具有明确证据支持，值得优先开展验证实验，但还没有完成最终确认
    WEAK = "weak_hypothesis"           # 存在一定可能性，但证据不足
    UNSUPPORTED = "unsupported"        # 当前证据不能支撑


class RndPriority(str, Enum):
    """研发分析任务优先级。"""

    P0 = "p0"   # 立即处理
    P1 = "p1"   # 高优先级
    P2 = "p2"   # 一般优先级
    P3 = "p3"   # 低优先级


class RndAnalysisStatus(str, Enum):
    """研发分析完整结果的状态。"""

    COMPLETED = "completed"   # 系统已生成根因假设/验证实验/团队分工/研发报告所需数据
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"  # 系统正常运行，但证据不足
    EXECUTION_FAILED = "execution_failed"            # 工作流组件执行失败 
    HUMAN_REVIEW_REQUIRED = "human_review_required"  # 系统完成了初步分析，但不直接通过


class TeamName(str, Enum):
    """动力系统研发流程中的标准团队角色。"""

    BMS_ALGORITHM = "bms_algorithm"
    CHARGING_CONTROL = "charging_control"
    THERMAL_MANAGEMENT = "thermal_management"
    TEST_VALIDATION = "test_validation"
    DATA_PLATFORM = "data_platform"
    VEHICLE_SOFTWARE = "vehicle_software"
    FUNCTIONAL_SAFETY = "functional_safety"
    QUALITY = "quality"
    PROJECT_MANAGEMENT = "project_management" 

# 定义了一套用于车辆研发问题根因分析的结构化数据模型（基于Pydantic的StrictBaseModel），目的是
# 把“提出问题->收集事实->提出假设->验证->分工执行->风险管理”这个研发排查流程，用强类型、带校验
# 规则的模型固化下来，便于程序化处理。

class RndAnalysisRequest(StrictBaseModel):
    """研发问题分析请求。"""

    raw_input: str = Field(
        min_length=1,
        description="用户输入的原始研发问题",
    )
    trace_id: str = Field(
        default_factory=lambda: uuid4().hex,
        min_length=1,
        description="研发分析流程追踪标识",
    )
    affected_scope: list[str] = Field(
        default_factory=list,
        description="已知影响范围，例如车型、车辆批次或工况",
    )
    available_data: list[str] = Field(
        default_factory=list,
        description="当前已经具备的数据",
    )
    operating_conditions: list[OperatingCondition] = Field(
        default_factory=list,
        description="异常发生时的运行条件",
    )
    requested_deliverables: list[str] = Field(
        default_factory=list,
        description="用户需要的研发交付物",
    )


class KnownFact(StrictBaseModel):
    """研发分析中已经获得的事实。"""

    fact_id: str = Field(
        pattern=r"^fact_[a-z0-9_-]+$",
        description="事实稳定标识",
    )
    description: str = Field(min_length=1)
    subsystem: Subsystem
    source: EvidenceSource
    source_reference: str | None = Field(
        default=None,
        min_length=1,
        description="Skill、知识块或实验结果的来源标识",
    )
    is_verified: bool = Field(
        default=False,
        description="该事实是否已经得到验证",
    )
    confidence: float = Field(
        ge=0.0,
        le=1.0,
        description="事实可信度",
    )


class MissingInformation(StrictBaseModel):
    """完成研发判断仍然缺失的信息。"""

    item_id: str = Field(
        pattern=r"^missing_[a-z0-9_-]+$"
    )
    description: str = Field(min_length=1)
    impact: str = Field(
        min_length=1,
        description="信息缺失对研发判断的影响",
    )
    priority: RndPriority
    required_for_confirmation: bool = Field(
        default=True,
        description="缺少该信息时是否禁止确认根因",
    )
    related_hypothesis_ids: list[str] = Field(
        default_factory=list,
        description="该缺失信息影响的候选根因",
    )


class RootCauseHypothesis(StrictBaseModel):
    """研发问题的候选根因。"""

    hypothesis_id: str = Field(
        pattern=r"^hyp_[a-z0-9_-]+$"
    )
    description: str = Field(min_length=1)
    subsystem: Subsystem
    status: RootCauseStatus
    priority: RndPriority

    supporting_fact_ids: list[str] = Field(
        default_factory=list,
        description="支持该根因的事实ID",
    )
    contradicting_fact_ids: list[str] = Field(
        default_factory=list,
        description="与该根因冲突的事实ID",
    )

    reasoning: str = Field(
        min_length=1,
        description="从事实到根因的推理依据",
    )
    confidence: float = Field(ge=0.0, le=1.0)
    potential_impact: str = Field(min_length=1)
    needs_human_review: bool = False

    @model_validator(mode="after")
    def validate_evidence(
        self,
    ) -> "RootCauseHypothesis":
        """根因状态必须与证据和置信度一致。"""

        if (
            self.status
            in {
                RootCauseStatus.CONFIRMED,
                RootCauseStatus.SUPPORTED,
            }
            and not self.supporting_fact_ids
        ):
            raise ValueError(
                "confirmed或supported根因必须有支持事实"
            )

        if (
            self.confidence >= 0.7
            and not self.supporting_fact_ids
        ):
            raise ValueError(
                "高置信度根因必须引用支持事实"
            )

        if (
            self.status == RootCauseStatus.CONFIRMED
            and self.confidence < 0.8
        ):
            raise ValueError(
                "confirmed根因置信度不得低于0.8"
            )

        if (
            self.status == RootCauseStatus.UNSUPPORTED
            and self.confidence > 0.4
        ):
            raise ValueError(
                "unsupported根因置信度不得高于0.4"
            )

        return self


class ExperimentCriterion(StrictBaseModel):
    """验证实验的判定标准。"""

    metric: str = Field(min_length=1)
    measurement_method: str = Field(min_length=1)
    pass_condition: str = Field(min_length=1)
    fail_condition: str = Field(min_length=1)


class ValidationExperiment(StrictBaseModel):
    """候选根因验证实验。"""

    experiment_id: str = Field(
        pattern=r"^exp_[a-z0-9_-]+$"
    )
    title: str = Field(min_length=1)
    linked_hypothesis_ids: list[str] = Field(
        min_length=1,
        description="该实验验证的候选根因",
    )
    objective: str = Field(min_length=1)

    required_inputs: list[str] = Field(
        default_factory=list
    )
    controlled_variables: list[str] = Field(
        default_factory=list
    )
    steps: list[str] = Field(min_length=1)
    observed_metrics: list[str] = Field(min_length=1)
    expected_observation: str = Field(min_length=1)
    criteria: list[ExperimentCriterion] = Field(
        min_length=1
    )
    stop_conditions: list[str] = Field(
        default_factory=list
    )
    safety_requirements: list[str] = Field(
        default_factory=list
    )
    deliverables: list[str] = Field(min_length=1)

    risk_level: RiskLevel = RiskLevel.NORMAL
    needs_human_approval: bool = False

    @model_validator(mode="after")
    def validate_safety(
        self,
    ) -> "ValidationExperiment":
        """高风险实验必须定义安全要求并人工审批。"""

        if self.risk_level == RiskLevel.HIGH:
            if not self.safety_requirements:
                raise ValueError(
                    "高风险实验必须定义安全要求"
                )

            if not self.needs_human_approval:
                raise ValueError(
                    "高风险实验必须经过人工审批"
                )

        return self


class TeamAssignment(StrictBaseModel):
    """研发团队任务。"""

    assignment_id: str = Field(
        pattern=r"^assign_[a-z0-9_-]+$"
    )
    experiment_ids: list[str] = Field(min_length=1)
    owner: TeamName
    collaborators: list[TeamName] = Field(
        default_factory=list
    )
    reviewers: list[TeamName] = Field(
        default_factory=list
    )

    task: str = Field(min_length=1)
    input_dependencies: list[str] = Field(
        default_factory=list
    )
    deliverables: list[str] = Field(min_length=1)
    completion_criteria: list[str] = Field(
        min_length=1
    )
    blockers: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_roles(
        self,
    ) -> "TeamAssignment":
        """负责人、协作方和审核方不得冲突。"""

        collaborators = set(self.collaborators)
        reviewers = set(self.reviewers)

        if len(collaborators) != len(self.collaborators):
            raise ValueError(
                "collaborators存在重复团队"
            )

        if len(reviewers) != len(self.reviewers):
            raise ValueError(
                "reviewers存在重复团队"
            )

        if self.owner in collaborators:
            raise ValueError(
                "owner不能同时作为collaborator"
            )

        if self.owner in reviewers:
            raise ValueError(
                "owner不能同时作为reviewer"
            )

        if collaborators & reviewers:
            raise ValueError(
                "同一团队不能同时协作和审核"
            )

        return self


class CollaborationDependency(StrictBaseModel):
    """两个研发团队任务之间的交接依赖。"""

    dependency_id: str = Field(
        pattern=r"^dep_[a-z0-9_-]+$"
    )
    upstream_assignment_id: str = Field(min_length=1)
    downstream_assignment_id: str = Field(min_length=1)
    required_deliverable: str = Field(min_length=1)
    handoff_criteria: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_direction(
        self,
    ) -> "CollaborationDependency":
        """任务不能依赖自身。"""

        if (
            self.upstream_assignment_id
            == self.downstream_assignment_id
        ):
            raise ValueError(
                "团队任务不能依赖自身"
            )

        return self


class RndRisk(StrictBaseModel):
    """研发分析过程中识别出的风险。"""

    risk_id: str = Field(
        pattern=r"^risk_[a-z0-9_-]+$"
    )
    description: str = Field(min_length=1)
    risk_level: RiskLevel

    related_hypothesis_ids: list[str] = Field(
        default_factory=list
    )
    related_experiment_ids: list[str] = Field(
        default_factory=list
    )

    mitigation: str = Field(min_length=1)
    owner: TeamName
    requires_human_review: bool = False

    @model_validator(mode="after")
    def validate_risk(
        self,
    ) -> "RndRisk":
        """风险必须有关联对象，高风险必须人工复核。"""

        if not (
            self.related_hypothesis_ids
            or self.related_experiment_ids
        ):
            raise ValueError(
                "风险必须关联根因或验证实验"
            )

        if (
            self.risk_level == RiskLevel.HIGH
            and not self.requires_human_review
        ):
            raise ValueError(
                "高风险必须要求人工复核"
            )

        return self
    

# 子模型的顶层聚合模型，代表一次研发问题分析的完整结构化产出。
class RndAnalysisResult(StrictBaseModel):
    """研发问题分析的完整结构化结果。"""

    status: RndAnalysisStatus
    trace_id: str = Field(min_length=1)
    issue: PowerSystemIssue
    summary: str = Field(min_length=1)

    known_facts: list[KnownFact] = Field(
        default_factory=list
    )
    missing_information: list[MissingInformation] = Field(
        default_factory=list
    )
    hypotheses: list[RootCauseHypothesis] = Field(
        default_factory=list
    )
    experiments: list[ValidationExperiment] = Field(
        default_factory=list
    )
    team_assignments: list[TeamAssignment] = Field(
        default_factory=list
    )
    dependencies: list[CollaborationDependency] = Field(
        default_factory=list
    )
    risks: list[RndRisk] = Field(
        default_factory=list
    )

    overall_risk_level: RiskLevel
    needs_human_review: bool

    unresolved_items: list[str] = Field(
        default_factory=list
    )
    failure_reason: str | None = Field(
        default=None,
        min_length=1,
    )

    @model_validator(mode="after")
    def validate_result(
        self,
    ) -> "RndAnalysisResult":
        """校验状态、对象引用和人工复核要求。"""

        self._validate_status()
        self._validate_unique_ids()
        self._validate_references()
        self._validate_confirmed_hypotheses()
        self._validate_human_review()

        return self

    def _validate_status(self) -> None:
        """校验研发分析整体状态。"""

        if self.issue.task_type != TaskType.RND_ANALYSIS:
            raise ValueError(
                "研发分析结果的task_type必须为rnd_analysis"
            )

        if self.status == RndAnalysisStatus.EXECUTION_FAILED:
            if self.failure_reason is None:
                raise ValueError(
                    "执行失败时必须包含failure_reason"
                )
            return

        if self.failure_reason is not None:
            raise ValueError(
                "非执行失败状态不能包含failure_reason"
            )

        if self.status in {
            RndAnalysisStatus.COMPLETED,
            RndAnalysisStatus.HUMAN_REVIEW_REQUIRED,
        }:
            if not self.hypotheses:
                raise ValueError(
                    "完成状态必须包含候选根因"
                )
            if not self.experiments:
                raise ValueError(
                    "完成状态必须包含验证实验"
                )
            if not self.team_assignments:
                raise ValueError(
                    "完成状态必须包含团队任务"
                )

        if (
            self.status
            == RndAnalysisStatus.INSUFFICIENT_EVIDENCE
            and any(
                item.status == RootCauseStatus.CONFIRMED
                for item in self.hypotheses
            )
        ):
            raise ValueError(
                "证据不足状态不能包含confirmed根因"
            )

    def _validate_unique_ids(self) -> None:
        """同类研发对象的ID不得重复。"""

        groups = [
            (
                self.known_facts,
                "fact_id",
                "fact_id",
            ),
            (
                self.missing_information,
                "item_id",
                "missing item_id",
            ),
            (
                self.hypotheses,
                "hypothesis_id",
                "hypothesis_id",
            ),
            (
                self.experiments,
                "experiment_id",
                "experiment_id",
            ),
            (
                self.team_assignments,
                "assignment_id",
                "assignment_id",
            ),
            (
                self.dependencies,
                "dependency_id",
                "dependency_id",
            ),
            (
                self.risks,
                "risk_id",
                "risk_id",
            ),
        ]

        for items, attribute, label in groups:
            values = [
                getattr(item, attribute)
                for item in items
            ]
            if len(values) != len(set(values)):
                raise ValueError(
                    f"{label}不能重复"
                )

    def _validate_references(self) -> None:
        """校验事实、根因、实验和团队任务之间的引用。"""

        fact_ids = {
            item.fact_id for item in self.known_facts
        }
        hypothesis_ids = {
            item.hypothesis_id
            for item in self.hypotheses
        }
        experiment_ids = {
            item.experiment_id
            for item in self.experiments
        }
        assignment_ids = {
            item.assignment_id
            for item in self.team_assignments
        }

        unsupported_ids = {
            item.hypothesis_id
            for item in self.hypotheses
            if item.status == RootCauseStatus.UNSUPPORTED
        }

        for hypothesis in self.hypotheses:
            referenced_facts = set(
                hypothesis.supporting_fact_ids
                + hypothesis.contradicting_fact_ids
            )

            if not referenced_facts <= fact_ids:
                raise ValueError(
                    "候选根因引用了不存在的fact_id"
                )

        for missing in self.missing_information:
            if not set(
                missing.related_hypothesis_ids
            ) <= hypothesis_ids:
                raise ValueError(
                    "缺失信息引用了不存在的hypothesis_id"
                )

        for experiment in self.experiments:
            linked_ids = set(
                experiment.linked_hypothesis_ids
            )

            if not linked_ids <= hypothesis_ids:
                raise ValueError(
                    "实验引用了不存在的hypothesis_id"
                )

            if linked_ids & unsupported_ids:
                raise ValueError(
                    "实验不能验证unsupported根因"
                )

        for assignment in self.team_assignments:
            if not set(
                assignment.experiment_ids
            ) <= experiment_ids:
                raise ValueError(
                    "团队任务引用了不存在的experiment_id"
                )

        assigned_experiment_ids = {
            experiment_id
            for assignment in self.team_assignments
            for experiment_id in assignment.experiment_ids
        }

        for experiment in self.experiments:
            if (
                experiment.experiment_id
                not in assigned_experiment_ids
            ):
                raise ValueError(
                    "每个验证实验必须分配负责团队"
                )

        for dependency in self.dependencies:
            if (
                dependency.upstream_assignment_id
                not in assignment_ids
                or dependency.downstream_assignment_id
                not in assignment_ids
            ):
                raise ValueError(
                    "协作依赖引用了不存在的assignment_id"
                )

        for risk in self.risks:
            if not set(
                risk.related_hypothesis_ids
            ) <= hypothesis_ids:
                raise ValueError(
                    "风险引用了不存在的hypothesis_id"
                )

            if not set(
                risk.related_experiment_ids
            ) <= experiment_ids:
                raise ValueError(
                    "风险引用了不存在的experiment_id"
                )

    def _validate_confirmed_hypotheses(self) -> None:
        """已确认根因必须由已验证事实支撑。"""

        fact_map = {
            item.fact_id: item
            for item in self.known_facts
        }

        confirmed_ids = {
            item.hypothesis_id
            for item in self.hypotheses
            if item.status == RootCauseStatus.CONFIRMED
        }

        for hypothesis in self.hypotheses:
            if (
                hypothesis.status
                != RootCauseStatus.CONFIRMED
            ):
                continue

            supporting_facts = [
                fact_map[fact_id]
                for fact_id
                in hypothesis.supporting_fact_ids
            ]

            if not all(
                fact.is_verified
                for fact in supporting_facts
            ):
                raise ValueError(
                    "confirmed根因必须由已验证事实支撑"
                )

        for missing in self.missing_information:
            if not missing.required_for_confirmation:
                continue

            affected_ids = (
                set(missing.related_hypothesis_ids)
                if missing.related_hypothesis_ids
                else confirmed_ids
            )

            if affected_ids & confirmed_ids:
                raise ValueError(
                    "必要信息缺失时不能确认根因"
                )

    def _validate_human_review(self) -> None:
        """高风险或审批事项必须保留人工复核标志。"""

        requires_review = (
            self.status
            == RndAnalysisStatus.HUMAN_REVIEW_REQUIRED
            or self.overall_risk_level == RiskLevel.HIGH
            or self.issue.severity
            in {
                Severity.HIGH,
                Severity.CRITICAL,
            }
            or any(
                item.needs_human_review
                for item in self.hypotheses
            )
            or any(
                item.needs_human_approval
                for item in self.experiments
            )
            or any(
                item.requires_human_review
                for item in self.risks
            )
        )

        if requires_review and not self.needs_human_review:
            raise ValueError(
                "高风险或审批事项必须要求人工复核"
            )