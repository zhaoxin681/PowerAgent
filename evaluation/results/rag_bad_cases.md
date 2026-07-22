# RAG Bad Cases

该文件由RAG自动评测脚本生成。

Bad Case数量：8

## RAG-002

### 用户问题

为什么不能仅根据单一阈值直接确认电池内短路？

### 检索结果

```json
[
  {
    "chunk_id": "battery_internal_short_circuit:e6d76ca14bff3a96",
    "document_id": "battery_internal_short_circuit",
    "title": "锂离子电池内短路候选诊断",
    "content": "章节：处置建议\n\n- 对持续异常单体进行隔离和进一步安全检查。\n- 避免仅依据单一阈值直接确认内短路。",
    "score": 0.23203253746032715,
    "rank": 1,
    "source_path": "battery/battery_internal_short_circuit.md",
    "section_path": "处置建议",
    "page_number": null,
    "subsystem": "battery",
    "topic": "internal_short_circuit",
    "metadata": {
      "document_version": "1.0",
      "source_type": "curated_seed"
    }
  },
  {
    "chunk_id": "battery_internal_short_circuit:7b5282965bfa7526",
    "document_id": "battery_internal_short_circuit",
    "title": "锂离子电池内短路候选诊断",
    "content": "章节：定义\n\n内短路是电池内部正负极之间形成非预期导电通路的故障形式，其早期特征可能较弱，通常需要多源数据联合判断。",
    "score": 0.21477991342544556,
    "rank": 2,
    "source_path": "battery/battery_internal_short_circuit.md",
    "section_path": "定义",
    "page_number": null,
    "subsystem": "battery",
    "topic": "internal_short_circuit",
    "metadata": {
      "source_type": "curated_seed",
      "document_version": "1.0"
    }
  },
  {
    "chunk_id": "battery_internal_short_circuit:a6783cbc2745451d",
    "document_id": "battery_internal_short_circuit",
    "title": "锂离子电池内短路候选诊断",
    "content": "章节：可能原因\n\n- 制造缺陷、机械损伤或异物引起内部导通。\n- 析锂、枝晶或隔膜损伤形成泄漏通路。\n- 外部采样和连接故障可能产生相似表象。",
    "score": 0.13627123832702637,
    "rank": 3,
    "source_path": "battery/battery_internal_short_circuit.md",
    "section_path": "可能原因",
    "page_number": null,
    "subsystem": "battery",
    "topic": "internal_short_circuit",
    "metadata": {
      "document_version": "1.0",
      "source_type": "curated_seed"
    }
  },
  {
    "chunk_id": "battery_internal_short_circuit:d98a238b060b1fc1",
    "document_id": "battery_internal_short_circuit",
    "title": "锂离子电池内短路候选诊断",
    "content": "章节：所需数据\n\n- 长时间静置电压、自放电速率和环境温度。\n- 单体温度、绝缘状态和历史工况。\n- 外部连接、采样回路和传感器检查结果。",
    "score": 0.11941665410995483,
    "rank": 4,
    "source_path": "battery/battery_internal_short_circuit.md",
    "section_path": "所需数据",
    "page_number": null,
    "subsystem": "battery",
    "topic": "internal_short_circuit",
    "metadata": {
      "document_version": "1.0",
      "source_type": "curated_seed"
    }
  }
]
```

### RAG回答

```json
{
  "question": "为什么不能仅根据单一阈值直接确认电池内短路？",
  "answer": "根据现有证据，不能仅依据单一阈值直接确认电池内短路，原因包括：内短路早期特征可能较弱，需要多源数据联合判断；外部采样和连接故障可能产生相似表象，容易误判；证据明确建议避免仅依据单一阈值直接确认内短路。",
  "citations": [
    {
      "chunk_id": "battery_internal_short_circuit:e6d76ca14bff3a96",
      "document_id": "battery_internal_short_circuit",
      "title": "锂离子电池内短路候选诊断",
      "section_path": "处置建议",
      "page_number": null,
      "supported_claim": "证据明确建议避免仅依据单一阈值直接确认内短路。",
      "evidence_text": "避免仅依据单一阈值直接确认内短路。"
    },
    {
      "chunk_id": "battery_internal_short_circuit:7b5282965bfa7526",
      "document_id": "battery_internal_short_circuit",
      "title": "锂离子电池内短路候选诊断",
      "section_path": "定义",
      "page_number": null,
      "supported_claim": "内短路早期特征可能较弱，需要多源数据联合判断。",
      "evidence_text": "内短路是电池内部正负极之间形成非预期导电通路的故障形式，其早期特征可能较弱，通常需要多源数据联合判断。"
    },
    {
      "chunk_id": "battery_internal_short_circuit:a6783cbc2745451d",
      "document_id": "battery_internal_short_circuit",
      "title": "锂离子电池内短路候选诊断",
      "section_path": "可能原因",
      "page_number": null,
      "supported_claim": "外部采样和连接故障可能产生相似表象，容易误判。",
      "evidence_text": "外部采样和连接故障可能产生相似表象。"
    }
  ],
  "confidence": 0.9,
  "sufficient_evidence": true,
  "missing_information": [],
  "needs_human_review": true
}
```

### 检查结果

```json
{
  "document_hit_at_k": {
    "passed": true,
    "expected": [
      "battery_internal_short_circuit"
    ],
    "actual": [
      "battery_internal_short_circuit",
      "battery_internal_short_circuit",
      "battery_internal_short_circuit",
      "battery_internal_short_circuit"
    ]
  },
  "chunk_hit_at_k": {
    "passed": true,
    "expected": [],
    "actual": [
      "battery_internal_short_circuit:e6d76ca14bff3a96",
      "battery_internal_short_circuit:7b5282965bfa7526",
      "battery_internal_short_circuit:a6783cbc2745451d",
      "battery_internal_short_circuit:d98a238b060b1fc1"
    ],
    "applicable": false
  },
  "reciprocal_rank": {
    "passed": true,
    "expected": [
      "battery_internal_short_circuit"
    ],
    "actual": 1.0
  },
  "source_keywords": {
    "passed": false,
    "expected": [
      "定义",
      "适用边界"
    ],
    "matched": [
      "定义"
    ]
  },
  "retrieval_overall": {
    "passed": false
  },
  "answer_mode": {
    "passed": true,
    "expected": "answer",
    "actual": "answer"
  },
  "sufficient_evidence": {
    "passed": true,
    "expected": true,
    "actual": true
  },
  "question_preserved": {
    "passed": true,
    "expected": "为什么不能仅根据单一阈值直接确认电池内短路？",
    "actual": "为什么不能仅根据单一阈值直接确认电池内短路？"
  },
  "citation_count": {
    "passed": true,
    "expected_minimum": 1,
    "actual": 3
  },
  "citation_validity": {
    "passed": true,
    "details": [
      {
        "chunk_id": "battery_internal_short_circuit:e6d76ca14bff3a96",
        "document_id": "battery_internal_short_circuit",
        "valid": true
      },
      {
        "chunk_id": "battery_internal_short_circuit:7b5282965bfa7526",
        "document_id": "battery_internal_short_circuit",
        "valid": true
      },
      {
        "chunk_id": "battery_internal_short_circuit:a6783cbc2745451d",
        "document_id": "battery_internal_short_circuit",
        "valid": true
      }
    ]
  },
  "answer_concepts": {
    "passed": false,
    "matched": 1,
    "total": 3,
    "details": [
      {
        "alternatives": [
          "需要多源数据联合判断",
          "多源数据"
        ],
        "matched": true
      },
      {
        "alternatives": [
          "只支持候选诊断",
          "不能直接确认内短路"
        ],
        "matched": false
      },
      {
        "alternatives": [
          "排除采样和连接异常",
          "排除替代解释"
        ],
        "matched": false
      }
    ]
  },
  "forbidden_claims": {
    "passed": true,
    "expected_absent": [],
    "matched": []
  },
  "human_review": {
    "passed": true,
    "applicable": true,
    "expected": true,
    "actual": true
  },
  "answer_overall": {
    "passed": false
  },
  "overall": {
    "passed": false
  }
}
```

