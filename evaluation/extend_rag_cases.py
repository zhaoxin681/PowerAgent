"""向统一评测集增加RAG评测样本。"""

from __future__ import annotations

from pathlib import Path

from agent_core.schemas import Subsystem
from evaluation.dataset import (
    load_evaluation_cases,
    write_evaluation_cases,
)
from evaluation.schemas import (
    EvaluationCase,
    EvaluatorType,
    RAGExpectation,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]

CASE_FILE = (
    PROJECT_ROOT
    / "evaluation"
    / "test_cases.jsonl"
)


def make_rag_case(
    *,
    case_id: str,
    user_input: str,
    subsystem: Subsystem | None,
    expected_document_ids: list[str],
    required_concepts: list[list[str]],
    should_answer: bool = True,
    should_refuse: bool = False,
    sufficient_evidence: bool = True,
    needs_human_review: bool | None = None,
    min_citation_count: int = 1,
    forbidden_claims: list[str] | None = None,
    tags: list[str] | None = None,
) -> EvaluationCase:
    """构造一条统一RAG评测样本。"""

    return EvaluationCase(
        case_id=case_id,
        user_input=user_input,
        evaluators=[
            EvaluatorType.RAG,
        ],
        tags=[
            "rag",
            *(tags or []),
        ],
        rag_expectation=RAGExpectation(
            should_answer=should_answer,
            should_refuse=should_refuse,
            retrieval_subsystem=subsystem,
            top_k=5,
            min_score=0.10,
            expected_document_ids=(
                expected_document_ids
            ),
            expected_sufficient_evidence=(
                sufficient_evidence
            ),
            expected_needs_human_review=(
                needs_human_review
            ),
            min_citation_count=min_citation_count,
            required_answer_concepts=(
                required_concepts
            ),
            forbidden_claims=(
                forbidden_claims or []
            ),
        ),
    )


