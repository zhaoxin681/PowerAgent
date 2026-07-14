# PowerSystemIssueParser Bad Cases

该文件由评测脚本自动生成。

Bad Case数量：7

## PSI-005

### 输入

请优化电机扭矩控制中的PI参数，目标是在不增加超调的前提下缩短响应时间。

### 未通过项目

required_concepts, overall

### 预测结果

```json
{
  "raw_text": "请优化电机扭矩控制中的PI参数，目标是在不增加超调的前提下缩短响应时间。",
  "subsystem": "electric_drive",
  "task_type": "parameter_optimization",
  "symptoms": [],
  "operating_conditions": [],
  "user_hypotheses": [],
  "requested_outputs": [],
  "missing_information": [
    "当前PI参数值",
    "电机参数（如电感、电阻）",
    "负载条件",
    "响应时间和超调量的当前指标"
  ],
  "severity": "low",
  "confidence": 0.8
}
```

### 检查详情

```json
{
  "subsystem": {
    "passed": true,
    "expected": "electric_drive",
    "actual": "electric_drive"
  },
  "task_type": {
    "passed": true,
    "expected": "parameter_optimization",
    "actual": "parameter_optimization"
  },
  "severity": {
    "passed": true,
    "expected": [
      "low"
    ],
    "actual": "low"
  },
  "raw_text": {
    "passed": true,
    "expected": "请优化电机扭矩控制中的PI参数，目标是在不增加超调的前提下缩短响应时间。",
    "actual": "请优化电机扭矩控制中的PI参数，目标是在不增加超调的前提下缩短响应时间。"
  },
  "required_concepts": {
    "passed": false,
    "matched": 0,
    "total": 3,
    "details": [
      {
        "field": "requested_outputs",
        "alternatives": [
          "优化pi参数",
          "PI参数优化"
        ],
        "actual_text": "",
        "matched": false
      },
      {
        "field": "requested_outputs",
        "alternatives": [
          "缩短响应时间"
        ],
        "actual_text": "",
        "matched": false
      },
      {
        "field": "requested_outputs",
        "alternatives": [
          "不增加超调",
          "控制超调"
        ],
        "actual_text": "",
        "matched": false
      }
    ]
  },
  "must_be_empty": {
    "passed": true,
    "correct": 3,
    "total": 3,
    "details": [
      {
        "field": "symptoms",
        "passed": true,
        "actual": []
      },
      {
        "field": "operating_conditions",
        "passed": true,
        "actual": []
      },
      {
        "field": "user_hypotheses",
        "passed": true,
        "actual": []
      }
    ]
  },
  "overall": {
    "passed": false
  }
}
```

### 人工分析

- 错误类型：
- 可能原因：
- Prompt修改建议：

## PSI-006

### 输入

请根据电池温升、充电功率和冷却回路数据生成一份快充异常分析报告。

### 未通过项目

subsystem, overall

### 预测结果

```json
{
  "raw_text": "请根据电池温升、充电功率和冷却回路数据生成一份快充异常分析报告。",
  "subsystem": "charging",
  "task_type": "report_generation",
  "symptoms": [],
  "operating_conditions": [],
  "user_hypotheses": [],
  "requested_outputs": [
    "快充异常分析报告"
  ],
  "missing_information": [
    "电池温升数据",
    "充电功率数据",
    "冷却回路数据"
  ],
  "severity": "unknown",
  "confidence": 0.8
}
```

### 检查详情

