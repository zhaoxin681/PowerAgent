"""动力系统云端策略模拟下发Skill。

将参数寻优结果转换为可审核、可追踪的模拟控制策略。
本模块不执行任何真实设备通信或控制操作。重点在于审批流控制和安全兜底。
"""

from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    model_validator,
)

from skills.base_skill import BaseSkill
from skills.optimization_skill import (
    CandidateEvaluation,
    OptimizationStatus,
)
from skills.schemas import RiskLevel, SkillContext


class DispatchStatus(str, Enum):
    """模拟云端策略的下发状态。"""

    DRAFT = "draft"   # 策略生成了，但需要人工批准才能生效（草稿态）
    READY = "ready"   # 策略生成了，安全检查通过，且允许自动下发（就绪状态，最顺畅的路径）
    REQUIRES_REVIEW = "requires_review"  # 策略生成了，但因某些原因必须人工复核（比如风险较高但还没到完全阻断的程度）
    BLOCKED = "blocked"  # 策略被阻断，完全不生成可执行方案（最保守的结果）


class DispatchStrategy(BaseModel):
    """通过安全检查后生成的模拟下发策略。"""

    model_config = ConfigDict(extra="forbid")

    strategy_id: str = Field(
        min_length=1,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]*$",
        description="模拟策略的唯一标识。",
    )
    strategy_version: str = Field(
        default="1.0.0",
        pattern=r"^\d+\.\d+\.\d+$",
        description="模拟策略版本号。",
    )
    target_device_id: str = Field(
        min_length=1,
        description="目标设备标识。",
    )

    charging_current_a: float = Field(
        ge=0,
        description="建议充电电流，单位为A。",
    )
    cooling_power_w: float = Field(
        ge=0,
        description="建议等效冷却功率，单位为W。",
    )
    valid_for_minutes: int = Field(
        gt=0,
        le=1440,
        description="策略有效时间，单位为分钟。",
    )

    simulation_only: Literal[True] = Field(
        default=True,
        description="固定为True，表示策略仅用于模拟。",
    )


class CloudDispatchInput(BaseModel):
    """云端策略模拟下发输入。"""

    model_config = ConfigDict(extra="forbid")

    # 参数寻优结果
    optimization_status: OptimizationStatus = Field(
        description="参数寻优执行状态。",
    )
    recommended_candidate: CandidateEvaluation | None = Field(
        default=None,
        description="参数寻优返回的推荐候选方案。",
    )
    optimization_reason: str = Field(
        min_length=1,
        description="参数寻优的选择或失败原因。",
    )

    # 当前动力系统风险
    current_risk_level: RiskLevel = Field(
        default=RiskLevel.NORMAL,
        description="当前动力系统综合风险等级。",
    )

    # 策略元数据
    strategy_id: str = Field(
        min_length=1,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]*$",
        description="本次模拟策略的唯一标识。",
    )
    strategy_version: str = Field(
        default="1.0.0",
        pattern=r"^\d+\.\d+\.\d+$",
        description="本次模拟策略版本号。",
    )
    target_device_id: str = Field(
        min_length=1,
        description="模拟策略对应的目标设备。",
    )
    valid_for_minutes: int = Field(
        default=30,
        gt=0,
        le=1440,
        description="策略有效时间，单位为分钟。",
    )

    # 审批配置
    allow_automatic_dispatch: bool = Field(
        default=False,
        description="是否允许生成自动下发就绪状态。",
    )
    force_manual_review: bool = Field(
        default=False,
        description="是否强制要求人工复核。",
    )

    # 下发层独立安全边界
    maximum_dispatch_current_a: float = Field(
        gt=0,
        description="下发层允许的最大充电电流。",
    )
    maximum_dispatch_cooling_power_w: float = Field(
        ge=0,
        description="下发层允许的最大冷却功率。",
    )

    @model_validator(mode="after")
    def validate_optimization_result(
        self,
    ) -> "CloudDispatchInput":
        """检查寻优状态与推荐候选是否一致。"""

        if self.optimization_status == OptimizationStatus.SUCCESS:
            if self.recommended_candidate is None:
                raise ValueError(
                    "successful optimization must provide "
                    "a recommended candidate"
                )

        if (
            self.optimization_status
            == OptimizationStatus.NO_FEASIBLE_SOLUTION
        ):
            if self.recommended_candidate is not None:
                raise ValueError(
                    "no-feasible-solution optimization must not "
                    "provide a recommended candidate"
                )

        if self.recommended_candidate is not None:
            if not self.recommended_candidate.prediction.is_feasible:
                raise ValueError(
                    "recommended candidate must be feasible"
                )

            if self.recommended_candidate.score is None:
                raise ValueError(
                    "recommended candidate must contain a score"
                )

        return self


