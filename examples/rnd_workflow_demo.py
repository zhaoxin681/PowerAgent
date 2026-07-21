"""第六周研发分析与跨团队协同工作流演示。

使用固定问题解析器、模拟RAG和模拟结构化LLM，
结合真实Router、Planner、Decision、Review和Report，
生成根因假设、验证实验、团队分工和研发分析报告。
"""

from __future__ import annotations

import json
from typing import Any

from agent_core.decision_agent import DecisionAgent
from agent_core.planner_agent import PlannerAgent
from agent_core.report_agent import ReportAgent
from agent_core.review_agent import ReviewAgent
from agent_core.router_agent import RouterAgent
from agent_core.schemas import (
    OperatingCondition,
    PowerSystemIssue,
    Severity,
    Subsystem,
    TaskType,
)
from agent_core.skill_registry import SkillRegistry
from agent_core.workflow import PowerAgentWorkflow
from rag.schemas import (
    RAGAnswer,
    RAGCitation,
)
from report.rnd_report_template import (
    RndReportTemplate,
)
from skills.schemas import RiskLevel
from workflows.rnd_analysis_workflow import (
    RndAnalysisWorkflow,
)
from workflows.rnd_models import (
    CollaborationDependency,
    ExperimentCriterion,
    RndAnalysisRequest,
    RndGenerationOutput,
    RndPriority,
    RndRisk,
    RootCauseHypothesis,
    RootCauseStatus,
    TeamAssignment,
    TeamName,
    ValidationExperiment,
)

class FixedRndIssueParser:
    """返回固定研发分析问题的演示解析器。"""

    def parse(
        self,
        user_input: str,
    ) -> PowerSystemIssue:
        """将演示输入转换为研发分析任务。"""

        return PowerSystemIssue(
            raw_text=user_input,
            subsystem=Subsystem.MULTI_SYSTEM,
            task_type=TaskType.RND_ANALYSIS,
            symptoms=[
                "SOC超过80%后充电电流频繁下降",
                "部分车辆最高温度偏高",
                "高SOC阶段单体压差扩大",
                "系统没有生成明确故障码",
            ],
            operating_conditions=[
                OperatingCondition(
                    name="SOC",
                    value="80以上",
                    unit="%",
                ),
                OperatingCondition(
                    name="充电阶段",
                    value="快充后段",
                    unit="",
                ),
            ],
            user_hypotheses=[],
            requested_outputs=[
                "候选根因",
                "验证实验",
                "团队分工",
                "研发分析报告",
            ],
            missing_information=[
                "缺少冷却液流量和水泵转速",
                "缺少异常车辆与正常车辆的对比日志",
            ],
            severity=Severity.MEDIUM,
            confidence=1.0,
        )
    

class DemoRndRAGPipeline:
    """返回固定动力系统研发证据。"""

    def __init__(self) -> None:
        self.call_count = 0

    def answer(
        self,
        question: str,
        **_: Any,
    ) -> RAGAnswer:
        """返回快充限流和热管理相关证据。"""

        self.call_count += 1

        return RAGAnswer(
            question=question,
            answer=(
                "高SOC快充阶段的电流下降可能与"
                "温度保护、单体电压约束、冷却能力"
                "及控制标定共同相关，需要通过对比"
                "实验区分各候选原因。"
            ),
            citations=[
                RAGCitation(
                    chunk_id="rnd_demo_chunk_1",
                    document_id="charging_thermal_doc",
                    title="高SOC快充约束与热管理知识",
                    section_path="快充后段限流",
                    page_number=None,
                    supported_claim=(
                        "快充后段限流可能由多种"
                        "安全约束共同触发"
                    ),
                    evidence_text=(
                        "高SOC阶段应综合检查温度、"
                        "单体电压和充电控制约束。"
                    ),
                )
            ],
            confidence=0.9,
            sufficient_evidence=True,
            missing_information=[
                "需要补充正常车辆与异常车辆的"
                "充电电流、温度和单体电压对比数据"
            ],
            needs_human_review=False,
        )
    

