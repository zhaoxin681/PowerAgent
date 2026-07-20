"""动力电池充电参数寻优Skill。

使用有限候选参数组合和数字孪生预测结果，
筛选满足安全约束的充电电流与冷却功率方案。
"""

from __future__ import annotations

from enum import Enum
from itertools import product

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)

from skills.base_skill import BaseSkill
from skills.digital_twin_skill import (
    DigitalTwinOutput,
    DigitalTwinSkill,
)
from skills.schemas import SkillContext


# 寻优状态枚举
class OptimizationStatus(str, Enum):
    """参数寻优执行状态。"""

    SUCCESS = "success"
    NO_FEASIBLE_SOLUTION = "no_feasible_solution"


# 寻优输入
class OptimizationInput(BaseModel):
    """动力电池充电参数寻优输入。"""

    model_config = ConfigDict(extra="forbid")

    # 当前动力电池状态
    current_soc_pct: float = Field(
        ge=0,
        le=100,
        description="当前SOC，单位为百分比。",
    )
    current_pack_voltage_v: float = Field(
        gt=0,
        description="当前电池组端电压，单位为V。",
    )
    current_maximum_temperature_c: float = Field(
        description="当前最高温度，单位为摄氏度。",
    )
    current_charging_current_a: float = Field(
        ge=0,
        description="当前充电电流，单位为A。",
    )

    # 待搜索的候选控制参数
    candidate_charging_currents_a: list[float] = Field(
        min_length=1,
        max_length=6,
        description="候选充电电流列表，单位为A。",
    )
    candidate_cooling_powers_w: list[float] = Field(
        min_length=1,
        max_length=6,
        description="候选等效冷却功率列表，单位为W。",
    )
    forecast_minutes: float = Field(
        gt=0,
        le=120,
        description="每个候选方案的预测时间，单位为分钟。",
    )

    # 简化数字孪生模型参数
    battery_capacity_ah: float = Field(
        default=100.0,
        gt=0,
        description="电池组额定容量，单位为Ah。",
    )
    pack_internal_resistance_ohm: float = Field(
        default=0.05,
        ge=0,
        description="电池组等效内阻，单位为欧姆。",
    )
    effective_thermal_capacity_j_per_c: float = Field(
        default=100000.0,
        gt=0,
        description="电池组等效热容量，单位为J/℃。",
    )
    ocv_rise_per_soc_pct_v: float = Field(
        default=0.05,
        ge=0,
        description="SOC每增加1%对应的等效开路电压增量。",
    )
    charging_efficiency: float = Field(
        default=0.98,
        gt=0,
        le=1,
        description="充电库仑效率。",
    )
    ambient_temperature_c: float = Field(
        default=25.0,
        description="环境温度，单位为摄氏度。",
    )

    # 充电安全边界
    maximum_pack_voltage_v: float = Field(
        gt=0,
        description="允许的最高电池组电压，单位为V。",
    )
    maximum_charging_current_a: float = Field(
        gt=0,
        description="允许的最大充电电流，单位为A。",
    )
    maximum_charging_temperature_c: float = Field(
        default=50.0,
        description="允许的最高充电温度，单位为摄氏度。",
    )
    high_soc_threshold_pct: float = Field(
        default=90.0,
        ge=0,
        le=100,
        description="进入高SOC阶段的阈值。",
    )
    high_soc_current_limit_a: float = Field(
        default=20.0,
        ge=0,
        description="高SOC阶段允许的最大充电电流。",
    )

    # 多目标评分权重
    charging_current_weight: float = Field(
        default=0.40,
        ge=0,
        le=1,
        description="充电电流得分权重。",
    )  # 越大电流优先（充的快）
    voltage_margin_weight: float = Field(
        default=0.25,
        ge=0,
        le=1,
        description="电压安全裕度得分权重。",
    )  # 电压裕度越大越安全
    temperature_margin_weight: float = Field(
        default=0.25,
        ge=0,
        le=1,
        description="温度安全裕度得分权重。",
    )  # 温度越大越安全
    cooling_penalty_weight: float = Field(
        default=0.10,
        ge=0,
        le=1,
        description="冷却功率惩罚权重。",
    )  # 冷却功率惩罚（用得越多冷却，扣分越多，因为耗能/成本）

    @field_validator(
        "candidate_charging_currents_a",
        "candidate_cooling_powers_w",
    ) # 校验函数同时作用于两个字段
    @classmethod
    def validate_candidate_values(
        cls,
        values: list[float],
    ) -> list[float]:
        """检查候选参数是否非负且不存在重复值。"""

        if any(value < 0 for value in values):
            raise ValueError(
                "candidate values must be non-negative"
            )

        if len(values) != len(set(values)):
            raise ValueError(
                "candidate values must not contain duplicates"
            )

        return values

    @model_validator(mode="after")
    def validate_optimization_settings(
        self,
    ) -> "OptimizationInput":
        """检查搜索空间、安全限制和评分权重。"""

        candidate_count = (
            len(self.candidate_charging_currents_a)
            * len(self.candidate_cooling_powers_w)
        )

        if candidate_count > 25:
            raise ValueError(
                "candidate combinations must not exceed 25"
            )

        if (
            self.high_soc_current_limit_a
            > self.maximum_charging_current_a
        ):
            raise ValueError(
                "high_soc_current_limit_a must not exceed "
                "maximum_charging_current_a"
            )

        total_weight = (
            self.charging_current_weight
            + self.voltage_margin_weight
            + self.temperature_margin_weight
            + self.cooling_penalty_weight
        )

        if abs(total_weight - 1.0) > 1e-9:
            raise ValueError(
                "optimization weights must sum to 1.0"
            )

        return self