```json
{
  "subsystem": {
    "passed": false,
    "expected": "multi_system",
    "actual": "charging"
  },
  "task_type": {
    "passed": true,
    "expected": "report_generation",
    "actual": "report_generation"
  },
  "severity": {
    "passed": true,
    "expected": [
      "unknown",
      "low",
      "medium"
    ],
    "actual": "unknown"
  },
  "raw_text": {
    "passed": true,
    "expected": "请根据电池温升、充电功率和冷却回路数据生成一份快充异常分析报告。",
    "actual": "请根据电池温升、充电功率和冷却回路数据生成一份快充异常分析报告。"
  },
  "required_concepts": {
    "passed": true,
    "matched": 1,
    "total": 1,
    "details": [
      {
        "field": "requested_outputs",
        "alternatives": [
          "快充异常分析报告",
          "异常分析报告"
        ],
        "actual_text": "快充异常分析报告",
        "matched": true
      }
    ]
  },
  "must_be_empty": {
    "passed": true,
    "correct": 3,
    "total": 3,
    "details": [
      {
        "field": "symptoms",
        "passed": true,
        "actual": []
      },
      {
        "field": "operating_conditions",
        "passed": true,
        "actual": []
      },
      {
        "field": "user_hypotheses",
        "passed": true,
        "actual": []
      }
    ]
  },
  "overall": {
    "passed": false
  }
}
```

### 人工分析

- 错误类型：
- 可能原因：
- Prompt修改建议：

## PSI-008

### 输入

请分析一组电池循环数据，计算容量衰减率、内阻增长率和异常循环点。

### 未通过项目

severity, overall

### 预测结果

```json
{
  "raw_text": "请分析一组电池循环数据，计算容量衰减率、内阻增长率和异常循环点。",
  "subsystem": "battery",
  "task_type": "data_analysis",
  "symptoms": [],
  "operating_conditions": [],
  "user_hypotheses": [],
  "requested_outputs": [
    "容量衰减率",
    "内阻增长率",
    "异常循环点"
  ],
  "missing_information": [
    "电池循环数据的具体数值",
    "循环次数",
    "容量和内阻的测量值"
  ],
  "severity": "unknown",
  "confidence": 0.7
}
```

### 检查详情

```json
{
  "subsystem": {
    "passed": true,
    "expected": "battery",
    "actual": "battery"
  },
  "task_type": {
    "passed": true,
    "expected": "data_analysis",
    "actual": "data_analysis"
  },
  "severity": {
    "passed": false,
    "expected": [
      "low"
    ],
    "actual": "unknown"
  },
  "raw_text": {
    "passed": true,
    "expected": "请分析一组电池循环数据，计算容量衰减率、内阻增长率和异常循环点。",
    "actual": "请分析一组电池循环数据，计算容量衰减率、内阻增长率和异常循环点。"
  },
  "required_concepts": {
    "passed": true,
    "matched": 3,
    "total": 3,
    "details": [
      {
        "field": "requested_outputs",
        "alternatives": [
          "容量衰减率"
        ],
        "actual_text": "容量衰减率 内阻增长率 异常循环点",
        "matched": true
      },
      {
        "field": "requested_outputs",
        "alternatives": [
          "内阻增长率"
        ],
        "actual_text": "容量衰减率 内阻增长率 异常循环点",
        "matched": true
      },
      {
        "field": "requested_outputs",
        "alternatives": [
          "异常循环点"
        ],
        "actual_text": "容量衰减率 内阻增长率 异常循环点",
        "matched": true
      }
    ]
  },
  "must_be_empty": {
    "passed": true,
    "correct": 3,
    "total": 3,
    "details": [
      {
        "field": "symptoms",
        "passed": true,
        "actual": []
      },
      {
        "field": "operating_conditions",
        "passed": true,
        "actual": []
      },
      {
        "field": "user_hypotheses",
        "passed": true,
        "actual": []
      }
    ]
  },
  "overall": {
    "passed": false
  }
}
```

### 人工分析

- 错误类型：
- 可能原因：
- Prompt修改建议：

## PSI-009

### 输入

直流快充进行到SOC 55%时连续三次中断，仪表提示充电通信异常。我怀疑充电桩握手失败，请给出排查方向。

### 未通过项目

required_concepts, overall

### 预测结果