class DemoRndLLM:
    """根据可信上下文返回固定研发方案。"""

    def __init__(self) -> None:
        self.call_count = 0

    def parse_structured(
        self,
        *,
        developer_prompt: str,
        user_input: str,
        response_model: type[Any],
    ) -> RndGenerationOutput:
        """生成符合真实事实ID的研发分析结果。"""

        self.call_count += 1

        assert response_model is RndGenerationOutput
        assert developer_prompt.strip()

        payload = self._parse_context(user_input)
        known_facts = payload["known_facts"]

        if not known_facts:
            raise ValueError(
                "演示上下文中没有审核后的已知事实"
            )

        fact_id = known_facts[0]["fact_id"]

        return RndGenerationOutput(
            summary=(
                "当前优先验证冷却能力与高SOC"
                "安全约束是否共同触发快充限流。"
            ),
            hypotheses=[
                RootCauseHypothesis(
                    hypothesis_id=(
                        "hyp_cooling_limit"
                    ),
                    description=(
                        "高SOC阶段冷却能力不足，"
                        "导致温度升高并触发充电限流"
                    ),
                    subsystem=Subsystem.THERMAL,
                    status=(
                        RootCauseStatus.SUPPORTED
                    ),
                    priority=RndPriority.P1,
                    supporting_fact_ids=[fact_id],
                    contradicting_fact_ids=[],
                    reasoning=(
                        "审核后的知识证据表明，"
                        "快充后段限流需要重点检查"
                        "温度和冷却相关约束。"
                    ),
                    confidence=0.76,
                    potential_impact=(
                        "延长快充时间，并可能增加"
                        "高温运行风险。"
                    ),
                    needs_human_review=False,
                ),
                RootCauseHypothesis(
                    hypothesis_id=(
                        "hyp_voltage_constraint"
                    ),
                    description=(
                        "高SOC阶段部分单体提前接近"
                        "电压上限，触发充电电流限制"
                    ),
                    subsystem=Subsystem.BATTERY,
                    status=(
                        RootCauseStatus.WEAK
                    ),
                    priority=RndPriority.P2,
                    supporting_fact_ids=[],
                    contradicting_fact_ids=[],
                    reasoning=(
                        "用户描述了高SOC阶段单体"
                        "压差扩大，但缺少量化数据。"
                    ),
                    confidence=0.4,
                    potential_impact=(
                        "可能导致充电功率下降，"
                        "并暴露电池一致性问题。"
                    ),
                    needs_human_review=False,
                ),
            ],
            experiments=[
                self._build_cooling_experiment(),
                self._build_voltage_experiment(),
            ],
            team_assignments=[
                self._build_data_assignment(),
                self._build_cooling_assignment(),
                self._build_voltage_assignment(),
            ],
            dependencies=[
                CollaborationDependency(
                    dependency_id=(
                        "dep_data_to_cooling"
                    ),
                    upstream_assignment_id=(
                        "assign_data_prepare"
                    ),
                    downstream_assignment_id=(
                        "assign_cooling_test"
                    ),
                    required_deliverable=(
                        "正常与异常车辆的对齐充电日志"
                    ),
                    handoff_criteria=(
                        "日志时间轴、SOC区间和信号"
                        "字段完整，可以执行A/B对比。"
                    ),
                ),
                CollaborationDependency(
                    dependency_id=(
                        "dep_data_to_voltage"
                    ),
                    upstream_assignment_id=(
                        "assign_data_prepare"
                    ),
                    downstream_assignment_id=(
                        "assign_voltage_analysis"
                    ),
                    required_deliverable=(
                        "高SOC阶段单体电压和电流数据"
                    ),
                    handoff_criteria=(
                        "单体编号、采样周期和充电阶段"
                        "信息完整。"
                    ),
                ),
            ],
            risks=[
                RndRisk(
                    risk_id="risk_test_overtemperature",
                    description=(
                        "快充A/B试验过程中可能出现"
                        "温度继续升高。"
                    ),
                    risk_level=RiskLevel.MEDIUM,
                    related_hypothesis_ids=[
                        "hyp_cooling_limit"
                    ],
                    related_experiment_ids=[
                        "exp_cooling_ab"
                    ],
                    mitigation=(
                        "设置超温停止条件，实时监测"
                        "最高温度和温升速率。"
                    ),
                    owner=TeamName.TEST_VALIDATION,
                    requires_human_review=False,
                )
            ],
            overall_risk_level=RiskLevel.MEDIUM,
            needs_human_review=False,
            unresolved_items=[
                "尚未获得真实冷却液流量和水泵转速",
                "尚未完成正常车辆与异常车辆对比",
            ],
        )

    @staticmethod
    def _parse_context(
        user_input: str,
    ) -> dict[str, Any]:
        """提取RndAnalysisWorkflow传入的JSON上下文。"""

        start_marker = "RND_CONTEXT_START"
        end_marker = "RND_CONTEXT_END"

        if (
            start_marker not in user_input
            or end_marker not in user_input
        ):
            raise ValueError(
                "研发分析输入缺少上下文标记"
            )

        context_text = (
            user_input
            .split(start_marker, maxsplit=1)[1]
            .split(end_marker, maxsplit=1)[0]
            .strip()
        )

        return json.loads(context_text)

    @staticmethod
    def _build_cooling_experiment(
    ) -> ValidationExperiment:
        """构造冷却能力A/B验证实验。"""

        return ValidationExperiment(
            experiment_id="exp_cooling_ab",
            title="冷却能力A/B快充对比实验",
            linked_hypothesis_ids=[
                "hyp_cooling_limit"
            ],
            objective=(
                "验证提高冷却能力后，温度升高"
                "和快充后段限流是否减轻。"
            ),
            required_inputs=[
                "充电电流",
                "SOC",
                "最高温度",
                "冷却控制状态",
            ],
            controlled_variables=[
                "初始SOC",
                "环境温度",
                "充电桩功率",
                "电池初始温度",
            ],
            steps=[
                "选择状态接近的试验车辆。",
                "固定初始SOC和环境条件。",
                "分别采用基准与增强冷却策略快充。",
                "对比SOC超过80%后的温度和电流。",
            ],
            observed_metrics=[
                "最高温度",
                "温升速率",
                "SOC超过80%后的平均充电电流",
            ],
            expected_observation=(
                "增强冷却后最高温度降低，"
                "后段平均充电电流提高。"
            ),
            criteria=[
                ExperimentCriterion(
                    metric=(
                        "SOC超过80%后的平均充电电流"
                    ),
                    measurement_method=(
                        "对齐两组充电日志后计算均值"
                    ),
                    pass_condition=(
                        "增强冷却后平均充电电流明显提高"
                    ),
                    fail_condition=(
                        "两组平均充电电流无明显差异"
                    ),
                )
            ],
            stop_conditions=[
                "最高温度超过安全上限",
                "出现充电系统严重故障码",
            ],
            safety_requirements=[
                "配置超温保护和人工停止权限"
            ],
            deliverables=[
                "A/B试验原始日志",
                "温度与充电电流对比报告",
            ],
            risk_level=RiskLevel.MEDIUM,
            needs_human_approval=False,
        )

    @staticmethod
    def _build_voltage_experiment(
    ) -> ValidationExperiment:
        """构造高SOC单体电压分析实验。"""

        return ValidationExperiment(
            experiment_id="exp_voltage_compare",
            title="高SOC单体电压约束对比分析",
            linked_hypothesis_ids=[
                "hyp_voltage_constraint"
            ],
            objective=(
                "判断是否存在部分单体提前接近"
                "电压上限并触发限流。"
            ),
            required_inputs=[
                "全部单体电压",
                "充电电流",
                "SOC",
            ],
            controlled_variables=[
                "SOC区间",
                "采样周期",
            ],
            steps=[
                "提取SOC 75%至100%的充电日志。",
                "计算各时刻最高单体电压和压差。",
                "对齐首次明显限流时刻。",
                "比较电压约束与限流的先后关系。",
            ],
            observed_metrics=[
                "最高单体电压",
                "单体压差",
                "充电电流下降时刻",
            ],
            expected_observation=(
                "若电压约束是主要原因，"
                "最高单体电压应先接近上限，"
                "随后出现充电电流下降。"
            ),
            criteria=[
                ExperimentCriterion(
                    metric="限流前最高单体电压",
                    measurement_method=(
                        "分析限流前后的单体电压时序"
                    ),
                    pass_condition=(
                        "限流前存在单体持续接近电压上限"
                    ),
                    fail_condition=(
                        "限流前单体电压仍具有充分裕度"
                    ),
                )
            ],
            stop_conditions=[],
            safety_requirements=[],
            deliverables=[
                "单体电压时序分析报告"
            ],
            risk_level=RiskLevel.LOW,
            needs_human_approval=False,
        )
    
    @staticmethod
    def _build_data_assignment(
    ) -> TeamAssignment:
        """构造数据准备任务。"""

        return TeamAssignment(
            assignment_id="assign_data_prepare",
            experiment_ids=[
                "exp_cooling_ab",
                "exp_voltage_compare",
            ],
            owner=TeamName.DATA_PLATFORM,
            collaborators=[
                TeamName.VEHICLE_SOFTWARE
            ],
            reviewers=[],
            task=(
                "提取并对齐正常车辆与异常车辆"
                "的高SOC快充日志。"
            ),
            input_dependencies=[
                "车辆VIN或设备标识",
                "充电时间范围",
                "信号字典",
            ],
            deliverables=[
                "对齐后的快充日志数据集",
                "数据质量检查记录",
            ],
            completion_criteria=[
                "关键电流、SOC、温度和单体电压"
                "信号不存在明显缺失",
                "正常与异常车辆数据具有可比性",
            ],
            blockers=[
                "异常车辆样本数量不足"
            ],
        )

    @staticmethod
    def _build_cooling_assignment(
    ) -> TeamAssignment:
        """构造冷却实验任务。"""

        return TeamAssignment(
            assignment_id="assign_cooling_test",
            experiment_ids=["exp_cooling_ab"],
            owner=TeamName.TEST_VALIDATION,
            collaborators=[
                TeamName.THERMAL_MANAGEMENT,
                TeamName.CHARGING_CONTROL,
            ],
            reviewers=[
                TeamName.FUNCTIONAL_SAFETY
            ],
            task="执行冷却能力A/B快充对比实验。",
            input_dependencies=[
                "对齐后的快充日志数据集",
                "两档冷却控制方案",
            ],
            deliverables=[
                "A/B试验日志",
                "冷却能力与限流关系报告",
            ],
            completion_criteria=[
                "两组实验均完成",
                "实验条件差异处于允许范围",
                "关键观察指标可重复比较",
            ],
            blockers=[
                "试验车辆或快充设备不可用"
            ],
        )

    @staticmethod
    def _build_voltage_assignment(
    ) -> TeamAssignment:
        """构造单体电压分析任务。"""

        return TeamAssignment(
            assignment_id=(
                "assign_voltage_analysis"
            ),
            experiment_ids=[
                "exp_voltage_compare"
            ],
            owner=TeamName.BMS_ALGORITHM,
            collaborators=[
                TeamName.DATA_PLATFORM
            ],
            reviewers=[
                TeamName.QUALITY
            ],
            task=(
                "分析高SOC阶段单体电压、"
                "压差与充电限流的时序关系。"
            ),
            input_dependencies=[
                "高SOC快充单体电压日志"
            ],
            deliverables=[
                "单体电压约束分析报告",
                "异常车辆清单",
            ],
            completion_criteria=[
                "明确限流前后的最高单体电压",
                "给出电压约束假设的支持或反向证据",
            ],
            blockers=[
                "单体电压信号采样不同步"
            ],
        )
    

