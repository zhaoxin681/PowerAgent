"""生成PowerAgent初始动力系统知识语料。

该脚本只用于创建可控、可评测的RAG种子文档。供后续RAG管线加载、切块、向量化使用。
默认不会覆盖已经存在的知识文档。
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
KNOWLEDGE_BASE_DIR = PROJECT_ROOT / "docs" / "knowledge_base"


# 定义每篇知识文档的统一骨架
@dataclass(frozen=True)
class KnowledgeDocumentSpec:
    """一份种子知识文档的结构化定义。"""

    relative_path: str
    document_id: str
    title: str
    subsystem: str
    topic: str
    definition: str
    symptoms: tuple[str, ...]
    causes: tuple[str, ...]
    required_data: tuple[str, ...]
    verification_steps: tuple[str, ...]
    actions: tuple[str, ...]
    boundaries: tuple[str, ...]


# 具体的知识数据，一共12篇文档
DOCUMENT_SPECS: tuple[KnowledgeDocumentSpec, ...] = (
    # 电压不一致
    KnowledgeDocumentSpec(
        relative_path="battery/battery_voltage_inconsistency.md",
        document_id="battery_voltage_inconsistency",
        title="动力电池单体电压不一致问题",
        subsystem="battery",
        topic="voltage_inconsistency",
        definition=(
            "单体电压不一致是指串联电池包中的不同单体在相同电流和相近环境条件下，"
            "表现出明显不同的端电压或电压变化趋势。"
        ),
        symptoms=(
            "充放电过程中单体最大压差持续扩大。",
            "某个单体比其他单体更早达到充电或放电截止电压。",
            "最低电压单体或最高电压单体在多个循环中相对固定。",
        ),
        causes=(
            "单体容量、SOC或老化程度存在差异。",
            "单体直流内阻或极化特性存在差异。",
            "温度分布、连接电阻或采样链路存在异常。",
        ),
        required_data=(
            "同步采集的单体电压、包电流和SOC数据。",
            "单体温度、内阻、容量或历史循环数据。",
            "采样线、连接件和电压采集模块检查结果。",
        ),
        verification_steps=(
            "先检查时间同步、采样跳变和传感器异常。",
            "在相近SOC、电流和温度条件下比较单体电压响应。",
            "结合静置、充电和放电阶段判断差异是否持续存在。",
        ),
        actions=(
            "对压差持续扩大的电池包限制高功率充放电。",
            "结合均衡、容量测试和连接检查进一步定位原因。",
        ),
        boundaries=(
            "仅凭一次电压差异不能确认电芯故障。",
            "具体告警阈值应依据产品规格和运行条件确定。",
        ),
    ),
    # 过充过放
    KnowledgeDocumentSpec(
        relative_path="battery/battery_overcharge_overdischarge.md",
        document_id="battery_overcharge_overdischarge",
        title="动力电池过充与过放风险",
        subsystem="battery",
        topic="overcharge_overdischarge",
        definition=(
            "过充和过放是指电池单体或电池包运行超出允许电压、SOC或容量边界，"
            "可能造成性能衰减和安全风险。"
        ),
        symptoms=(
            "充电时单体电压超过允许上限。",
            "放电时单体电压低于允许下限。",
            "某个单体频繁提前触发充电或放电截止条件。",
        ),
        causes=(
            "SOC估计偏差或单体一致性较差。",
            "充电控制、接触器或电流执行机构异常。",
            "电压采样漂移、均衡能力不足或保护策略失效。",
        ),
        required_data=(
            "单体电压、包电流、SOC和充放电状态。",
            "充电机指令、BMS限值和接触器状态。",
            "告警记录、保护触发记录和时间同步信息。",
        ),
        verification_steps=(
            "确认电压采样值与独立测量结果是否一致。",
            "核对BMS限值、充电机指令和实际电流。",
            "检查异常单体是否在多个循环中重复出现。",
        ),
        actions=(
            "达到安全边界时停止或限制充放电。",
            "完成采样链路、控制链路和电芯状态复核后再恢复运行。",
        ),
        boundaries=(
            "正常电压范围应依据具体电芯体系和产品要求确定。",
            "不能仅根据包电压排除单体过充或过放风险。",
        ),
    ),
    # 内短路
    KnowledgeDocumentSpec(
        relative_path="battery/battery_internal_short_circuit.md",
        document_id="battery_internal_short_circuit",
        title="锂离子电池内短路候选诊断",
        subsystem="battery",
        topic="internal_short_circuit",
        definition=(
            "内短路是电池内部正负极之间形成非预期导电通路的故障形式，"
            "其早期特征可能较弱，通常需要多源数据联合判断。"
        ),
        symptoms=(
            "静置阶段自放电速度异常增大。",
            "无明显外部负载时局部温度或温升异常。",
            "单体电压、温度和一致性指标出现持续性偏离。",
        ),
        causes=(
            "制造缺陷、机械损伤或异物引起内部导通。",
            "析锂、枝晶或隔膜损伤形成泄漏通路。",
            "外部采样和连接故障可能产生相似表象。",
        ),
        required_data=(
            "长时间静置电压、自放电速率和环境温度。",
            "单体温度、绝缘状态和历史工况。",
            "外部连接、采样回路和传感器检查结果。",
        ),
        verification_steps=(
            "先排除电压采样、外部泄漏和连接异常。",
            "比较相同温度与SOC条件下的静置电压变化。",
            "结合温度、绝缘和重复试验判断异常是否稳定。",
        ),
        actions=(
            "对持续异常单体进行隔离和进一步安全检查。",
            "避免仅依据单一阈值直接确认内短路。",
        ),
        boundaries=(
            "本知识条目只支持候选诊断，不代表故障确认。",
            "涉及安全风险时必须由专业人员进行复核。",
        ),
    ),
    # 热失控
    KnowledgeDocumentSpec(
        relative_path="thermal/battery_thermal_runaway.md",
        document_id="battery_thermal_runaway",
        title="动力电池热失控风险识别",
        subsystem="thermal",
        topic="thermal_runaway",
        definition=(
            "热失控是电池内部放热反应超过散热能力并导致温度快速、自加速上升的危险状态。"
        ),
        symptoms=(
            "单体温度或温升速率明显异常。",
            "局部热点与周围测点温差持续扩大。",
            "温度异常同时伴随电压突变、绝缘异常或气体信号。",
        ),
        causes=(
            "内短路、过充、外部加热或机械损伤。",
            "冷却能力不足导致热量持续积累。",
            "传感器故障也可能造成虚假高温信号。",
        ),
        required_data=(
            "多点温度、温升速率和环境温度。",
            "单体电压、电流、SOC及冷却系统状态。",
            "绝缘、烟气或其他可用安全信号。",
        ),
        verification_steps=(
            "检查温度信号连续性和相邻测点一致性。",
            "核对冷却执行状态与实际流量或风量。",
            "联合分析温度、电压、电流和绝缘信号。",
        ),
        actions=(
            "出现快速温升或多信号异常时执行安全降级或停止运行。",
            "将高风险对象交由专业安全流程处置。",
        ),
        boundaries=(
            "单点高温不能自动等同于热失控。",
            "安全动作应服从产品级保护策略和应急规范。",
        ),
    ),
    # 热管理故障
    KnowledgeDocumentSpec(
        relative_path="thermal/thermal_management_faults.md",
        document_id="thermal_management_faults",
        title="动力系统热管理常见故障",
        subsystem="thermal",
        topic="thermal_management_fault",
        definition=(
            "热管理故障是指冷却、加热、换热或温度控制能力不能满足动力系统运行需求。"
        ),
        symptoms=(
            "最高温度或最大温差超过目标范围。",
            "冷却指令存在但温度下降不明显。",
            "泵、风扇、阀或压缩机状态与控制指令不一致。",
        ),
        causes=(
            "冷却液不足、气阻、堵塞或泄漏。",
            "泵、风扇、阀门或压缩机执行异常。",
            "温度传感器、控制逻辑或通信链路异常。",
        ),
        required_data=(
            "温度测点、环境温度和负载功率。",
            "泵速、风扇转速、阀位和冷却液温度。",
            "控制指令、反馈状态及故障码。",
        ),
        verification_steps=(
            "先检查温度传感器合理性。",
            "比较控制指令和执行机构反馈。",
            "结合入口出口温度和流量判断换热能力。",
        ),
        actions=(
            "热管理能力不足时限制功率或停止高负荷运行。",
            "按传感器、执行机构和回路顺序排查。",
        ),
        boundaries=(
            "温差异常可能同时受到电芯状态和工况分布影响。",
            "不能只依据单个执行机构状态判断整套热管理性能。",
        ),
    ),
    # 快充约束
    KnowledgeDocumentSpec(
        relative_path="charging/fast_charging_constraints.md",
        document_id="fast_charging_constraints",
        title="动力电池快充约束与风险",
        subsystem="charging",
        topic="fast_charging",
        definition=(
            "快充约束是根据电压、SOC、温度、电流和电池状态确定允许充电功率的边界。"
        ),
        symptoms=(
            "高SOC阶段仍保持较大充电电流。",
            "单体电压接近上限且压差增大。",
            "充电过程中温度或温差快速上升。",
        ),
        causes=(
            "充电限值计算不合理或数据延迟。",
            "电芯一致性、温度分布或老化程度差异。",
            "充电机与BMS指令执行不一致。",
        ),
        required_data=(
            "单体电压、SOC、温度和充电电流。",
            "BMS允许电流、充电机请求值和实际值。",
            "电池容量、内阻和老化状态。",
        ),
        verification_steps=(
            "核对BMS限值与充电机实际输出。",
            "按SOC区间分析允许电流与实际电流。",
            "识别限制充电能力的最低裕量单体。",
        ),
        actions=(
            "接近电压或温度边界时降低充电功率。",
            "出现过压或超温风险时停止充电并检查原因。",
        ),
        boundaries=(
            "快充限值必须结合具体电芯和热管理能力确定。",
            "本条目不提供通用固定充电倍率。",
        ),
    ),
    # 充电通信异常
    KnowledgeDocumentSpec(
        relative_path="charging/charging_communication_faults.md",
        document_id="charging_communication_faults",
        title="充电机与BMS通信异常",
        subsystem="charging",
        topic="charging_communication",
        definition=(
            "充电通信异常是指BMS与充电设备之间的报文、状态或控制指令不能正常交换。"
        ),
        symptoms=(
            "充电握手失败或充电流程中断。",
            "请求电压、电流与实际输出长时间不一致。",
            "报文超时、计数器异常或状态机停滞。",
        ),
        causes=(
            "通信链路、供电、终端电阻或连接器异常。",
            "报文周期、信号定义或协议版本不一致。",
            "BMS或充电机状态机逻辑异常。",
        ),
        required_data=(
            "通信报文、时间戳和错误计数。",
            "BMS和充电机状态机状态。",
            "请求值、允许值、实际输出及连接状态。",
        ),
        verification_steps=(
            "检查物理连接、供电和通信质量。",
            "确认关键报文周期、计数器和校验字段。",
            "沿充电状态机定位首次出现分歧的位置。",
        ),
        actions=(
            "通信状态不确定时禁止继续高功率充电。",
            "保存完整报文和状态日志用于联合分析。",
        ),
        boundaries=(
            "通信中断不一定代表电池本体故障。",
            "协议字段和超时要求应以具体接口定义为准。",
        ),
    ),
    # 故障验证方法
    KnowledgeDocumentSpec(
        relative_path="maintenance/battery_fault_verification.md",
        document_id="battery_fault_verification",
        title="动力电池故障验证方法",
        subsystem="multi_system",
        topic="fault_verification",
        definition=(
            "故障验证是通过数据核验、重复测试和交叉证据判断异常是否真实存在及其可能来源。"
        ),
        symptoms=(
            "同一异常在不同数据源中的表现不一致。",
            "告警存在但原始数据缺少明显异常。",
            "异常仅在特定工况或时间段出现。",
        ),
        causes=(
            "真实部件故障。",
            "传感器、采样、通信或时间同步问题。",
            "阈值、控制逻辑或数据处理错误。",
        ),
        required_data=(
            "原始高频数据和告警前后时间窗口。",
            "传感器、控制器和执行机构状态。",
            "重复试验、对照样本和维修记录。",
        ),
        verification_steps=(
            "确认原始数据完整性和时间同步。",
            "使用独立测量或冗余信号交叉验证。",
            "在安全条件下复现工况并比较结果。",
        ),
        actions=(
            "先验证数据可信度，再进行部件更换。",
            "记录假设、验证步骤、证据和结论。",
        ),
        boundaries=(
            "无法复现不等于异常不存在。",
            "涉及高压和热安全的验证必须遵守安全流程。",
        ),
    ),
    # 维修策略
    KnowledgeDocumentSpec(
        relative_path="maintenance/maintenance_strategy.md",
        document_id="maintenance_strategy",
        title="动力系统维修策略制定",
        subsystem="multi_system",
        topic="maintenance_strategy",
        definition=(
            "维修策略用于根据风险、证据、影响范围和可验证性确定检查、降级、维修或更换措施。"
        ),
        symptoms=(
            "异常重复发生并影响系统性能。",
            "风险等级提升或安全裕量下降。",
            "不同团队对故障原因和处置优先级存在分歧。",
        ),
        causes=(
            "根因证据不足。",
            "故障影响范围和维修成本尚未量化。",
            "数据、软件和硬件问题相互耦合。",
        ),
        required_data=(
            "故障频率、严重程度和影响范围。",
            "验证结果、部件履历和维修成本。",
            "软件版本、标定版本和变更记录。",
        ),
        verification_steps=(
            "按安全风险和业务影响确定优先级。",
            "将候选原因与验证证据逐项对应。",
            "维修后执行回归测试并确认异常是否消失。",
        ),
        actions=(
            "优先执行低风险、可验证的检查项目。",
            "高风险或证据不足场景保留人工审批。",
        ),
        boundaries=(
            "维修建议不能替代现场安全规范。",
            "更换部件前应尽量排除数据和软件问题。",
        ),
    ),
    # 数字孪生
    KnowledgeDocumentSpec(
        relative_path="digital_twin/battery_digital_twin.md",
        document_id="battery_digital_twin",
        title="动力电池数字孪生基础",
        subsystem="multi_system",
        topic="battery_digital_twin",
        definition=(
            "动力电池数字孪生通过模型、运行数据和参数更新描述真实电池的状态与行为。"
        ),
        symptoms=(
            "模型输出与真实电池数据偏差持续增大。",
            "模型参数无法适应温度、SOC或老化变化。",
            "不同运行阶段的预测精度差异明显。",
        ),
        causes=(
            "模型结构或参数不能覆盖当前工况。",
            "传感数据质量不足或模型更新不及时。",
            "老化、热状态和电状态耦合未被充分描述。",
        ),
        required_data=(
            "电压、电流、温度、SOC和容量数据。",
            "模型参数、版本和更新时间。",
            "预测误差及运行工况分布。",
        ),
        verification_steps=(
            "比较模型输出与实测数据的残差。",
            "按温度、SOC和工况区间评估模型性能。",
            "记录参数更新前后的性能变化。",
        ),
        actions=(
            "模型失配时更新参数或切换适用模型。",
            "关键控制动作前保留边界检查和人工审核。",
        ),
        boundaries=(
            "数字孪生不等同于真实系统本身。",
            "模型结论必须结合传感数据和适用范围解释。",
        ),
    ),
    # 云边协调框架
    KnowledgeDocumentSpec(
        relative_path="digital_twin/cloud_edge_collaboration.md",
        document_id="cloud_edge_collaboration",
        title="动力系统云边协同架构",
        subsystem="multi_system",
        topic="cloud_edge_collaboration",
        definition=(
            "云边协同通过边缘侧实时处理与云端集中训练、分析和管理实现能力分工。"
        ),
        symptoms=(
            "边缘计算资源不足以运行复杂模型。",
            "云端更新延迟或通信中断影响模型同步。",
            "云端与边缘模型版本不一致。",
        ),
        causes=(
            "模型规模、通信带宽或部署策略不匹配。",
            "版本管理、回滚和完整性校验不足。",
            "云端与边缘的数据分布存在差异。",
        ),
        required_data=(
            "边缘设备算力、内存、延迟和能耗。",
            "模型版本、发布时间和部署状态。",
            "通信质量、同步记录和推理日志。",
        ),
        verification_steps=(
            "确认模型版本、参数和配置一致性。",
            "评估边缘推理延迟及资源占用。",
            "模拟通信中断和更新失败场景。",
        ),
        actions=(
            "边缘侧保留安全规则和降级能力。",
            "云端更新应支持验证、灰度部署和回滚。",
        ),
        boundaries=(
            "实时安全控制不能完全依赖远程云端响应。",
            "云端建议下发前必须满足边缘侧安全约束。",
        ),
    ),
    # 安全与诊断术语
    KnowledgeDocumentSpec(
        relative_path="common/power_system_safety_terms.md",
        document_id="power_system_safety_terms",
        title="动力系统安全与诊断术语",
        subsystem="multi_system",
        topic="safety_terms",
        definition=(
            "本条目统一PowerAgent中风险、异常、候选原因、故障确认和人工复核等术语。"
        ),
        symptoms=(
            "异常表示数据或状态偏离预期，但不必然代表部件故障。",
            "候选原因表示可以解释现象但尚未被证据确认的原因。",
            "故障确认需要稳定、可追溯且能够排除主要替代解释的证据。",
        ),
        causes=(
            "术语混用可能导致模型过度诊断。",
            "将相关性描述为因果关系会降低报告可信度。",
            "忽略适用边界可能导致不恰当处置。",
        ),
        required_data=(
            "原始现象、运行条件和时间范围。",
            "候选原因、支持证据和反例。",
            "验证步骤、确认状态和责任人。",
        ),
        verification_steps=(
            "检查每个结论是否具有对应证据。",
            "区分已观察事实、模型推断和人工判断。",
            "对高风险结论设置人工复核。",
        ),
        actions=(
            "报告中明确标注不确定性和缺失信息。",
            "无充分证据时输出拒答或补充信息要求。",
        ),
        boundaries=(
            "Agent生成内容不能替代专业安全决策。",
            "术语定义应在后续企业规范接入时同步更新。",
        ),
    ),
)


# 格式化辅助函数
def format_bullets(items: tuple[str, ...]) -> str:
    """将字符串列表格式化为Markdown项目符号。"""

    return "\n".join(f"- {item}" for item in items)

# 核心渲染函数
def render_document(spec: KnowledgeDocumentSpec) -> str:
    """将结构化定义转换为统一Markdown知识文档。"""

    return f"""---