class CandidateEvaluation(BaseModel):
    """单个候选充电参数组合的评估结果。"""

    model_config = ConfigDict(extra="forbid")

    candidate_charging_current_a: float = Field(
        ge=0,
        description="候选充电电流，单位为A。",
    )
    cooling_power_w: float = Field(
        ge=0,
        description="候选等效冷却功率，单位为W。",
    )
    score: float | None = Field(
        default=None,
        description=(
            "可行候选方案的综合评分；"
            "不可行方案的评分为None。"
        ),
    )
    prediction: DigitalTwinOutput = Field(
        description="该候选方案对应的数字孪生预测结果。",
    )


class OptimizationOutput(BaseModel):
    """动力电池充电参数寻优输出。"""

    model_config = ConfigDict(extra="forbid")

    status: OptimizationStatus

    recommended_candidate: CandidateEvaluation | None = Field(
        default=None,
        description="综合评分最高的可行候选方案。",
    )
    alternative_candidates: list[CandidateEvaluation] = Field(
        default_factory=list,
        description="除推荐方案外的主要可行备选方案。",
    )
    evaluated_candidates: list[CandidateEvaluation] = Field(
        min_length=1,
        description="全部候选参数组合的评估结果。",
    )

    evaluated_candidate_count: int = Field(
        ge=1,
        description="实际完成评估的候选方案数量。",
    )
    feasible_candidate_count: int = Field(
        ge=0,
        description="满足全部安全约束的候选方案数量。",
    )

    selection_reason: str = Field(
        min_length=1,
        description="推荐方案或无可行方案的原因说明。",
    )

    @model_validator(mode="after")
    def validate_output_consistency(
        self,
    ) -> "OptimizationOutput":
        """检查寻优状态和候选结果是否一致。"""

        if (
            self.evaluated_candidate_count
            != len(self.evaluated_candidates)
        ):
            raise ValueError(
                "evaluated_candidate_count must match "
                "evaluated_candidates length"
            )

        actual_feasible_count = sum(
            candidate.prediction.is_feasible
            for candidate in self.evaluated_candidates
        )

        if (
            self.feasible_candidate_count
            != actual_feasible_count
        ):
            raise ValueError(
                "feasible_candidate_count must match "
                "the number of feasible predictions"
            )

        if self.status == OptimizationStatus.SUCCESS:
            if self.recommended_candidate is None:
                raise ValueError(
                    "successful optimization must contain "
                    "a recommended candidate"
                )

            if not self.recommended_candidate.prediction.is_feasible:
                raise ValueError(
                    "recommended candidate must be feasible"
                )

            if self.recommended_candidate.score is None:
                raise ValueError(
                    "recommended candidate must have a score"
                )

        if (
            self.status
            == OptimizationStatus.NO_FEASIBLE_SOLUTION
        ):
            if self.recommended_candidate is not None:
                raise ValueError(
                    "no-feasible-solution output must not "
                    "contain a recommended candidate"
                )

            if self.alternative_candidates:
                raise ValueError(
                    "no-feasible-solution output must not "
                    "contain alternative candidates"
                )

            if self.feasible_candidate_count != 0:
                raise ValueError(
                    "no-feasible-solution output must have "
                    "zero feasible candidates"
                )

        return self
    