def build_rag_cases() -> list[EvaluationCase]:
    """构建知识命中、证据回答和拒答样本。"""

    return [
        make_rag_case(
            case_id="RAG-001",
            user_input=(
                "锂离子电池内短路早期可能出现"
                "哪些典型现象？"
            ),
            subsystem=Subsystem.BATTERY,
            expected_document_ids=[
                "battery_internal_short_circuit",
            ],
            required_concepts=[
                [
                    "静置阶段自放电速度异常增大",
                    "静置自放电异常",
                ],
                [
                    "局部温度或温升异常",
                    "局部温升异常",
                ],
                [
                    "持续性偏离",
                    "一致性指标持续偏离",
                ],
            ],
            needs_human_review=True,
            tags=[
                "internal_short_circuit",
                "safety",
            ],
        ),
        make_rag_case(
            case_id="RAG-002",
            user_input=(
                "为什么不能仅根据单一阈值"
                "直接确认电池内短路？"
            ),
            subsystem=Subsystem.BATTERY,
            expected_document_ids=[
                "battery_internal_short_circuit",
            ],
            required_concepts=[
                [
                    "需要多源数据联合判断",
                    "多源数据",
                ],
                [
                    "只支持候选诊断",
                    "不能直接确认内短路",
                ],
                [
                    "排除采样和连接异常",
                    "排除替代解释",
                ],
            ],
            needs_human_review=True,
            tags=[
                "internal_short_circuit",
                "diagnosis_boundary",
            ],
        ),
        make_rag_case(
            case_id="RAG-003",
            user_input=(
                "BMS与充电机通信异常的"
                "常见原因有哪些？"
            ),
            subsystem=Subsystem.CHARGING,
            expected_document_ids=[
                "charging_communication_faults",
            ],
            required_concepts=[
                [
                    "通信链路",
                    "连接器异常",
                    "终端电阻",
                ],
                [
                    "协议版本不一致",
                    "报文周期",
                ],
                [
                    "状态机逻辑异常",
                    "状态机",
                ],
            ],
            tags=[
                "charging_communication",
            ],
        ),
        make_rag_case(
            case_id="RAG-004",
            user_input=(
                "排查充电通信中断时需要"
                "采集哪些数据并如何定位？"
            ),
            subsystem=Subsystem.CHARGING,
            expected_document_ids=[
                "charging_communication_faults",
            ],
            required_concepts=[
                [
                    "通信报文",
                    "时间戳",
                    "错误计数",
                ],
                [
                    "状态机状态",
                    "充电状态机",
                ],
                [
                    "首次出现分歧的位置",
                    "定位首次分歧",
                ],
            ],
            tags=[
                "charging_communication",
                "verification",
            ],
        ),
        make_rag_case(
            case_id="RAG-005",
            user_input=(
                "动力系统中的异常、候选原因"
                "和故障确认有什么区别？"
            ),
            subsystem=Subsystem.MULTI_SYSTEM,
            expected_document_ids=[
                "power_system_safety_terms",
            ],
            required_concepts=[
                [
                    "异常不必然代表部件故障",
                    "异常不等于故障",
                ],
                [
                    "尚未被证据确认",
                    "候选原因",
                ],
                [
                    "排除主要替代解释",
                    "故障确认需要证据",
                ],
            ],
            tags=[
                "safety_terms",
                "diagnosis_boundary",
            ],
        ),
        make_rag_case(
            case_id="RAG-006",
            user_input=(
                "对于动力系统高风险结论，"
                "报告中应如何保证可靠性？"
            ),
            subsystem=Subsystem.MULTI_SYSTEM,
            expected_document_ids=[
                "power_system_safety_terms",
            ],
            required_concepts=[
                [
                    "检查每个结论是否具有对应证据",
                    "结论具有证据",
                ],
                [
                    "区分已观察事实、模型推断和人工判断",
                    "区分事实和推断",
                ],
                [
                    "设置人工复核",
                    "人工复核",
                ],
            ],
            needs_human_review=True,
            tags=[
                "safety_terms",
                "human_review",
            ],
        ),
        make_rag_case(
            case_id="RAG-007",
            user_input=(
                "动力电池数字孪生预测误差"
                "持续增大的可能原因有哪些？"
            ),
            subsystem=Subsystem.MULTI_SYSTEM,
            expected_document_ids=[
                "battery_digital_twin",
            ],
            required_concepts=[
                [
                    "模型结构或参数不能覆盖当前工况",
                    "模型参数不能覆盖工况",
                ],
                [
                    "传感数据质量不足",
                    "模型更新不及时",
                ],
                [
                    "耦合未被充分描述",
                    "热状态和电状态耦合",
                ],
            ],
            tags=[
                "digital_twin",
            ],
        ),
        make_rag_case(
            case_id="RAG-008",
            user_input=(
                "数字孪生的输出能否直接等同于"
                "真实电池状态？"
            ),
            subsystem=Subsystem.MULTI_SYSTEM,
            expected_document_ids=[
                "battery_digital_twin",
            ],
            required_concepts=[
                [
                    "不等同于真实系统本身",
                    "不能等同于真实电池",
                ],
                [
                    "结合传感数据",
                    "适用范围",
                ],
                [
                    "保留边界检查和人工审核",
                    "人工审核",
                ],
            ],
            tags=[
                "digital_twin",
                "model_boundary",
            ],
        ),
        make_rag_case(
            case_id="RAG-009",
            user_input=(
                "如何验证动力电池异常是真实故障，"
                "而不是采样或通信问题？"
            ),
            subsystem=Subsystem.MULTI_SYSTEM,
            expected_document_ids=[
                "battery_fault_verification",
            ],
            required_concepts=[
                [
                    "原始数据完整性和时间同步",
                    "检查时间同步",
                ],
                [
                    "独立测量或冗余信号",
                    "交叉验证",
                ],
                [
                    "复现工况",
                    "重复试验",
                ],
            ],
            tags=[
                "fault_verification",
            ],
        ),
        make_rag_case(
            case_id="RAG-010",
            user_input=(
                "动力电池热失控风险通常需要"
                "关注哪些联合异常信号？"
            ),
            subsystem=Subsystem.THERMAL,
            expected_document_ids=[
                "battery_thermal_runaway",
            ],
            required_concepts=[
                [
                    "温升速率明显异常",
                    "快速温升",
                ],
                [
                    "局部热点与周围测点温差持续扩大",
                    "局部温差扩大",
                ],
                [
                    "电压突变、绝缘异常或气体信号",
                    "多信号异常",
                ],
            ],
            needs_human_review=True,
            tags=[
                "thermal_runaway",
                "safety",
            ],
        ),
        make_rag_case(
            case_id="RAG-011",
            user_input=(
                "动力电池达到多少摄氏度时，"
                "必须统一判定为热失控？"
            ),
            subsystem=Subsystem.THERMAL,
            expected_document_ids=[
                "battery_thermal_runaway",
            ],
            required_concepts=[
                [
                    "没有给出固定温度阈值",
                    "不能仅依据单点高温",
                ],
                [
                    "服从产品级保护策略",
                    "以产品级策略为准",
                ],
            ],
            should_answer=False,
            should_refuse=True,
            sufficient_evidence=False,
            needs_human_review=True,
            min_citation_count=1,
            forbidden_claims=[
                "统一阈值为",
                "固定阈值是",
            ],
            tags=[
                "thermal_runaway",
                "refusal",
                "missing_threshold",
            ],
        ),
        make_rag_case(
            case_id="RAG-012",
            user_input=(
                "充电CAN报文超过多少毫秒"
                "必须判定为通信故障？"
            ),
            subsystem=Subsystem.CHARGING,
            expected_document_ids=[
                "charging_communication_faults",
            ],
            required_concepts=[
                [
                    "以具体接口定义为准",
                    "协议字段和超时要求",
                ],
                [
                    "知识库没有给出具体毫秒阈值",
                    "没有固定超时阈值",
                ],
            ],
            should_answer=False,
            should_refuse=True,
            sufficient_evidence=False,
            min_citation_count=1,
            forbidden_claims=[
                "统一超时阈值为",
                "固定为500毫秒",
            ],
            tags=[
                "charging_communication",
                "refusal",
                "missing_threshold",
            ],
        ),
        make_rag_case(
            case_id="RAG-013",
            user_input=(
                "内短路等效电阻5.1kΩ"
                "是不是所有动力电池统一标准？"
            ),
            subsystem=Subsystem.BATTERY,
            expected_document_ids=[
                "battery_internal_short_circuit",
            ],
            required_concepts=[
                [
                    "知识条目没有给出统一等效电阻阈值",
                    "没有统一标准",
                ],
                [
                    "需要多源数据联合判断",
                    "不能仅依据单一阈值",
                ],
            ],
            should_answer=False,
            should_refuse=True,
            sufficient_evidence=False,
            needs_human_review=True,
            min_citation_count=1,
            forbidden_claims=[
                "5.1kΩ是统一标准",
                "统一阈值为5.1kΩ",
            ],
            tags=[
                "internal_short_circuit",
                "refusal",
                "missing_threshold",
            ],
        ),
    ]


def main() -> None:
    """追加RAG样本并防止重复写入。"""

    existing_cases = load_evaluation_cases(
        CASE_FILE
    )

    new_cases = build_rag_cases()

    existing_ids = {
        case.case_id
        for case in existing_cases
    }

    duplicate_ids = sorted(
        case.case_id
        for case in new_cases
        if case.case_id in existing_ids
    )

    if duplicate_ids:
        raise ValueError(
            "以下RAG样本已经存在："
            + ", ".join(duplicate_ids)
        )

    all_cases = [
        *existing_cases,
        *new_cases,
    ]

    write_evaluation_cases(
        CASE_FILE,
        all_cases,
    )

    print(f"原有样本：{len(existing_cases)}")
    print(f"新增RAG样本：{len(new_cases)}")
    print(f"统一样本总数：{len(all_cases)}")


if __name__ == "__main__":
    main()