document_id: {spec.document_id}
title: {spec.title}
subsystem: {spec.subsystem}
topic: {spec.topic}
version: "1.0"
source_type: curated_seed
---

# 定义

{spec.definition}

# 典型现象

{format_bullets(spec.symptoms)}

# 可能原因

{format_bullets(spec.causes)}

# 所需数据

{format_bullets(spec.required_data)}

# 验证步骤

{format_bullets(spec.verification_steps)}

# 处置建议

{format_bullets(spec.actions)}

# 适用边界

{format_bullets(spec.boundaries)}
"""


# 写入文件（幂等控制）
def create_knowledge_base(*, overwrite: bool = False) -> tuple[int, int]:
    """创建初始知识库，返回新增和跳过文件数。"""

    created_count = 0
    skipped_count = 0

    for spec in DOCUMENT_SPECS:
        output_path = KNOWLEDGE_BASE_DIR / spec.relative_path
        output_path.parent.mkdir(parents=True, exist_ok=True)

        if output_path.exists() and not overwrite:
            skipped_count += 1
            continue

        output_path.write_text(
            render_document(spec),
            encoding="utf-8",
        )
        created_count += 1

    return created_count, skipped_count


def main() -> None:
    """命令行入口。"""

    parser = argparse.ArgumentParser(
        description="创建PowerAgent初始动力系统知识语料"
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="覆盖已经存在的种子知识文档",
    )
    args = parser.parse_args()

    created_count, skipped_count = create_knowledge_base(
        overwrite=args.overwrite
    )

    print("PowerAgent初始知识语料创建完成")
    print(f"知识库目录：{KNOWLEDGE_BASE_DIR}")
    print(f"新建文档数：{created_count}")
    print(f"跳过文档数：{skipped_count}")
    print(f"文档总数：{len(DOCUMENT_SPECS)}")


if __name__ == "__main__":
    main()