"""首批动力系统Skills业务闭环演示。"""

from __future__ import annotations

from agent_core import SkillRegistry
from skills import create_default_skills


def main() -> None:
    """执行电池、温度、充电、数字孪生、参数寻优、诊断和报告流程。"""

    registry = SkillRegistry()

    for skill in create_default_skills():
        registry.register(skill)

    # 1. 分析电池电压状态
    battery_result = registry.invoke(
        "battery_analysis",
        {
            "cell_voltages_v": [
                3.652,
                3.648,
                3.571,
                3.655,
            ],
            "spread_threshold_v": 0.05,
        },
    )

    # 2. 分析动力电池温度状态
    thermal_result = registry.invoke(
        "thermal_analysis",
        {
            "temperatures_c": [
                27.0,
                27.5,
                34.2,
                28.1,
            ],
            "spread_threshold_c": 5.0,
        },
    )

    # 3. 检查当前充电过程安全约束
    charging_result = registry.invoke(
        "charging_analysis",
        {
            "pack_voltage_v": 395.0,
            "charging_current_a": 28.0,
            "soc_pct": 95.0,
            "maximum_temperature_c": 34.2,
            "maximum_pack_voltage_v": 400.0,
            "maximum_charging_current_a": 50.0,
            "high_soc_current_limit_a": 20.0,
        },
    )

    # 4. 预测候选充电参数下的未来状态
    digital_twin_result = registry.invoke(
        "digital_twin",
        {
            "current_soc_pct": 95.0,
            "current_pack_voltage_v": 395.0,
            "current_maximum_temperature_c": 34.2,
            "current_charging_current_a": 28.0,
            "candidate_charging_current_a": 18.0,
            "forecast_minutes": 20.0,
            "cooling_power_w": 20.0,
            "battery_capacity_ah": 100.0,
            "pack_internal_resistance_ohm": 0.05,
            "effective_thermal_capacity_j_per_c": (
                100000.0
            ),
            "ocv_rise_per_soc_pct_v": 0.05,
            "charging_efficiency": 0.98,
            "ambient_temperature_c": 25.0,
            "maximum_pack_voltage_v": 400.0,
            "maximum_charging_current_a": 50.0,
            "maximum_charging_temperature_c": 50.0,
            "high_soc_threshold_pct": 90.0,
            "high_soc_current_limit_a": 20.0,
        },
    )


    # 5. 搜索满足安全约束的推荐充电参数
    optimization_result = registry.invoke(
        "parameter_optimization",
        {
            "current_soc_pct": 95.0,
            "current_pack_voltage_v": 395.0,
            "current_maximum_temperature_c": 34.2,
            "current_charging_current_a": 28.0,
            "candidate_charging_currents_a": [
                10.0,
                18.0,
                25.0,
            ],
            "candidate_cooling_powers_w": [
                0.0,
                20.0,
            ],
            "forecast_minutes": 20.0,
            "battery_capacity_ah": 100.0,
            "pack_internal_resistance_ohm": 0.05,
            "effective_thermal_capacity_j_per_c": (
                100000.0
            ),
            "ocv_rise_per_soc_pct_v": 0.05,
            "charging_efficiency": 0.98,
            "ambient_temperature_c": 25.0,
            "maximum_pack_voltage_v": 400.0,
            "maximum_charging_current_a": 50.0,
            "maximum_charging_temperature_c": 50.0,
            "high_soc_threshold_pct": 90.0,
            "high_soc_current_limit_a": 20.0,
        },
    )

    # 6. 根据已有分析结果生成候选诊断
    diagnosis_result = registry.invoke(
        "diagnosis",
        {
            "issue_summary": "电池组压差扩大且温差偏高",
            "battery_risk": (
                battery_result.consistency_risk
            ),
            "thermal_risk": (
                thermal_result
                .temperature_inconsistency_risk
            ),
            "charging_risk": charging_result.has_risk,
            "abnormal_cell_numbers": [
                battery_result.minimum_cell_number
            ],
            "abnormal_sensor_numbers": (
                thermal_result
                .overtemperature_sensor_numbers
            ),
            "violated_constraints": (
                charging_result.violated_constraints
            ),
        },
    )

    # 7. 将参数寻优结果转换为模拟云端策略
    dispatch_result = registry.invoke(
        "cloud_dispatch",
        {
            "optimization_status": (
                optimization_result.status
            ),
            "recommended_candidate": (
                optimization_result.recommended_candidate
            ),
            "optimization_reason": (
                optimization_result.selection_reason
            ),
            "current_risk_level": (
                diagnosis_result.risk_level
            ),
            "strategy_id": "CHARGE-STRATEGY-001",
            "strategy_version": "1.0.0",
            "target_device_id": "PACK-001",
            "valid_for_minutes": 30,
            "allow_automatic_dispatch": True,
            "force_manual_review": False,
            "maximum_dispatch_current_a": 30.0,
            "maximum_dispatch_cooling_power_w": 50.0,
        },
        context={
            "trace_id": "demo-cloud-dispatch-001",
            "source": "power_skills_demo",
        },
    )


    # 8. 根据参数寻优状态构造报告内容 
    optimization_findings: list[str] = [] 
    optimization_evidence: list[str] = [] 
    optimization_unresolved_items: list[str] = [] 
    
    if optimization_result.recommended_candidate is not None: 
        recommended_candidate = ( 
            optimization_result.recommended_candidate 
        ) 
        
        optimization_findings.append( 
            ( "推荐充电参数："
              f"{recommended_candidate.candidate_charging_current_a}A，" 
              "等效冷却功率：" 
              f"{recommended_candidate.cooling_power_w}W。" 
            ) 
        ) 
        
        optimization_evidence.extend( 
            [ 
                ( 
                    "推荐方案综合评分：" 
                    f"{recommended_candidate.score}" 
                ), 
                ( 
                    "推荐方案预测SOC：" 
                    f"{recommended_candidate.prediction.predicted_soc_pct}%" 
                ), 
                ( 
                    "推荐方案预测电池组电压：" 
                    f"{recommended_candidate.prediction.predicted_pack_voltage_v}V" 
                ), 
                ( 
                    "推荐方案预测最高温度：" 
                    f"{recommended_candidate.prediction.predicted_maximum_temperature_c}℃" 
                ), 
                ( 
                    "参数寻优共评估" 
                    f"{optimization_result.evaluated_candidate_count}" 
                    "个候选方案，其中" 
                    f"{optimization_result.feasible_candidate_count}" 
                    "个满足安全约束。" 
                ), 
            ] 
        ) 
    else: 
        optimization_findings.append( 
            "参数寻优未找到满足全部安全约束的候选方案。" 
        ) 
        
        optimization_unresolved_items.append( 
            ( 
                "需要调整候选电流、冷却能力、预测时长" "或安全边界后重新执行参数寻优。" 
            ) 
        )


    dispatch_findings: list[str] = [
        (
            "模拟云端策略状态："
            f"{dispatch_result.status.value}。"
        )
    ]
    dispatch_evidence: list[str] = [
        *dispatch_result.decision_evidence,
        (
            "策略安全检查结果："
            f"{dispatch_result.safety_checks_passed}。"
        ),
        (
            "是否需要人工复核："
            f"{dispatch_result.requires_manual_review}。"
        ),
        (
            "策略追踪标识："
            f"{dispatch_result.source_trace_id}。"
        ),
    ]
    dispatch_unresolved_items: list[str] = []
    if dispatch_result.strategy is not None:
        dispatch_findings.append(
            (
                "模拟策略建议充电电流："
                f"{dispatch_result.strategy.charging_current_a}A，"
                "建议冷却功率："
                f"{dispatch_result.strategy.cooling_power_w}W。"
            )
        )
        dispatch_evidence.extend(
            [
                (
                    "模拟策略编号："
                    f"{dispatch_result.strategy.strategy_id}。"
                ),
                (
                    "策略有效时间："
                    f"{dispatch_result.strategy.valid_for_minutes}"
                    "分钟。"
                ),
                (
                    "策略仅用于模拟："
                    f"{dispatch_result.strategy.simulation_only}。"
                ),
            ]
        )
    if dispatch_result.blocking_reasons:
        dispatch_unresolved_items.append(
            (
                "云端模拟策略被阻断，原因："
                + "、".join(
                    dispatch_result.blocking_reasons
                )
                + "。"
            )
        )
    if dispatch_result.requires_manual_review:
        dispatch_unresolved_items.append(
            "当前模拟策略需要人工审核后才能继续处理。"
        )

    # 9. 生成包含预测、寻优和下发结果的结构化报告
    report_result = registry.invoke(
        "report_generation",
        {
            "original_question": (
                "电池组压差扩大且温差偏高，"
                "评估并推荐后续充电控制参数。"
            ),
            "findings": [
                diagnosis_result.primary_cause,
                *diagnosis_result.alternative_causes,
                (
                    "单一候选充电策略数字孪生预测"
                    f"可行性：{digital_twin_result.is_feasible}"
                ),
                *optimization_findings,
                *dispatch_findings,
            ],
            "risk_level": diagnosis_result.risk_level,
            "recommendations": (
                diagnosis_result.verification_steps
            ),
            "evidence": [
                *diagnosis_result.evidence,
                (
                    "单一候选预测SOC："
                    f"{digital_twin_result.predicted_soc_pct}%"
                ),
                (
                    "单一候选预测电池组电压："
                    f"{digital_twin_result.predicted_pack_voltage_v}V"
                ),
                (
                    "单一候选预测最高温度："
                    f"{digital_twin_result.predicted_maximum_temperature_c}℃"
                ),
                *optimization_evidence,
                *dispatch_evidence,
            ],
            "unresolved_items": [
                "需要结合历史数据确认异常持续性。",
                (
                    "数字孪生预测基于简化模型，"
                    "实际应用前需要真实模型校准。"
                ),
                *optimization_unresolved_items,
                *dispatch_unresolved_items,
            ],
            "device_id": "PACK-001",
        },
    )

    print("电池分析结果：")
    print(battery_result.model_dump_json(indent=2))

    print("\n温度分析结果：")
    print(thermal_result.model_dump_json(indent=2))

    print("\n充电分析结果：")
    print(charging_result.model_dump_json(indent=2))

    print("\n数字孪生预测结果：")
    print(digital_twin_result.model_dump_json(indent=2,))

    print("\n参数寻优结果：") 
    print( optimization_result.model_dump_json( indent=2,))

    print("\n候选诊断结果：")
    print(diagnosis_result.model_dump_json(indent=2))

    print("\n模拟云端策略下发结果：")
    print(dispatch_result.model_dump_json(indent=2,))

    print("\n结构化报告：")
    print(report_result.model_dump_json(indent=2))


if __name__ == "__main__":
    main()