```json
{
  "raw_text": "直流快充进行到SOC 55%时连续三次中断，仪表提示充电通信异常。我怀疑充电桩握手失败，请给出排查方向。",
  "subsystem": "charging",
  "task_type": "fault_diagnosis",
  "symptoms": [
    "充电中断",
    "充电通信异常"
  ],
  "operating_conditions": [
    {
      "name": "SOC",
      "value": "55",
      "unit": "%"
    }
  ],
  "user_hypotheses": [
    "充电桩握手失败"
  ],
  "requested_outputs": [
    "排查方向"
  ],
  "missing_information": [
    "充电桩型号",
    "车辆型号",
    "充电桩与车辆通信协议版本",
    "中断时的故障码",
    "充电桩日志"
  ],
  "severity": "medium",
  "confidence": 0.85
}
```

### 检查详情

```json
{
  "subsystem": {
    "passed": true,
    "expected": "charging",
    "actual": "charging"
  },
  "task_type": {
    "passed": true,
    "expected": "fault_diagnosis",
    "actual": "fault_diagnosis"
  },
  "severity": {
    "passed": true,
    "expected": [
      "medium",
      "high"
    ],
    "actual": "medium"
  },
  "raw_text": {
    "passed": true,
    "expected": "直流快充进行到SOC 55%时连续三次中断，仪表提示充电通信异常。我怀疑充电桩握手失败，请给出排查方向。",
    "actual": "直流快充进行到SOC 55%时连续三次中断，仪表提示充电通信异常。我怀疑充电桩握手失败，请给出排查方向。"
  },
  "required_concepts": {
    "passed": false,
    "matched": 4,
    "total": 5,
    "details": [
      {
        "field": "symptoms",
        "alternatives": [
          "连续三次中断",
          "三次中断"
        ],
        "actual_text": "充电中断 充电通信异常",
        "matched": false
      },
      {
        "field": "symptoms",
        "alternatives": [
          "充电通信异常",
          "通信异常"
        ],
        "actual_text": "充电中断 充电通信异常",
        "matched": true
      },
      {
        "field": "operating_conditions",
        "alternatives": [
          "soc55%",
          "SOC 55%"
        ],
        "actual_text": "SOC 55 %",
        "matched": true
      },
      {
        "field": "user_hypotheses",
        "alternatives": [
          "充电桩握手失败",
          "握手失败"
        ],
        "actual_text": "充电桩握手失败",
        "matched": true
      },
      {
        "field": "requested_outputs",
        "alternatives": [
          "排查方向",
          "排查方案"
        ],
        "actual_text": "排查方向",
        "matched": true
      }
    ]
  },
  "must_be_empty": {
    "passed": true,
    "correct": 0,
    "total": 0,
    "details": []
  },
  "overall": {
    "passed": false
  }
}
```

### 人工分析

- 错误类型：
- 可能原因：
- Prompt修改建议：

## PSI-010

### 输入

环境温度35℃，车辆低速爬坡时冷却液出口温度达到68℃，水泵指令为90%，请分析热管理系统异常原因。

### 未通过项目

severity, required_concepts, overall

### 预测结果

```json
{
  "raw_text": "环境温度35℃，车辆低速爬坡时冷却液出口温度达到68℃，水泵指令为90%，请分析热管理系统异常原因。",
  "subsystem": "thermal",
  "task_type": "fault_diagnosis",
  "symptoms": [
    "冷却液出口温度达到68℃"
  ],
  "operating_conditions": [
    {
      "name": "环境温度",
      "value": "35",
      "unit": "℃"
    },
    {
      "name": "车辆状态",
      "value": "低速爬坡",
      "unit": ""
    },
    {
      "name": "水泵指令",
      "value": "90",
      "unit": "%"
    }
  ],
  "user_hypotheses": [],
  "requested_outputs": [],
  "missing_information": [
    "冷却液出口温度正常范围",
    "水泵实际转速或流量",
    "散热器风扇状态",
    "冷却液液位",
    "节温器状态"
  ],
  "severity": "medium",
  "confidence": 0.8
}
```

### 检查详情