class CloudDispatchOutput(BaseModel):
    """云端策略模拟下发输出。"""

    model_config = ConfigDict(extra="forbid")

    status: DispatchStatus

    strategy: DispatchStrategy | None = Field(
        default=None,
        description="通过检查后生成的模拟策略。",
    )
    source_candidate: CandidateEvaluation | None = Field(
        default=None,
        description="策略所依据的参数寻优候选方案。",
    )

    safety_checks_passed: bool = Field(
        description="下发层安全检查是否通过。",
    )
    requires_manual_review: bool = Field(
        description="是否需要人工复核。",
    )

    blocking_reasons: list[str] = Field(
        default_factory=list,
        description="阻断模拟下发的原因。",
    )
    decision_evidence: list[str] = Field(
        min_length=1,
        description="下发状态判断依据。",
    )

    rollback_recommendation: str = Field(
        min_length=1,
        description="策略异常时的回滚或降级建议。",
    )
    source_trace_id: str = Field(
        min_length=1,
        description="来源调用或工作流的追踪标识。",
    )

    @model_validator(mode="after")
    def validate_dispatch_consistency(
        self,
    ) -> "CloudDispatchOutput":
        """检查下发状态和输出数据是否一致。"""

        if self.status == DispatchStatus.BLOCKED:
            if self.strategy is not None:
                raise ValueError(
                    "blocked output must not contain a strategy"
                )

            if self.safety_checks_passed:
                raise ValueError(
                    "blocked output must fail safety checks"
                )

            if not self.blocking_reasons:
                raise ValueError(
                    "blocked output must contain blocking reasons"
                )

            if not self.requires_manual_review:
                raise ValueError(
                    "blocked output must require manual review"
                )

        if self.status == DispatchStatus.READY:
            if self.strategy is None:
                raise ValueError(
                    "ready output must contain a strategy"
                )

            if not self.safety_checks_passed:
                raise ValueError(
                    "ready output must pass safety checks"
                )

            if self.requires_manual_review:
                raise ValueError(
                    "ready output must not require manual review"
                )

            if self.blocking_reasons:
                raise ValueError(
                    "ready output must not contain blocking reasons"
                )

        if self.status == DispatchStatus.DRAFT:
            if self.strategy is None:
                raise ValueError(
                    "draft output must contain a strategy"
                )

            if not self.safety_checks_passed:
                raise ValueError(
                    "draft output must pass safety checks"
                )

            if not self.requires_manual_review:
                raise ValueError(
                    "draft output must require approval"
                )

            if self.blocking_reasons:
                raise ValueError(
                    "draft output must not contain blocking reasons"
                )

        if self.status == DispatchStatus.REQUIRES_REVIEW:
            if self.strategy is None:
                raise ValueError(
                    "review output must contain a strategy"
                )

            if not self.safety_checks_passed:
                raise ValueError(
                    "review output must pass safety checks"
                )

            if not self.requires_manual_review:
                raise ValueError(
                    "review output must require manual review"
                )

            if self.blocking_reasons:
                raise ValueError(
                    "review output must not contain blocking reasons"
                )

        return self
    