### 人工分析

- 错误层级：检索 / 生成 / 引用 / 标注
- 错误类型：
- 可能原因：
- 修复建议：
- 回归状态：待修复

### 自动分类

EVIDENCE_SECTION_MISS, ANSWER_CONCEPT_MISS

## RAG-004

### 用户问题

排查充电通信中断时需要采集哪些数据并如何定位？

### 检索结果

```json
[
  {
    "chunk_id": "charging_communication_faults:cc1811a929d847a3",
    "document_id": "charging_communication_faults",
    "title": "充电机与BMS通信异常",
    "content": "章节：适用边界\n\n- 通信中断不一定代表电池本体故障。\n- 协议字段和超时要求应以具体接口定义为准。",
    "score": 0.1737356185913086,
    "rank": 1,
    "source_path": "charging/charging_communication_faults.md",
    "section_path": "适用边界",
    "page_number": null,
    "subsystem": "charging",
    "topic": "charging_communication",
    "metadata": {
      "source_type": "curated_seed",
      "document_version": "1.0"
    }
  },
  {
    "chunk_id": "charging_communication_faults:6b86bd2ad14df3bd",
    "document_id": "charging_communication_faults",
    "title": "充电机与BMS通信异常",
    "content": "章节：典型现象\n\n- 充电握手失败或充电流程中断。\n- 请求电压、电流与实际输出长时间不一致。\n- 报文超时、计数器异常或状态机停滞。",
    "score": 0.12449467182159424,
    "rank": 2,
    "source_path": "charging/charging_communication_faults.md",
    "section_path": "典型现象",
    "page_number": null,
    "subsystem": "charging",
    "topic": "charging_communication",
    "metadata": {
      "document_version": "1.0",
      "source_type": "curated_seed"
    }
  }
]
```

### RAG回答

```json
{
  "question": "排查充电通信中断时需要采集哪些数据并如何定位？",
  "answer": "根据现有证据，充电通信中断的典型现象包括充电握手失败或充电流程中断、请求电压/电流与实际输出长时间不一致、报文超时、计数器异常或状态机停滞。但证据未提供具体需要采集的数据项和定位步骤。",
  "citations": [
    {
      "chunk_id": "charging_communication_faults:6b86bd2ad14df3bd",
      "document_id": "charging_communication_faults",
      "title": "充电机与BMS通信异常",
      "section_path": "典型现象",
      "page_number": null,
      "supported_claim": "充电通信中断的典型现象包括充电握手失败或充电流程中断、请求电压/电流与实际输出长时间不一致、报文超时、计数器异常或状态机停滞。",
      "evidence_text": "章节：典型现象\n\n- 充电握手失败或充电流程中断。\n- 请求电压、电流与实际输出长时间不一致。\n- 报文超时、计数器异常或状态机停滞。"
    }
  ],
  "confidence": 0.3,
  "sufficient_evidence": false,
  "missing_information": [
    "需要采集的具体数据项（如CAN报文、电压电流波形等）",
    "定位步骤或排查流程",
    "协议字段和超时要求的具体定义"
  ],
  "needs_human_review": true
}
```

### 检查结果

```json
{
  "document_hit_at_k": {
    "passed": true,
    "expected": [
      "charging_communication_faults"
    ],
    "actual": [
      "charging_communication_faults",
      "charging_communication_faults"
    ]
  },
  "chunk_hit_at_k": {
    "passed": true,
    "expected": [],
    "actual": [
      "charging_communication_faults:cc1811a929d847a3",
      "charging_communication_faults:6b86bd2ad14df3bd"
    ],
    "applicable": false
  },
  "reciprocal_rank": {
    "passed": true,
    "expected": [
      "charging_communication_faults"
    ],
    "actual": 1.0
  },
  "source_keywords": {
    "passed": false,
    "expected": [
      "所需数据",
      "验证步骤"
    ],
    "matched": []
  },
  "retrieval_overall": {
    "passed": false
  },
  "answer_mode": {
    "passed": false,
    "expected": "answer",
    "actual": "refuse"
  },
  "sufficient_evidence": {
    "passed": false,
    "expected": true,
    "actual": false
  },
  "question_preserved": {
    "passed": true,
    "expected": "排查充电通信中断时需要采集哪些数据并如何定位？",
    "actual": "排查充电通信中断时需要采集哪些数据并如何定位？"
  },
  "citation_count": {
    "passed": true,
    "expected_minimum": 1,
    "actual": 1
  },
  "citation_validity": {
    "passed": true,
    "details": [
      {
        "chunk_id": "charging_communication_faults:6b86bd2ad14df3bd",
        "document_id": "charging_communication_faults",
        "valid": true
      }
    ]
  },
  "answer_concepts": {
    "passed": false,
    "matched": 0,
    "total": 3,
    "details": [
      {
        "alternatives": [
          "通信报文",
          "时间戳",
          "错误计数"
        ],
        "matched": false
      },
      {
        "alternatives": [
          "状态机状态",
          "充电状态机"
        ],
        "matched": false
      },
      {
        "alternatives": [
          "首次出现分歧的位置",
          "定位首次分歧"
        ],
        "matched": false
      }
    ]
  },
  "forbidden_claims": {
    "passed": true,
    "expected_absent": [],
    "matched": []
  },
  "human_review": {
    "passed": true,
    "applicable": false,
    "expected": null,
    "actual": true
  },
  "answer_overall": {
    "passed": false
  },
  "overall": {
    "passed": false
  }
}
```

### 人工分析

- 错误层级：检索 / 生成 / 引用 / 标注
- 错误类型：
- 可能原因：
- 修复建议：
- 回归状态：待修复

### 自动分类

EVIDENCE_SECTION_MISS, WRONG_ANSWER_MODE, ANSWER_CONCEPT_MISS

## RAG-005

### 用户问题

动力系统中的异常、候选原因和故障确认有什么区别？

### 检索结果