def build_base_workflow(
    rag_pipeline: DemoRndRAGPipeline,
) -> PowerAgentWorkflow:
    """创建研发分析底层LangGraph工作流。"""

    registry = SkillRegistry()

    return PowerAgentWorkflow(
        issue_parser=FixedRndIssueParser(),
        router_agent=RouterAgent(),
        planner_agent=PlannerAgent(
            registry=registry,
        ),
        decision_agent=DecisionAgent(
            max_replans=1,
        ),
        review_agent=ReviewAgent(),
        report_agent=ReportAgent(),
        registry=registry,
        rag_pipeline=rag_pipeline,
    )


def build_request() -> RndAnalysisRequest:
    """构造研发分析请求。"""

    return RndAnalysisRequest(
        raw_input=(
            "部分车辆在快充过程中，"
            "SOC超过80%后充电电流频繁下降，"
            "同时最高温度偏高且单体压差扩大，"
            "但没有明确故障码。"
        ),
        trace_id="week6_rnd_demo_001",
        affected_scope=[
            "部分车辆",
            "高SOC快充工况",
        ],
        available_data=[
            "充电电流",
            "SOC",
            "最高温度",
            "单体电压",
        ],
        operating_conditions=[
            OperatingCondition(
                name="SOC",
                value="80以上",
                unit="%",
            )
        ],
        requested_deliverables=[
            "候选根因",
            "验证实验",
            "团队分工",
            "研发分析报告",
        ],
    )