```json
{
  "subsystem": {
    "passed": true,
    "expected": "thermal",
    "actual": "thermal"
  },
  "task_type": {
    "passed": true,
    "expected": "fault_diagnosis",
    "actual": "fault_diagnosis"
  },
  "severity": {
    "passed": false,
    "expected": [
      "high"
    ],
    "actual": "medium"
  },
  "raw_text": {
    "passed": true,
    "expected": "环境温度35℃，车辆低速爬坡时冷却液出口温度达到68℃，水泵指令为90%，请分析热管理系统异常原因。",
    "actual": "环境温度35℃，车辆低速爬坡时冷却液出口温度达到68℃，水泵指令为90%，请分析热管理系统异常原因。"
  },
  "required_concepts": {
    "passed": false,
    "matched": 4,
    "total": 5,
    "details": [
      {
        "field": "symptoms",
        "alternatives": [
          "冷却液出口温度达到68℃",
          "出口温度68℃"
        ],
        "actual_text": "冷却液出口温度达到68℃",
        "matched": true
      },
      {
        "field": "operating_conditions",
        "alternatives": [
          "环境温度35℃",
          "35℃"
        ],
        "actual_text": "环境温度 35 ℃ 车辆状态 低速爬坡  水泵指令 90 %",
        "matched": true
      },
      {
        "field": "operating_conditions",
        "alternatives": [
          "低速爬坡"
        ],
        "actual_text": "环境温度 35 ℃ 车辆状态 低速爬坡  水泵指令 90 %",
        "matched": true
      },
      {
        "field": "operating_conditions",
        "alternatives": [
          "水泵指令90%",
          "水泵90%"
        ],
        "actual_text": "环境温度 35 ℃ 车辆状态 低速爬坡  水泵指令 90 %",
        "matched": true
      },
      {
        "field": "requested_outputs",
        "alternatives": [
          "异常原因",
          "原因分析"
        ],
        "actual_text": "",
        "matched": false
      }
    ]
  },
  "must_be_empty": {
    "passed": true,
    "correct": 1,
    "total": 1,
    "details": [
      {
        "field": "user_hypotheses",
        "passed": true,
        "actual": []
      }
    ]
  },
  "overall": {
    "passed": false
  }
}
```

### 人工分析

- 错误类型：
- 可能原因：
- Prompt修改建议：

## PSI-011

### 输入

永磁同步电机的弱磁控制为什么能够扩展高速运行区间？

### 未通过项目

severity, required_concepts, overall

### 预测结果

```json
{
  "raw_text": "永磁同步电机的弱磁控制为什么能够扩展高速运行区间？",
  "subsystem": "electric_drive",
  "task_type": "knowledge_query",
  "symptoms": [],
  "operating_conditions": [],
  "user_hypotheses": [],
  "requested_outputs": [],
  "missing_information": [],
  "severity": "unknown",
  "confidence": 0.95
}
```

### 检查详情

```json
{
  "subsystem": {
    "passed": true,
    "expected": "electric_drive",
    "actual": "electric_drive"
  },
  "task_type": {
    "passed": true,
    "expected": "knowledge_query",
    "actual": "knowledge_query"
  },
  "severity": {
    "passed": false,
    "expected": [
      "low"
    ],
    "actual": "unknown"
  },
  "raw_text": {
    "passed": true,
    "expected": "永磁同步电机的弱磁控制为什么能够扩展高速运行区间？",
    "actual": "永磁同步电机的弱磁控制为什么能够扩展高速运行区间？"
  },
  "required_concepts": {
    "passed": false,
    "matched": 0,
    "total": 2,
    "details": [
      {
        "field": "requested_outputs",
        "alternatives": [
          "弱磁控制"
        ],
        "actual_text": "",
        "matched": false
      },
      {
        "field": "requested_outputs",
        "alternatives": [
          "扩展高速运行区间",
          "高速运行区间"
        ],
        "actual_text": "",
        "matched": false
      }
    ]
  },
  "must_be_empty": {
    "passed": true,
    "correct": 3,
    "total": 3,
    "details": [
      {
        "field": "symptoms",
        "passed": true,
        "actual": []
      },
      {
        "field": "operating_conditions",
        "passed": true,
        "actual": []
      },
      {
        "field": "user_hypotheses",
        "passed": true,
        "actual": []
      }
    ]
  },
  "overall": {
    "passed": false
  }
}
```

