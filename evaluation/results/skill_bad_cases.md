# Tool Calling Bad Cases

该文件由Skill评测脚本自动生成。

Bad Case数量：1

## charging_003

### 输入

当前充电参数为：包电压385 V，充电电流35 A，SOC 70%，最高温度54℃；允许的最大包电压为400 V，最大充电电流为50 A，最高充电温度为50℃。

### 期望结果

```json
{
  "should_call_tool": true,
  "expected_skill": "charging_analysis",
  "expected_argument_keys": [
    "pack_voltage_v",
    "charging_current_a",
    "soc_pct",
    "maximum_temperature_c",
    "maximum_pack_voltage_v",
    "maximum_charging_current_a",
    "maximum_charging_temperature_c"
  ],
  "expected_status": "success"
}
```

### 实际结果

```json
{
  "status": "success",
  "tool_name": "charging_analysis",
  "arguments": {
    "pack_voltage_v": 385,
    "charging_current_a": 35,
    "soc_pct": 70,
    "maximum_temperature_c": 54,
    "maximum_pack_voltage_v": 400,
    "maximum_charging_current_a": 50
  },
  "error_code": null,
  "error_message": null
}
```

### 检查结果

```json
{
  "status": {
    "passed": true,
    "expected": "success",
    "actual": "success"
  },
  "skill": {
    "passed": true,
    "expected": "charging_analysis",
    "actual": "charging_analysis"
  },
  "required_arguments": {
    "passed": false,
    "expected": [
      "pack_voltage_v",
      "charging_current_a",
      "soc_pct",
      "maximum_temperature_c",
      "maximum_pack_voltage_v",
      "maximum_charging_current_a",
      "maximum_charging_temperature_c"
    ],
    "actual": [
      "charging_current_a",
      "maximum_charging_current_a",
      "maximum_pack_voltage_v",
      "maximum_temperature_c",
      "pack_voltage_v",
      "soc_pct"
    ],
    "missing": [
      "maximum_charging_temperature_c"
    ]
  },
  "execution": {
    "passed": true,
    "expected": "success",
    "actual": "success"
  },
  "overall": {
    "passed": false
  }
}
```

### 人工分析

- 错误类型：
- 可能原因：
- Prompt或代码修改建议：
- 回归状态：待修复