def main() -> None:
    """运行第六周研发分析完整演示。"""

    rag_pipeline = DemoRndRAGPipeline()
    rnd_llm = DemoRndLLM()

    base_workflow = build_base_workflow(
        rag_pipeline
    )

    workflow = RndAnalysisWorkflow(
        base_workflow=base_workflow,
        llm_client=rnd_llm,
    )

    result = workflow.analyze(
        build_request()
    )

    markdown_report = (
        RndReportTemplate().render(result)
    )

    print("第六周研发分析工作流执行完成。")
    print(f"trace_id: {result.trace_id}")
    print(f"status: {result.status.value}")
    print(
        "risk_level: "
        f"{result.overall_risk_level.value}"
    )
    print(
        "needs_human_review: "
        f"{result.needs_human_review}"
    )
    print(
        "hypothesis_count: "
        f"{len(result.hypotheses)}"
    )
    print(
        "experiment_count: "
        f"{len(result.experiments)}"
    )
    print(
        "assignment_count: "
        f"{len(result.team_assignments)}"
    )
    print(
        "rag_call_count: "
        f"{rag_pipeline.call_count}"
    )
    print(
        "rnd_llm_call_count: "
        f"{rnd_llm.call_count}"
    )

    print("\n结构化研发分析结果：")
    print(
        result.model_dump_json(
            indent=2,
        )
    )

    print("\n研发分析Markdown报告：")
    print(markdown_report)


if __name__ == "__main__":
    main()