```json
[
  {
    "chunk_id": "power_system_safety_terms:9ca4f43a15e549b0",
    "document_id": "power_system_safety_terms",
    "title": "动力系统安全与诊断术语",
    "content": "章节：典型现象\n\n- 异常表示数据或状态偏离预期，但不必然代表部件故障。\n- 候选原因表示可以解释现象但尚未被证据确认的原因。\n- 故障确认需要稳定、可追溯且能够排除主要替代解释的证据。",
    "score": 0.2360132932662964,
    "rank": 1,
    "source_path": "common/power_system_safety_terms.md",
    "section_path": "典型现象",
    "page_number": null,
    "subsystem": "multi_system",
    "topic": "safety_terms",
    "metadata": {
      "document_version": "1.0",
      "source_type": "curated_seed"
    }
  },
  {
    "chunk_id": "power_system_safety_terms:b518f5c8efdfb783",
    "document_id": "power_system_safety_terms",
    "title": "动力系统安全与诊断术语",
    "content": "章节：所需数据\n\n- 原始现象、运行条件和时间范围。\n- 候选原因、支持证据和反例。\n- 验证步骤、确认状态和责任人。",
    "score": 0.16312575340270996,
    "rank": 2,
    "source_path": "common/power_system_safety_terms.md",
    "section_path": "所需数据",
    "page_number": null,
    "subsystem": "multi_system",
    "topic": "safety_terms",
    "metadata": {
      "document_version": "1.0",
      "source_type": "curated_seed"
    }
  },
  {
    "chunk_id": "power_system_safety_terms:e325507c25628967",
    "document_id": "power_system_safety_terms",
    "title": "动力系统安全与诊断术语",
    "content": "章节：定义\n\n本条目统一PowerAgent中风险、异常、候选原因、故障确认和人工复核等术语。",
    "score": 0.14751780033111572,
    "rank": 3,
    "source_path": "common/power_system_safety_terms.md",
    "section_path": "定义",
    "page_number": null,
    "subsystem": "multi_system",
    "topic": "safety_terms",
    "metadata": {
      "document_version": "1.0",
      "source_type": "curated_seed"
    }
  },
  {
    "chunk_id": "power_system_safety_terms:3faf36e9bc809dfb",
    "document_id": "power_system_safety_terms",
    "title": "动力系统安全与诊断术语",
    "content": "章节：处置建议\n\n- 报告中明确标注不确定性和缺失信息。\n- 无充分证据时输出拒答或补充信息要求。",
    "score": 0.13739871978759766,
    "rank": 4,
    "source_path": "common/power_system_safety_terms.md",
    "section_path": "处置建议",
    "page_number": null,
    "subsystem": "multi_system",
    "topic": "safety_terms",
    "metadata": {
      "source_type": "curated_seed",
      "document_version": "1.0"
    }
  },
  {
    "chunk_id": "battery_fault_verification:dc21e4b5dbf3651a",
    "document_id": "battery_fault_verification",
    "title": "动力电池故障验证方法",
    "content": "章节：典型现象\n\n- 同一异常在不同数据源中的表现不一致。\n- 告警存在但原始数据缺少明显异常。\n- 异常仅在特定工况或时间段出现。",
    "score": 0.12079739570617676,
    "rank": 5,
    "source_path": "maintenance/battery_fault_verification.md",
    "section_path": "典型现象",
    "page_number": null,
    "subsystem": "multi_system",
    "topic": "fault_verification",
    "metadata": {
      "source_type": "curated_seed",
      "document_version": "1.0"
    }
  }
]
```

### RAG回答

```json
{
  "question": "动力系统中的异常、候选原因和故障确认有什么区别？",
  "answer": "根据现有证据，异常表示数据或状态偏离预期，但不必然代表部件故障；候选原因是可解释现象但尚未被证据确认的原因；故障确认需要稳定、可追溯且能够排除主要替代解释的证据。",
  "citations": [
    {
      "chunk_id": "power_system_safety_terms:9ca4f43a15e549b0",
      "document_id": "power_system_safety_terms",
      "title": "动力系统安全与诊断术语",
      "section_path": "典型现象",
      "page_number": null,
      "supported_claim": "异常、候选原因和故障确认的定义区别",
      "evidence_text": "章节：典型现象\n\n- 异常表示数据或状态偏离预期，但不必然代表部件故障。\n- 候选原因表示可以解释现象但尚未被证据确认的原因。\n- 故障确认需要稳定、可追溯且能够排除主要替代解释的证据。"
    }
  ],
  "confidence": 0.9,
  "sufficient_evidence": true,
  "missing_information": [],
  "needs_human_review": true
}
```

### 检查结果

```json
{
  "document_hit_at_k": {
    "passed": true,
    "expected": [
      "power_system_safety_terms"
    ],
    "actual": [
      "power_system_safety_terms",
      "power_system_safety_terms",
      "power_system_safety_terms",
      "power_system_safety_terms",
      "battery_fault_verification"
    ]
  },
  "chunk_hit_at_k": {
    "passed": true,
    "expected": [],
    "actual": [
      "power_system_safety_terms:9ca4f43a15e549b0",
      "power_system_safety_terms:b518f5c8efdfb783",
      "power_system_safety_terms:e325507c25628967",
      "power_system_safety_terms:3faf36e9bc809dfb",
      "battery_fault_verification:dc21e4b5dbf3651a"
    ],
    "applicable": false
  },
  "reciprocal_rank": {
    "passed": true,
    "expected": [
      "power_system_safety_terms"
    ],
    "actual": 1.0
  },
  "source_keywords": {
    "passed": true,
    "expected": [
      "定义",
      "典型现象"
    ],
    "matched": [
      "定义",
      "典型现象"
    ]
  },
  "retrieval_overall": {
    "passed": true
  },
  "answer_mode": {
    "passed": true,
    "expected": "answer",
    "actual": "answer"
  },
  "sufficient_evidence": {
    "passed": true,
    "expected": true,
    "actual": true
  },
  "question_preserved": {
    "passed": true,
    "expected": "动力系统中的异常、候选原因和故障确认有什么区别？",
    "actual": "动力系统中的异常、候选原因和故障确认有什么区别？"
  },
  "citation_count": {
    "passed": true,
    "expected_minimum": 1,
    "actual": 1
  },
  "citation_validity": {
    "passed": true,
    "details": [
      {
        "chunk_id": "power_system_safety_terms:9ca4f43a15e549b0",
        "document_id": "power_system_safety_terms",
        "valid": true
      }
    ]
  },
  "answer_concepts": {
    "passed": false,
    "matched": 2,
    "total": 3,
    "details": [
      {
        "alternatives": [
          "异常不必然代表部件故障",
          "异常不等于故障"
        ],
        "matched": false
      },
      {
        "alternatives": [
          "尚未被证据确认",
          "候选原因"
        ],
        "matched": true
      },
      {
        "alternatives": [
          "排除主要替代解释",
          "故障确认需要证据"
        ],
        "matched": true
      }
    ]
  },
  "forbidden_claims": {
    "passed": true,
    "expected_absent": [],
    "matched": []
  },
  "human_review": {
    "passed": true,
    "applicable": false,
    "expected": null,
    "actual": true
  },
  "answer_overall": {
    "passed": false
  },
  "overall": {
    "passed": false
  }
}
```

### 人工分析

- 错误层级：检索 / 生成 / 引用 / 标注
- 错误类型：
- 可能原因：
- 修复建议：
- 回归状态：待修复

### 自动分类

ANSWER_CONCEPT_MISS

## RAG-008

### 用户问题

数字孪生的输出能否直接等同于真实电池状态？

### 检索结果