# 实现 网格搜索+调用数字孪生+多目标加权评分+排序推荐 完整流程。
class OptimizationSkill(
    BaseSkill[OptimizationInput, OptimizationOutput]
):
    """搜索并评估候选充电电流和冷却功率组合。"""

    name = "parameter_optimization"
    description = (
        "调用简化数字孪生模型评估候选充电电流和"
        "冷却功率组合，返回满足安全约束的推荐参数。"
    )

    input_model = OptimizationInput
    output_model = OptimizationOutput

    def __init__(
        self,
        digital_twin_skill: DigitalTwinSkill | None = None,
    ) -> None:
        """初始化参数寻优Skill及其数字孪生依赖。"""

        self._digital_twin_skill = (
            digital_twin_skill
            or DigitalTwinSkill()
        )

        super().__init__()

    def execute(
        self,
        skill_input: OptimizationInput,
        context: SkillContext,
    ) -> dict[str, object]:
        """评估全部候选组合并选择推荐方案。"""

        # 1. 生成候选充电电流和冷却功率的笛卡尔积
        candidate_pairs = list(
            product(
                skill_input.candidate_charging_currents_a,
                skill_input.candidate_cooling_powers_w,
            )
        )

        # 暂存每个候选参数及其数字孪生预测结果
        raw_evaluations: list[
            tuple[float, float, DigitalTwinOutput]
        ] = []

        # 2. 调用DigitalTwinSkill评估每个候选组合
        for candidate_current, cooling_power in candidate_pairs:
            prediction = self._digital_twin_skill.run(
                {
                    "current_soc_pct": (
                        skill_input.current_soc_pct
                    ),
                    "current_pack_voltage_v": (
                        skill_input.current_pack_voltage_v
                    ),
                    "current_maximum_temperature_c": (
                        skill_input
                        .current_maximum_temperature_c
                    ),
                    "current_charging_current_a": (
                        skill_input
                        .current_charging_current_a
                    ),
                    "candidate_charging_current_a": (
                        candidate_current
                    ),
                    "forecast_minutes": (
                        skill_input.forecast_minutes
                    ),
                    "cooling_power_w": cooling_power,
                    "battery_capacity_ah": (
                        skill_input.battery_capacity_ah
                    ),
                    "pack_internal_resistance_ohm": (
                        skill_input
                        .pack_internal_resistance_ohm
                    ),
                    "effective_thermal_capacity_j_per_c": (
                        skill_input
                        .effective_thermal_capacity_j_per_c
                    ),
                    "ocv_rise_per_soc_pct_v": (
                        skill_input.ocv_rise_per_soc_pct_v
                    ),
                    "charging_efficiency": (
                        skill_input.charging_efficiency
                    ),
                    "ambient_temperature_c": (
                        skill_input.ambient_temperature_c
                    ),
                    "maximum_pack_voltage_v": (
                        skill_input.maximum_pack_voltage_v
                    ),
                    "maximum_charging_current_a": (
                        skill_input
                        .maximum_charging_current_a
                    ),
                    "maximum_charging_temperature_c": (
                        skill_input
                        .maximum_charging_temperature_c
                    ),
                    "high_soc_threshold_pct": (
                        skill_input.high_soc_threshold_pct
                    ),
                    "high_soc_current_limit_a": (
                        skill_input.high_soc_current_limit_a
                    ),
                },
                context=context,
            )

            raw_evaluations.append(
                (
                    candidate_current,
                    cooling_power,
                    prediction,
                )
            )

        # 3. 提取满足全部安全约束的候选方案
        feasible_evaluations = [
            item
            for item in raw_evaluations
            if item[2].is_feasible
        ]

        # 4. 所有候选均不可行时，不生成推荐方案
        if not feasible_evaluations:
            evaluated_candidates = [
                CandidateEvaluation(
                    candidate_charging_current_a=(
                        candidate_current
                    ),
                    cooling_power_w=cooling_power,
                    score=None,
                    prediction=prediction,
                )
                for (
                    candidate_current,
                    cooling_power,
                    prediction,
                ) in raw_evaluations
            ]

            return {
                "status": (
                    OptimizationStatus
                    .NO_FEASIBLE_SOLUTION
                ),
                "recommended_candidate": None,
                "alternative_candidates": [],
                "evaluated_candidates": (
                    evaluated_candidates
                ),
                "evaluated_candidate_count": len(
                    evaluated_candidates
                ),
                "feasible_candidate_count": 0,
                "selection_reason": (
                    "所有候选参数均违反数字孪生"
                    "安全约束，未生成推荐方案。"
                ),
            }

        # 5. 获取归一化评分所需的最大值
        maximum_feasible_current = max(
            candidate_current
            for (
                candidate_current,
                _,
                _,
            ) in feasible_evaluations
        )  # 可行方案里最大的候选电流

        maximum_voltage_margin = max(
            prediction.voltage_margin_v
            for (
                _,
                _,
                prediction,
            ) in feasible_evaluations
        )  # 可行方案里最大的电压裕度

        maximum_temperature_margin = max(
            prediction.temperature_margin_c
            for (
                _,
                _,
                prediction,
            ) in feasible_evaluations
        )  # 可行方案里最大的温度裕度

        maximum_cooling_power = max(
            cooling_power
            for (
                _,
                cooling_power,
                _,
            ) in raw_evaluations
        )  # 全部候选里的最大冷却功率

        # 6. 为全部候选生成结构化评估结果
        evaluated_candidates: list[
            CandidateEvaluation
        ] = []

        for (
            candidate_current,
            cooling_power,
            prediction,
        ) in raw_evaluations:
            if not prediction.is_feasible:
                evaluated_candidates.append(
                    CandidateEvaluation(
                        candidate_charging_current_a=(
                            candidate_current
                        ),
                        cooling_power_w=cooling_power,
                        score=None,
                        prediction=prediction,
                    )
                )
                continue

            current_score = self._normalize_value(
                value=candidate_current,
                maximum=maximum_feasible_current,
            )

            voltage_margin_score = self._normalize_value(
                value=prediction.voltage_margin_v,
                maximum=maximum_voltage_margin,
            )

            temperature_margin_score = (
                self._normalize_value(
                    value=prediction.temperature_margin_c,
                    maximum=maximum_temperature_margin,
                )
            )

            cooling_penalty = self._normalize_value(
                value=cooling_power,
                maximum=maximum_cooling_power,
            )
            # 综合得分
            total_score = (
                skill_input.charging_current_weight
                * current_score
                + skill_input.voltage_margin_weight
                * voltage_margin_score
                + skill_input.temperature_margin_weight
                * temperature_margin_score
                - skill_input.cooling_penalty_weight
                * cooling_penalty
            )

            evaluated_candidates.append(
                CandidateEvaluation(
                    candidate_charging_current_a=(
                        candidate_current
                    ),
                    cooling_power_w=cooling_power,
                    score=round(total_score, 6),
                    prediction=prediction,
                )
            )

        # 7. 对可行候选进行确定性排序
        feasible_candidates = [
            candidate
            for candidate in evaluated_candidates
            if candidate.prediction.is_feasible
        ]

        # 综合得分降序，得分相同时冷却功率升序（优选耗能更少的方案）
        # 前两者都相同时，候选电流降序（优先选充电更快的方案）
        feasible_candidates.sort(
            key=lambda candidate: (
                -self._require_score(candidate),
                candidate.cooling_power_w,
                -candidate.candidate_charging_current_a,
            )
        )

        recommended_candidate = feasible_candidates[0]

        alternative_candidates = (
            feasible_candidates[1:4]
        )

        # 8. 返回推荐方案及完整评估记录
        return {
            "status": OptimizationStatus.SUCCESS,
            "recommended_candidate": (
                recommended_candidate
            ),
            "alternative_candidates": (
                alternative_candidates
            ),
            "evaluated_candidates": (
                evaluated_candidates
            ),
            "evaluated_candidate_count": len(
                evaluated_candidates
            ),
            "feasible_candidate_count": len(
                feasible_candidates
            ),
            "selection_reason": (
                "推荐方案在满足全部数字孪生安全约束的"
                "候选中综合评分最高；评分同时考虑充电"
                "电流、电压裕度、温度裕度和冷却能耗。"
            ),
        }

    @staticmethod
    def _normalize_value(
        *,
        value: float,
        maximum: float,
    ) -> float:
        """将非负指标归一化到0～1。"""

        if maximum <= 0:
            return 0.0

        return value / maximum

    @staticmethod
    def _require_score(
        candidate: CandidateEvaluation,
    ) -> float:
        """读取可行候选评分并防止None参与排序。"""

        if candidate.score is None:
            raise ValueError(
                "feasible candidate must contain a score"
            )

        return candidate.score