### 人工分析

- 错误类型：
- 可能原因：
- Prompt修改建议：

## PSI-012

### 输入

快充时电池最高温度升高到50℃，充电功率从150 kW降至70 kW，请制定电池、充电和热管理团队联合验证计划。

### 未通过项目

required_concepts, overall

### 预测结果

```json
{
  "raw_text": "快充时电池最高温度升高到50℃，充电功率从150 kW降至70 kW，请制定电池、充电和热管理团队联合验证计划。",
  "subsystem": "multi_system",
  "task_type": "rnd_analysis",
  "symptoms": [
    "电池最高温度升高到50℃",
    "充电功率从150 kW降至70 kW"
  ],
  "operating_conditions": [
    {
      "name": "充电类型",
      "value": "快充",
      "unit": ""
    },
    {
      "name": "电池最高温度",
      "value": "50",
      "unit": "℃"
    },
    {
      "name": "充电功率",
      "value": "150降至70",
      "unit": "kW"
    }
  ],
  "user_hypotheses": [],
  "requested_outputs": [
    "电池、充电和热管理团队联合验证计划"
  ],
  "missing_information": [
    "电池类型和规格",
    "充电桩规格",
    "环境温度",
    "SOC范围",
    "充电时长",
    "冷却系统状态"
  ],
  "severity": "high",
  "confidence": 0.85
}
```

### 检查详情

```json
{
  "subsystem": {
    "passed": true,
    "expected": "multi_system",
    "actual": "multi_system"
  },
  "task_type": {
    "passed": true,
    "expected": "rnd_analysis",
    "actual": "rnd_analysis"
  },
  "severity": {
    "passed": true,
    "expected": [
      "high"
    ],
    "actual": "high"
  },
  "raw_text": {
    "passed": true,
    "expected": "快充时电池最高温度升高到50℃，充电功率从150 kW降至70 kW，请制定电池、充电和热管理团队联合验证计划。",
    "actual": "快充时电池最高温度升高到50℃，充电功率从150 kW降至70 kW，请制定电池、充电和热管理团队联合验证计划。"
  },
  "required_concepts": {
    "passed": false,
    "matched": 5,
    "total": 7,
    "details": [
      {
        "field": "symptoms",
        "alternatives": [
          "最高温度升高到50℃",
          "温度50℃"
        ],
        "actual_text": "电池最高温度升高到50℃ 充电功率从150 kW降至70 kW",
        "matched": true
      },
      {
        "field": "symptoms",
        "alternatives": [
          "150kw降至70kw",
          "充电功率下降"
        ],
        "actual_text": "电池最高温度升高到50℃ 充电功率从150 kW降至70 kW",
        "matched": true
      },
      {
        "field": "operating_conditions",
        "alternatives": [
          "快充"
        ],
        "actual_text": "充电类型 快充  电池最高温度 50 ℃ 充电功率 150降至70 kW",
        "matched": true
      },
      {
        "field": "requested_outputs",
        "alternatives": [
          "联合验证计划",
          "验证计划"
        ],
        "actual_text": "电池、充电和热管理团队联合验证计划",
        "matched": true
      },
      {
        "field": "requested_outputs",
        "alternatives": [
          "电池团队"
        ],
        "actual_text": "电池、充电和热管理团队联合验证计划",
        "matched": false
      },
      {
        "field": "requested_outputs",
        "alternatives": [
          "充电团队"
        ],
        "actual_text": "电池、充电和热管理团队联合验证计划",
        "matched": false
      },
      {
        "field": "requested_outputs",
        "alternatives": [
          "热管理团队"
        ],
        "actual_text": "电池、充电和热管理团队联合验证计划",
        "matched": true
      }
    ]
  },
  "must_be_empty": {
    "passed": true,
    "correct": 1,
    "total": 1,
    "details": [
      {
        "field": "user_hypotheses",
        "passed": true,
        "actual": []
      }
    ]
  },
  "overall": {
    "passed": false
  }
}
```

### 人工分析

- 错误类型：
- 可能原因：
- Prompt修改建议：