```json
[
  {
    "chunk_id": "battery_digital_twin:e42eb0f2e8e23318",
    "document_id": "battery_digital_twin",
    "title": "动力电池数字孪生基础",
    "content": "章节：定义\n\n动力电池数字孪生通过模型、运行数据和参数更新描述真实电池的状态与行为。",
    "score": 0.299146831035614,
    "rank": 1,
    "source_path": "digital_twin/battery_digital_twin.md",
    "section_path": "定义",
    "page_number": null,
    "subsystem": "multi_system",
    "topic": "battery_digital_twin",
    "metadata": {
      "source_type": "curated_seed",
      "document_version": "1.0"
    }
  },
  {
    "chunk_id": "battery_digital_twin:be67e92d3c557b8b",
    "document_id": "battery_digital_twin",
    "title": "动力电池数字孪生基础",
    "content": "章节：典型现象\n\n- 模型输出与真实电池数据偏差持续增大。\n- 模型参数无法适应温度、SOC或老化变化。\n- 不同运行阶段的预测精度差异明显。",
    "score": 0.18514591455459595,
    "rank": 2,
    "source_path": "digital_twin/battery_digital_twin.md",
    "section_path": "典型现象",
    "page_number": null,
    "subsystem": "multi_system",
    "topic": "battery_digital_twin",
    "metadata": {
      "source_type": "curated_seed",
      "document_version": "1.0"
    }
  },
  {
    "chunk_id": "battery_digital_twin:ca6bf87e64d74656",
    "document_id": "battery_digital_twin",
    "title": "动力电池数字孪生基础",
    "content": "章节：可能原因\n\n- 模型结构或参数不能覆盖当前工况。\n- 传感数据质量不足或模型更新不及时。\n- 老化、热状态和电状态耦合未被充分描述。",
    "score": 0.15885907411575317,
    "rank": 3,
    "source_path": "digital_twin/battery_digital_twin.md",
    "section_path": "可能原因",
    "page_number": null,
    "subsystem": "multi_system",
    "topic": "battery_digital_twin",
    "metadata": {
      "source_type": "curated_seed",
      "document_version": "1.0"
    }
  },
  {
    "chunk_id": "battery_digital_twin:c1d3645d5748b941",
    "document_id": "battery_digital_twin",
    "title": "动力电池数字孪生基础",
    "content": "章节：适用边界\n\n- 数字孪生不等同于真实系统本身。\n- 模型结论必须结合传感数据和适用范围解释。",
    "score": 0.15830212831497192,
    "rank": 4,
    "source_path": "digital_twin/battery_digital_twin.md",
    "section_path": "适用边界",
    "page_number": null,
    "subsystem": "multi_system",
    "topic": "battery_digital_twin",
    "metadata": {
      "source_type": "curated_seed",
      "document_version": "1.0"
    }
  },
  {
    "chunk_id": "battery_digital_twin:f9ca2a52809c6cc5",
    "document_id": "battery_digital_twin",
    "title": "动力电池数字孪生基础",
    "content": "章节：验证步骤\n\n- 比较模型输出与实测数据的残差。\n- 按温度、SOC和工况区间评估模型性能。\n- 记录参数更新前后的性能变化。",
    "score": 0.12922334671020508,
    "rank": 5,
    "source_path": "digital_twin/battery_digital_twin.md",
    "section_path": "验证步骤",
    "page_number": null,
    "subsystem": "multi_system",
    "topic": "battery_digital_twin",
    "metadata": {
      "document_version": "1.0",
      "source_type": "curated_seed"
    }
  }
]
```

### RAG回答

```json
{
  "question": "数字孪生的输出能否直接等同于真实电池状态？",
  "answer": "不能。根据现有证据，数字孪生通过模型、运行数据和参数更新描述真实电池的状态与行为，但数字孪生不等同于真实系统本身，模型结论必须结合传感数据和适用范围解释。此外，模型输出与真实电池数据可能存在偏差，且模型参数无法适应温度、SOC或老化变化时，预测精度会下降。因此，数字孪生的输出不能直接等同于真实电池状态。",
  "citations": [
    {
      "chunk_id": "battery_digital_twin:e42eb0f2e8e23318",
      "document_id": "battery_digital_twin",
      "title": "动力电池数字孪生基础",
      "section_path": "定义",
      "page_number": null,
      "supported_claim": "数字孪生通过模型和数据描述真实电池，但并非等同。",
      "evidence_text": "动力电池数字孪生通过模型、运行数据和参数更新描述真实电池的状态与行为。"
    },
    {
      "chunk_id": "battery_digital_twin:c1d3645d5748b941",
      "document_id": "battery_digital_twin",
      "title": "动力电池数字孪生基础",
      "section_path": "适用边界",
      "page_number": null,
      "supported_claim": "数字孪生不等同于真实系统本身。",
      "evidence_text": "章节：适用边界\n\n- 数字孪生不等同于真实系统本身。\n- 模型结论必须结合传感数据和适用范围解释。"
    },
    {
      "chunk_id": "battery_digital_twin:be67e92d3c557b8b",
      "document_id": "battery_digital_twin",
      "title": "动力电池数字孪生基础",
      "section_path": "典型现象",
      "page_number": null,
      "supported_claim": "模型输出与真实数据可能存在偏差。",
      "evidence_text": "章节：典型现象\n\n- 模型输出与真实电池数据偏差持续增大。\n- 模型参数无法适应温度、SOC或老化变化。\n- 不同运行阶段的预测精度差异明显。"
    }
  ],
  "confidence": 0.9,
  "sufficient_evidence": true,
  "missing_information": [],
  "needs_human_review": true
}
```

### 检查结果

```json
{
  "document_hit_at_k": {
    "passed": true,
    "expected": [
      "battery_digital_twin"
    ],
    "actual": [
      "battery_digital_twin",
      "battery_digital_twin",
      "battery_digital_twin",
      "battery_digital_twin",
      "battery_digital_twin"
    ]
  },
  "chunk_hit_at_k": {
    "passed": true,
    "expected": [],
    "actual": [
      "battery_digital_twin:e42eb0f2e8e23318",
      "battery_digital_twin:be67e92d3c557b8b",
      "battery_digital_twin:ca6bf87e64d74656",
      "battery_digital_twin:c1d3645d5748b941",
      "battery_digital_twin:f9ca2a52809c6cc5"
    ],
    "applicable": false
  },
  "reciprocal_rank": {
    "passed": true,
    "expected": [
      "battery_digital_twin"
    ],
    "actual": 1.0
  },
  "source_keywords": {
    "passed": false,
    "expected": [
      "处置建议",
      "适用边界"
    ],
    "matched": [
      "适用边界"
    ]
  },
  "retrieval_overall": {
    "passed": false
  },
  "answer_mode": {
    "passed": true,
    "expected": "answer",
    "actual": "answer"
  },
  "sufficient_evidence": {
    "passed": true,
    "expected": true,
    "actual": true
  },
  "question_preserved": {
    "passed": true,
    "expected": "数字孪生的输出能否直接等同于真实电池状态？",
    "actual": "数字孪生的输出能否直接等同于真实电池状态？"
  },
  "citation_count": {
    "passed": true,
    "expected_minimum": 1,
    "actual": 3
  },
  "citation_validity": {
    "passed": true,
    "details": [
      {
        "chunk_id": "battery_digital_twin:e42eb0f2e8e23318",
        "document_id": "battery_digital_twin",
        "valid": true
      },
      {
        "chunk_id": "battery_digital_twin:c1d3645d5748b941",
        "document_id": "battery_digital_twin",
        "valid": true
      },
      {
        "chunk_id": "battery_digital_twin:be67e92d3c557b8b",
        "document_id": "battery_digital_twin",
        "valid": true
      }
    ]
  },
  "answer_concepts": {
    "passed": false,
    "matched": 2,
    "total": 3,
    "details": [
      {
        "alternatives": [
          "不等同于真实系统本身",
          "不能等同于真实电池"
        ],
        "matched": true
      },
      {
        "alternatives": [
          "结合传感数据",
          "适用范围"
        ],
        "matched": true
      },
      {
        "alternatives": [
          "保留边界检查和人工审核",
          "人工审核"
        ],
        "matched": false
      }
    ]
  },
  "forbidden_claims": {
    "passed": true,
    "expected_absent": [],
    "matched": []
  },
  "human_review": {
    "passed": true,
    "applicable": false,
    "expected": null,
    "actual": true
  },
  "answer_overall": {
    "passed": false
  },
  "overall": {
    "passed": false
  }
}
```

### 人工分析