# 实现了一套多级安全检查+分层审批决策的判断树，把上一层寻优结果最终转化为四种下发状态之一
class CloudDispatchSkill(
    BaseSkill[CloudDispatchInput, CloudDispatchOutput]
):
    """将参数寻优结果转换为模拟云端下发策略。"""

    name = "cloud_dispatch"
    description = (
        "根据参数寻优结果、当前风险等级和下发权限，"
        "生成可审核、可追踪的模拟云端策略。"
    )

    input_model = CloudDispatchInput
    output_model = CloudDispatchOutput

    def execute(
        self,
        skill_input: CloudDispatchInput,
        context: SkillContext,
    ) -> dict[str, object]:
        """执行模拟策略安全检查和状态决策。"""

        decision_evidence = [
            (
                "参数寻优结果说明："
                f"{skill_input.optimization_reason}"
            ),
            (
                "当前动力系统风险等级："
                f"{skill_input.current_risk_level.value}。"
            ),
        ] # 记录判断依据，贯穿全程不断追加

        rollback_recommendation = (
            "如后续验证发现状态异常，应停止采用该策略，"
            "恢复当前安全参数并转入人工复核。"
        )

        # 1. 参数寻优没有找到可行方案时直接阻断
        if (
            skill_input.optimization_status
            == OptimizationStatus.NO_FEASIBLE_SOLUTION
        ):
            decision_evidence.append(
                "参数寻优未返回满足安全约束的推荐方案。"
            )

            return {
                "status": DispatchStatus.BLOCKED,
                "strategy": None,
                "source_candidate": None,
                "safety_checks_passed": False,
                "requires_manual_review": True,
                "blocking_reasons": [
                    "no_feasible_optimization_solution"
                ],
                "decision_evidence": decision_evidence,
                "rollback_recommendation": (
                    rollback_recommendation
                ),
                "source_trace_id": context.trace_id,
            }

        # 输入模型已经保证成功状态下推荐方案不为空
        recommended_candidate = (
            skill_input.recommended_candidate
        )

        if recommended_candidate is None:
            raise ValueError(
                "recommended candidate is required"
            )

        # 2. 执行云端下发层的独立安全检查
        blocking_reasons: list[str] = []

        if (
            recommended_candidate
            .candidate_charging_current_a
            > skill_input.maximum_dispatch_current_a
        ):
            blocking_reasons.append(
                "dispatch_current_limit_exceeded"
            )

            decision_evidence.append(
                (
                    "推荐充电电流"
                    f"{recommended_candidate.candidate_charging_current_a}A"
                    "超过下发层允许的最大电流"
                    f"{skill_input.maximum_dispatch_current_a}A。"
                )
            )

        if (
            recommended_candidate.cooling_power_w
            > skill_input.maximum_dispatch_cooling_power_w
        ):
            blocking_reasons.append(
                "dispatch_cooling_power_limit_exceeded"
            )

            decision_evidence.append(
                (
                    "推荐冷却功率"
                    f"{recommended_candidate.cooling_power_w}W"
                    "超过下发层允许的最大冷却功率"
                    f"{skill_input.maximum_dispatch_cooling_power_w}W。"
                )
            )

        # 3. 高风险状态下禁止生成可执行策略
        if skill_input.current_risk_level == RiskLevel.HIGH:
            blocking_reasons.append(
                "current_high_risk_requires_blocking"
            )

            decision_evidence.append(
                "当前动力系统处于高风险状态，禁止自动生成下发策略。"
            )

        # 4. 任意阻断条件存在时返回blocked
        if blocking_reasons:
            return {
                "status": DispatchStatus.BLOCKED,
                "strategy": None,
                "source_candidate": (
                    recommended_candidate
                ),
                "safety_checks_passed": False,
                "requires_manual_review": True,
                "blocking_reasons": blocking_reasons,
                "decision_evidence": decision_evidence,
                "rollback_recommendation": (
                    rollback_recommendation
                ),
                "source_trace_id": context.trace_id,
            }

        # 5. 安全检查通过后生成模拟策略
        strategy = DispatchStrategy(
            strategy_id=skill_input.strategy_id,
            strategy_version=(
                skill_input.strategy_version
            ),
            target_device_id=(
                skill_input.target_device_id
            ),
            charging_current_a=(
                recommended_candidate
                .candidate_charging_current_a
            ),
            cooling_power_w=(
                recommended_candidate.cooling_power_w
            ),
            valid_for_minutes=(
                skill_input.valid_for_minutes
            ),
            simulation_only=True,
        )

        decision_evidence.append(
            "推荐方案通过数字孪生可行性检查。"
        )
        decision_evidence.append(
            "推荐参数未超过云端下发层独立安全边界。"
        )

        # 6. 中风险或强制复核时进入人工审核状态
        if (
            skill_input.current_risk_level
            == RiskLevel.MEDIUM
            or skill_input.force_manual_review
        ):
            if (
                skill_input.current_risk_level
                == RiskLevel.MEDIUM
            ):
                decision_evidence.append(
                    "当前风险等级为中风险，策略必须经过人工复核。"
                )

            if skill_input.force_manual_review:
                decision_evidence.append(
                    "调用配置明确要求对策略进行人工复核。"
                )

            return {
                "status": (
                    DispatchStatus.REQUIRES_REVIEW
                ),
                "strategy": strategy,
                "source_candidate": (
                    recommended_candidate
                ),
                "safety_checks_passed": True,
                "requires_manual_review": True,
                "blocking_reasons": [],
                "decision_evidence": decision_evidence,
                "rollback_recommendation": (
                    rollback_recommendation
                ),
                "source_trace_id": context.trace_id,
            }

        # 7. 明确允许自动下发时进入ready状态
        if skill_input.allow_automatic_dispatch:
            decision_evidence.append(
                "当前风险可接受且已明确允许自动下发。"
            )

            return {
                "status": DispatchStatus.READY,
                "strategy": strategy,
                "source_candidate": (
                    recommended_candidate
                ),
                "safety_checks_passed": True,
                "requires_manual_review": False,
                "blocking_reasons": [],
                "decision_evidence": decision_evidence,
                "rollback_recommendation": (
                    rollback_recommendation
                ),
                "source_trace_id": context.trace_id,
            }

        # 8. 未授权自动下发时只生成策略草稿
        decision_evidence.append(
            "策略已通过安全检查，但尚未获得自动下发授权。"
        )

        return {
            "status": DispatchStatus.DRAFT,
            "strategy": strategy,
            "source_candidate": recommended_candidate,
            "safety_checks_passed": True,
            "requires_manual_review": True,
            "blocking_reasons": [],
            "decision_evidence": decision_evidence,
            "rollback_recommendation": (
                rollback_recommendation
            ),
            "source_trace_id": context.trace_id,
        }