- 错误层级：检索 / 生成 / 引用 / 标注
- 错误类型：
- 可能原因：
- 修复建议：
- 回归状态：待修复

### 自动分类

EVIDENCE_SECTION_MISS, ANSWER_CONCEPT_MISS

## RAG-010

### 用户问题

动力电池热失控风险通常需要关注哪些联合异常信号？

### 检索结果

```json
[
  {
    "chunk_id": "battery_thermal_runaway:3cea8d378dcca6ec",
    "document_id": "battery_thermal_runaway",
    "title": "动力电池热失控风险识别",
    "content": "章节：定义\n\n热失控是电池内部放热反应超过散热能力并导致温度快速、自加速上升的危险状态。",
    "score": 0.319491446018219,
    "rank": 1,
    "source_path": "thermal/battery_thermal_runaway.md",
    "section_path": "定义",
    "page_number": null,
    "subsystem": "thermal",
    "topic": "thermal_runaway",
    "metadata": {
      "document_version": "1.0",
      "source_type": "curated_seed"
    }
  },
  {
    "chunk_id": "battery_thermal_runaway:7d2928ec946122aa",
    "document_id": "battery_thermal_runaway",
    "title": "动力电池热失控风险识别",
    "content": "章节：适用边界\n\n- 单点高温不能自动等同于热失控。\n- 安全动作应服从产品级保护策略和应急规范。",
    "score": 0.28312259912490845,
    "rank": 2,
    "source_path": "thermal/battery_thermal_runaway.md",
    "section_path": "适用边界",
    "page_number": null,
    "subsystem": "thermal",
    "topic": "thermal_runaway",
    "metadata": {
      "source_type": "curated_seed",
      "document_version": "1.0"
    }
  },
  {
    "chunk_id": "battery_thermal_runaway:972e5d4663f1404b",
    "document_id": "battery_thermal_runaway",
    "title": "动力电池热失控风险识别",
    "content": "章节：典型现象\n\n- 单体温度或温升速率明显异常。\n- 局部热点与周围测点温差持续扩大。\n- 温度异常同时伴随电压突变、绝缘异常或气体信号。",
    "score": 0.23763728141784668,
    "rank": 3,
    "source_path": "thermal/battery_thermal_runaway.md",
    "section_path": "典型现象",
    "page_number": null,
    "subsystem": "thermal",
    "topic": "thermal_runaway",
    "metadata": {
      "document_version": "1.0",
      "source_type": "curated_seed"
    }
  },
  {
    "chunk_id": "battery_thermal_runaway:f93ab2525d9f9752",
    "document_id": "battery_thermal_runaway",
    "title": "动力电池热失控风险识别",
    "content": "章节：处置建议\n\n- 出现快速温升或多信号异常时执行安全降级或停止运行。\n- 将高风险对象交由专业安全流程处置。",
    "score": 0.20490944385528564,
    "rank": 4,
    "source_path": "thermal/battery_thermal_runaway.md",
    "section_path": "处置建议",
    "page_number": null,
    "subsystem": "thermal",
    "topic": "thermal_runaway",
    "metadata": {
      "document_version": "1.0",
      "source_type": "curated_seed"
    }
  },
  {
    "chunk_id": "battery_thermal_runaway:495b7d947c05ffd8",
    "document_id": "battery_thermal_runaway",
    "title": "动力电池热失控风险识别",
    "content": "章节：验证步骤\n\n- 检查温度信号连续性和相邻测点一致性。\n- 核对冷却执行状态与实际流量或风量。\n- 联合分析温度、电压、电流和绝缘信号。",
    "score": 0.20107907056808472,
    "rank": 5,
    "source_path": "thermal/battery_thermal_runaway.md",
    "section_path": "验证步骤",
    "page_number": null,
    "subsystem": "thermal",
    "topic": "thermal_runaway",
    "metadata": {
      "source_type": "curated_seed",
      "document_version": "1.0"
    }
  }
]
```

### RAG回答

```json
{
  "question": "动力电池热失控风险通常需要关注哪些联合异常信号？",
  "answer": "根据现有证据，动力电池热失控风险需要关注温度异常（单体温度或温升速率明显异常、局部热点与周围测点温差持续扩大）同时伴随电压突变、绝缘异常或气体信号等联合异常信号。",
  "citations": [
    {
      "chunk_id": "battery_thermal_runaway:972e5d4663f1404b",
      "document_id": "battery_thermal_runaway",
      "title": "动力电池热失控风险识别",
      "section_path": "典型现象",
      "page_number": null,
      "supported_claim": "热失控风险需要关注温度异常伴随电压突变、绝缘异常或气体信号等联合异常信号。",
      "evidence_text": "温度异常同时伴随电压突变、绝缘异常或气体信号。"
    }
  ],
  "confidence": 0.6,
  "sufficient_evidence": false,
  "missing_information": [
    "未提供具体的联合异常信号阈值或组合模式。"
  ],
  "needs_human_review": true
}
```

### 检查结果

```json
{
  "document_hit_at_k": {
    "passed": true,
    "expected": [
      "battery_thermal_runaway"
    ],
    "actual": [
      "battery_thermal_runaway",
      "battery_thermal_runaway",
      "battery_thermal_runaway",
      "battery_thermal_runaway",
      "battery_thermal_runaway"
    ]
  },
  "chunk_hit_at_k": {
    "passed": true,
    "expected": [],
    "actual": [
      "battery_thermal_runaway:3cea8d378dcca6ec",
      "battery_thermal_runaway:7d2928ec946122aa",
      "battery_thermal_runaway:972e5d4663f1404b",
      "battery_thermal_runaway:f93ab2525d9f9752",
      "battery_thermal_runaway:495b7d947c05ffd8"
    ],
    "applicable": false
  },
  "reciprocal_rank": {
    "passed": true,
    "expected": [
      "battery_thermal_runaway"
    ],
    "actual": 1.0
  },
  "source_keywords": {
    "passed": true,
    "expected": [
      "典型现象"
    ],
    "matched": [
      "典型现象"
    ]
  },
  "retrieval_overall": {
    "passed": true
  },
  "answer_mode": {
    "passed": false,
    "expected": "answer",
    "actual": "refuse"
  },
  "sufficient_evidence": {
    "passed": false,
    "expected": true,
    "actual": false
  },
  "question_preserved": {
    "passed": true,
    "expected": "动力电池热失控风险通常需要关注哪些联合异常信号？",
    "actual": "动力电池热失控风险通常需要关注哪些联合异常信号？"
  },
  "citation_count": {
    "passed": true,
    "expected_minimum": 1,
    "actual": 1
  },
  "citation_validity": {
    "passed": true,
    "details": [
      {
        "chunk_id": "battery_thermal_runaway:972e5d4663f1404b",
        "document_id": "battery_thermal_runaway",
        "valid": true
      }
    ]
  },
  "answer_concepts": {
    "passed": true,
    "matched": 3,
    "total": 3,
    "details": [
      {
        "alternatives": [
          "温升速率明显异常",
          "快速温升"
        ],
        "matched": true
      },
      {
        "alternatives": [
          "局部热点与周围测点温差持续扩大",
          "局部温差扩大"
        ],
        "matched": true
      },
      {
        "alternatives": [
          "电压突变、绝缘异常或气体信号",
          "多信号异常"
        ],
        "matched": true
      }
    ]
  },
  "forbidden_claims": {
    "passed": true,
    "expected_absent": [],
    "matched": []
  },
  "human_review": {
    "passed": true,
    "applicable": true,
    "expected": true,
    "actual": true
  },
  "answer_overall": {
    "passed": false
  },
  "overall": {
    "passed": false
  }
}
```

### 人工分析

- 错误层级：检索 / 生成 / 引用 / 标注
- 错误类型：
- 可能原因：
- 修复建议：
- 回归状态：待修复

### 自动分类

WRONG_ANSWER_MODE

## RAG-011

### 用户问题

动力电池达到多少摄氏度时，必须统一判定为热失控？

### 检索结果

```json
[
  {
    "chunk_id": "battery_thermal_runaway:3cea8d378dcca6ec",
    "document_id": "battery_thermal_runaway",
    "title": "动力电池热失控风险识别",
    "content": "章节：定义\n\n热失控是电池内部放热反应超过散热能力并导致温度快速、自加速上升的危险状态。",
    "score": 0.21072840690612793,
    "rank": 1,
    "source_path": "thermal/battery_thermal_runaway.md",
    "section_path": "定义",
    "page_number": null,
    "subsystem": "thermal",
    "topic": "thermal_runaway",
    "metadata": {
      "document_version": "1.0",
      "source_type": "curated_seed"
    }
  },
  {
    "chunk_id": "battery_thermal_runaway:972e5d4663f1404b",
    "document_id": "battery_thermal_runaway",
    "title": "动力电池热失控风险识别",
    "content": "章节：典型现象\n\n- 单体温度或温升速率明显异常。\n- 局部热点与周围测点温差持续扩大。\n- 温度异常同时伴随电压突变、绝缘异常或气体信号。",
    "score": 0.12186527252197266,
    "rank": 2,
    "source_path": "thermal/battery_thermal_runaway.md",
    "section_path": "典型现象",
    "page_number": null,
    "subsystem": "thermal",
    "topic": "thermal_runaway",
    "metadata": {
      "source_type": "curated_seed",
      "document_version": "1.0"
    }
  },
  {
    "chunk_id": "battery_thermal_runaway:7d2928ec946122aa",
    "document_id": "battery_thermal_runaway",
    "title": "动力电池热失控风险识别",
    "content": "章节：适用边界\n\n- 单点高温不能自动等同于热失控。\n- 安全动作应服从产品级保护策略和应急规范。",
    "score": 0.11048686504364014,
    "rank": 3,
    "source_path": "thermal/battery_thermal_runaway.md",
    "section_path": "适用边界",
    "page_number": null,
    "subsystem": "thermal",
    "topic": "thermal_runaway",
    "metadata": {
      "source_type": "curated_seed",
      "document_version": "1.0"
    }
  },
  {
    "chunk_id": "battery_thermal_runaway:b71bacc12d6f67a6",
    "document_id": "battery_thermal_runaway",
    "title": "动力电池热失控风险识别",
    "content": "章节：所需数据\n\n- 多点温度、温升速率和环境温度。\n- 单体电压、电流、SOC及冷却系统状态。\n- 绝缘、烟气或其他可用安全信号。",
    "score": 0.10516691207885742,
    "rank": 4,
    "source_path": "thermal/battery_thermal_runaway.md",
    "section_path": "所需数据",
    "page_number": null,
    "subsystem": "thermal",
    "topic": "thermal_runaway",
    "metadata": {
      "document_version": "1.0",
      "source_type": "curated_seed"
    }
  }
]
```

### RAG回答

```json
{
  "question": "动力电池达到多少摄氏度时，必须统一判定为热失控？",
  "answer": "现有证据未提供统一的热失控判定温度阈值。热失控被定义为电池内部放热反应超过散热能力并导致温度快速、自加速上升的危险状态，其判定需结合温度、温升速率、电压、绝缘、烟气等多维信号综合判断，且单点高温不能自动等同于热失控。",
  "citations": [
    {
      "chunk_id": "battery_thermal_runaway:3cea8d378dcca6ec",
      "document_id": "battery_thermal_runaway",
      "title": "动力电池热失控风险识别",
      "section_path": "定义",
      "page_number": null,
      "supported_claim": "热失控的定义，未提及具体温度阈值",
      "evidence_text": "热失控是电池内部放热反应超过散热能力并导致温度快速、自加速上升的危险状态。"
    },
    {
      "chunk_id": "battery_thermal_runaway:972e5d4663f1404b",
      "document_id": "battery_thermal_runaway",
      "title": "动力电池热失控风险识别",
      "section_path": "典型现象",
      "page_number": null,
      "supported_claim": "热失控的典型现象包括温度异常、温差扩大及伴随信号",
      "evidence_text": "章节：典型现象\n\n- 单体温度或温升速率明显异常。\n- 局部热点与周围测点温差持续扩大。\n- 温度异常同时伴随电压突变、绝缘异常或气体信号。"
    },
    {
      "chunk_id": "battery_thermal_runaway:7d2928ec946122aa",
      "document_id": "battery_thermal_runaway",
      "title": "动力电池热失控风险识别",
      "section_path": "适用边界",
      "page_number": null,
      "supported_claim": "单点高温不能自动等同于热失控，需综合判断",
      "evidence_text": "章节：适用边界\n\n- 单点高温不能自动等同于热失控。\n- 安全动作应服从产品级保护策略和应急规范。"
    }
  ],
  "confidence": 0.3,
  "sufficient_evidence": false,
  "missing_information": [
    "统一的热失控判定温度阈值",
    "产品级保护策略中规定的具体温度限值"
  ],
  "needs_human_review": true
}
```

### 检查结果

```json
{
  "document_hit_at_k": {
    "passed": true,
    "expected": [
      "battery_thermal_runaway"
    ],
    "actual": [
      "battery_thermal_runaway",
      "battery_thermal_runaway",
      "battery_thermal_runaway",
      "battery_thermal_runaway"
    ]
  },
  "chunk_hit_at_k": {
    "passed": true,
    "expected": [],
    "actual": [
      "battery_thermal_runaway:3cea8d378dcca6ec",
      "battery_thermal_runaway:972e5d4663f1404b",
      "battery_thermal_runaway:7d2928ec946122aa",
      "battery_thermal_runaway:b71bacc12d6f67a6"
    ],
    "applicable": false
  },
  "reciprocal_rank": {
    "passed": true,
    "expected": [
      "battery_thermal_runaway"
    ],
    "actual": 1.0
  },
  "source_keywords": {
    "passed": true,
    "expected": [
      "适用边界"
    ],
    "matched": [
      "适用边界"
    ]
  },
  "retrieval_overall": {
    "passed": true
  },
  "answer_mode": {
    "passed": true,
    "expected": "refuse",
    "actual": "refuse"
  },
  "sufficient_evidence": {
    "passed": true,
    "expected": false,
    "actual": false
  },
  "question_preserved": {
    "passed": true,
    "expected": "动力电池达到多少摄氏度时，必须统一判定为热失控？",
    "actual": "动力电池达到多少摄氏度时，必须统一判定为热失控？"
  },
  "citation_count": {
    "passed": true,
    "expected_minimum": 1,
    "actual": 3
  },
  "citation_validity": {
    "passed": true,
    "details": [
      {
        "chunk_id": "battery_thermal_runaway:3cea8d378dcca6ec",
        "document_id": "battery_thermal_runaway",
        "valid": true
      },
      {
        "chunk_id": "battery_thermal_runaway:972e5d4663f1404b",
        "document_id": "battery_thermal_runaway",
        "valid": true
      },
      {
        "chunk_id": "battery_thermal_runaway:7d2928ec946122aa",
        "document_id": "battery_thermal_runaway",
        "valid": true
      }
    ]
  },
  "answer_concepts": {
    "passed": false,
    "matched": 0,
    "total": 2,
    "details": [
      {
        "alternatives": [
          "没有给出固定温度阈值",
          "不能仅依据单点高温"
        ],
        "matched": false
      },
      {
        "alternatives": [
          "服从产品级保护策略",
          "以产品级策略为准"
        ],
        "matched": false
      }
    ]
  },
  "forbidden_claims": {
    "passed": true,
    "expected_absent": [
      "统一阈值为",
      "固定阈值是"
    ],
    "matched": []
  },
  "human_review": {
    "passed": true,
    "applicable": true,
    "expected": true,
    "actual": true
  },
  "answer_overall": {
    "passed": false
  },
  "overall": {
    "passed": false
  }
}
```

### 人工分析

- 错误层级：检索 / 生成 / 引用 / 标注
- 错误类型：
- 可能原因：
- 修复建议：
- 回归状态：待修复

### 自动分类

ANSWER_CONCEPT_MISS

## RAG-012

### 用户问题

充电CAN报文超过多少毫秒必须判定为通信故障？

### 检索结果

```json
[
  {
    "chunk_id": "charging_communication_faults:cc1811a929d847a3",
    "document_id": "charging_communication_faults",
    "title": "充电机与BMS通信异常",
    "content": "章节：适用边界\n\n- 通信中断不一定代表电池本体故障。\n- 协议字段和超时要求应以具体接口定义为准。",
    "score": 0.17863047122955322,
    "rank": 1,
    "source_path": "charging/charging_communication_faults.md",
    "section_path": "适用边界",
    "page_number": null,
    "subsystem": "charging",
    "topic": "charging_communication",
    "metadata": {
      "source_type": "curated_seed",
      "document_version": "1.0"
    }
  },
  {
    "chunk_id": "charging_communication_faults:cd4aed0401b0a782",
    "document_id": "charging_communication_faults",
    "title": "充电机与BMS通信异常",
    "content": "章节：处置建议\n\n- 通信状态不确定时禁止继续高功率充电。\n- 保存完整报文和状态日志用于联合分析。",
    "score": 0.12629073858261108,
    "rank": 2,
    "source_path": "charging/charging_communication_faults.md",
    "section_path": "处置建议",
    "page_number": null,
    "subsystem": "charging",
    "topic": "charging_communication",
    "metadata": {
      "source_type": "curated_seed",
      "document_version": "1.0"
    }
  },
  {
    "chunk_id": "charging_communication_faults:6b86bd2ad14df3bd",
    "document_id": "charging_communication_faults",
    "title": "充电机与BMS通信异常",
    "content": "章节：典型现象\n\n- 充电握手失败或充电流程中断。\n- 请求电压、电流与实际输出长时间不一致。\n- 报文超时、计数器异常或状态机停滞。",
    "score": 0.1047290563583374,
    "rank": 3,
    "source_path": "charging/charging_communication_faults.md",
    "section_path": "典型现象",
    "page_number": null,
    "subsystem": "charging",
    "topic": "charging_communication",
    "metadata": {
      "source_type": "curated_seed",
      "document_version": "1.0"
    }
  },
  {
    "chunk_id": "charging_communication_faults:d9f93c5e30307c54",
    "document_id": "charging_communication_faults",
    "title": "充电机与BMS通信异常",
    "content": "章节：定义\n\n充电通信异常是指BMS与充电设备之间的报文、状态或控制指令不能正常交换。",
    "score": 0.10302084684371948,
    "rank": 4,
    "source_path": "charging/charging_communication_faults.md",
    "section_path": "定义",
    "page_number": null,
    "subsystem": "charging",
    "topic": "charging_communication",
    "metadata": {
      "document_version": "1.0",
      "source_type": "curated_seed"
    }
  }
]
```

### RAG回答

```json
{
  "question": "充电CAN报文超过多少毫秒必须判定为通信故障？",
  "answer": "现有证据未提供充电CAN报文超时的具体毫秒阈值。证据指出“协议字段和超时要求应以具体接口定义为准”，因此判定通信故障的超时时间需依据具体接口协议定义，无法给出统一数值。",
  "citations": [
    {
      "chunk_id": "charging_communication_faults:cc1811a929d847a3",
      "document_id": "charging_communication_faults",
      "title": "充电机与BMS通信异常",
      "section_path": "适用边界",
      "page_number": null,
      "supported_claim": "超时阈值需依据具体接口定义",
      "evidence_text": "协议字段和超时要求应以具体接口定义为准。"
    }
  ],
  "confidence": 0.1,
  "sufficient_evidence": false,
  "missing_information": [
    "充电CAN报文超时判定的具体毫秒阈值",
    "所依据的接口协议或标准"
  ],
  "needs_human_review": false
}
```

### 检查结果

```json
{
  "document_hit_at_k": {
    "passed": true,
    "expected": [
      "charging_communication_faults"
    ],
    "actual": [
      "charging_communication_faults",
      "charging_communication_faults",
      "charging_communication_faults",
      "charging_communication_faults"
    ]
  },
  "chunk_hit_at_k": {
    "passed": true,
    "expected": [],
    "actual": [
      "charging_communication_faults:cc1811a929d847a3",
      "charging_communication_faults:cd4aed0401b0a782",
      "charging_communication_faults:6b86bd2ad14df3bd",
      "charging_communication_faults:d9f93c5e30307c54"
    ],
    "applicable": false
  },
  "reciprocal_rank": {
    "passed": true,
    "expected": [
      "charging_communication_faults"
    ],
    "actual": 1.0
  },
  "source_keywords": {
    "passed": true,
    "expected": [
      "适用边界"
    ],
    "matched": [
      "适用边界"
    ]
  },
  "retrieval_overall": {
    "passed": true
  },
  "answer_mode": {
    "passed": true,
    "expected": "refuse",
    "actual": "refuse"
  },
  "sufficient_evidence": {
    "passed": true,
    "expected": false,
    "actual": false
  },
  "question_preserved": {
    "passed": true,
    "expected": "充电CAN报文超过多少毫秒必须判定为通信故障？",
    "actual": "充电CAN报文超过多少毫秒必须判定为通信故障？"
  },
  "citation_count": {
    "passed": true,
    "expected_minimum": 1,
    "actual": 1
  },
  "citation_validity": {
    "passed": true,
    "details": [
      {
        "chunk_id": "charging_communication_faults:cc1811a929d847a3",
        "document_id": "charging_communication_faults",
        "valid": true
      }
    ]
  },
  "answer_concepts": {
    "passed": false,
    "matched": 1,
    "total": 2,
    "details": [
      {
        "alternatives": [
          "以具体接口定义为准",
          "协议字段和超时要求"
        ],
        "matched": true
      },
      {
        "alternatives": [
          "知识库没有给出具体毫秒阈值",
          "没有固定超时阈值"
        ],
        "matched": false
      }
    ]
  },
  "forbidden_claims": {
    "passed": true,
    "expected_absent": [
      "统一超时阈值为",
      "固定为500毫秒"
    ],
    "matched": []
  },
  "human_review": {
    "passed": true,
    "applicable": false,
    "expected": null,
    "actual": false
  },
  "answer_overall": {
    "passed": false
  },
  "overall": {
    "passed": false
  }
}
```

### 人工分析

- 错误层级：检索 / 生成 / 引用 / 标注
- 错误类型：
- 可能原因：
- 修复建议：
- 回归状态：待修复

### 自动分类

ANSWER_CONCEPT_MISS

## RAG-013

### 用户问题

内短路等效电阻5.1kΩ是不是所有动力电池统一标准？

### 检索结果

```json
[
  {
    "chunk_id": "battery_internal_short_circuit:7b5282965bfa7526",
    "document_id": "battery_internal_short_circuit",
    "title": "锂离子电池内短路候选诊断",
    "content": "章节：定义\n\n内短路是电池内部正负极之间形成非预期导电通路的故障形式，其早期特征可能较弱，通常需要多源数据联合判断。",
    "score": 0.1622023582458496,
    "rank": 1,
    "source_path": "battery/battery_internal_short_circuit.md",
    "section_path": "定义",
    "page_number": null,
    "subsystem": "battery",
    "topic": "internal_short_circuit",
    "metadata": {
      "document_version": "1.0",
      "source_type": "curated_seed"
    }
  },
  {
    "chunk_id": "battery_internal_short_circuit:297da311e42bf058",
    "document_id": "battery_internal_short_circuit",
    "title": "锂离子电池内短路候选诊断",
    "content": "章节：典型现象\n\n- 静置阶段自放电速度异常增大。\n- 无明显外部负载时局部温度或温升异常。\n- 单体电压、温度和一致性指标出现持续性偏离。",
    "score": 0.15910452604293823,
    "rank": 2,
    "source_path": "battery/battery_internal_short_circuit.md",
    "section_path": "典型现象",
    "page_number": null,
    "subsystem": "battery",
    "topic": "internal_short_circuit",
    "metadata": {
      "document_version": "1.0",
      "source_type": "curated_seed"
    }
  },
  {
    "chunk_id": "battery_internal_short_circuit:d98a238b060b1fc1",
    "document_id": "battery_internal_short_circuit",
    "title": "锂离子电池内短路候选诊断",
    "content": "章节：所需数据\n\n- 长时间静置电压、自放电速率和环境温度。\n- 单体温度、绝缘状态和历史工况。\n- 外部连接、采样回路和传感器检查结果。",
    "score": 0.15104085206985474,
    "rank": 3,
    "source_path": "battery/battery_internal_short_circuit.md",
    "section_path": "所需数据",
    "page_number": null,
    "subsystem": "battery",
    "topic": "internal_short_circuit",
    "metadata": {
      "document_version": "1.0",
      "source_type": "curated_seed"
    }
  },
  {
    "chunk_id": "battery_internal_short_circuit:e6d76ca14bff3a96",
    "document_id": "battery_internal_short_circuit",
    "title": "锂离子电池内短路候选诊断",
    "content": "章节：处置建议\n\n- 对持续异常单体进行隔离和进一步安全检查。\n- 避免仅依据单一阈值直接确认内短路。",
    "score": 0.10031116008758545,
    "rank": 4,
    "source_path": "battery/battery_internal_short_circuit.md",
    "section_path": "处置建议",
    "page_number": null,
    "subsystem": "battery",
    "topic": "internal_short_circuit",
    "metadata": {
      "source_type": "curated_seed",
      "document_version": "1.0"
    }
  }
]
```

### RAG回答

```json
{
  "question": "内短路等效电阻5.1kΩ是不是所有动力电池统一标准？",
  "answer": "现有证据未提及内短路等效电阻5.1kΩ，也未说明该值是否为所有动力电池的统一标准。证据仅描述了内短路的定义、典型现象、所需数据和处置建议，未涉及具体电阻阈值。",
  "citations": [
    {
      "chunk_id": "battery_internal_short_circuit:7b5282965bfa7526",
      "document_id": "battery_internal_short_circuit",
      "title": "锂离子电池内短路候选诊断",
      "section_path": "定义",
      "page_number": null,
      "supported_claim": "证据未提供内短路等效电阻的具体数值或标准。",
      "evidence_text": "内短路是电池内部正负极之间形成非预期导电通路的故障形式，其早期特征可能较弱，通常需要多源数据联合判断。"
    },
    {
      "chunk_id": "battery_internal_short_circuit:e6d76ca14bff3a96",
      "document_id": "battery_internal_short_circuit",
      "title": "锂离子电池内短路候选诊断",
      "section_path": "处置建议",
      "page_number": null,
      "supported_claim": "证据强调不应仅依据单一阈值确认内短路。",
      "evidence_text": "避免仅依据单一阈值直接确认内短路。"
    }
  ],
  "confidence": 0.0,
  "sufficient_evidence": false,
  "missing_information": [
    "内短路等效电阻5.1kΩ的来源或标准",
    "动力电池内短路电阻的统一阈值或标准"
  ],
  "needs_human_review": true
}
```

### 检查结果

```json
{
  "document_hit_at_k": {
    "passed": true,
    "expected": [
      "battery_internal_short_circuit"
    ],
    "actual": [
      "battery_internal_short_circuit",
      "battery_internal_short_circuit",
      "battery_internal_short_circuit",
      "battery_internal_short_circuit"
    ]
  },
  "chunk_hit_at_k": {
    "passed": true,
    "expected": [],
    "actual": [
      "battery_internal_short_circuit:7b5282965bfa7526",
      "battery_internal_short_circuit:297da311e42bf058",
      "battery_internal_short_circuit:d98a238b060b1fc1",
      "battery_internal_short_circuit:e6d76ca14bff3a96"
    ],
    "applicable": false
  },
  "reciprocal_rank": {
    "passed": true,
    "expected": [
      "battery_internal_short_circuit"
    ],
    "actual": 1.0
  },
  "source_keywords": {
    "passed": false,
    "expected": [
      "定义",
      "适用边界"
    ],
    "matched": [
      "定义"
    ]
  },
  "retrieval_overall": {
    "passed": false
  },
  "answer_mode": {
    "passed": true,
    "expected": "refuse",
    "actual": "refuse"
  },
  "sufficient_evidence": {
    "passed": true,
    "expected": false,
    "actual": false
  },
  "question_preserved": {
    "passed": true,
    "expected": "内短路等效电阻5.1kΩ是不是所有动力电池统一标准？",
    "actual": "内短路等效电阻5.1kΩ是不是所有动力电池统一标准？"
  },
  "citation_count": {
    "passed": true,
    "expected_minimum": 1,
    "actual": 2
  },
  "citation_validity": {
    "passed": true,
    "details": [
      {
        "chunk_id": "battery_internal_short_circuit:7b5282965bfa7526",
        "document_id": "battery_internal_short_circuit",
        "valid": true
      },
      {
        "chunk_id": "battery_internal_short_circuit:e6d76ca14bff3a96",
        "document_id": "battery_internal_short_circuit",
        "valid": true
      }
    ]
  },
  "answer_concepts": {
    "passed": false,
    "matched": 0,
    "total": 2,
    "details": [
      {
        "alternatives": [
          "知识条目没有给出统一等效电阻阈值",
          "没有统一标准"
        ],
        "matched": false
      },
      {
        "alternatives": [
          "需要多源数据联合判断",
          "不能仅依据单一阈值"
        ],
        "matched": false
      }
    ]
  },
  "forbidden_claims": {
    "passed": true,
    "expected_absent": [
      "5.1kΩ是统一标准",
      "统一阈值为5.1kΩ"
    ],
    "matched": []
  },
  "human_review": {
    "passed": true,
    "applicable": true,
    "expected": true,
    "actual": true
  },
  "answer_overall": {
    "passed": false
  },
  "overall": {
    "passed": false
  }
}
```

### 人工分析

- 错误层级：检索 / 生成 / 引用 / 标注
- 错误类型：
- 可能原因：
- 修复建议：
- 回归状态：待修复

### 自动分类

EVIDENCE_SECTION_MISS, ANSWER_CONCEPT_MISS
