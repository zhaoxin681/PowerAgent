# PowerAgent 第四周：Agent工作流编排

## 1. 本周学习目标

第四周主题为：**基于LangGraph的多Agent工作流编排**。

主要目标：

* 理解LangGraph中的State、Node、Edge、Conditional Edge和Reducer；
* 建立PowerAgent统一工作流状态；
* 构建Router Agent、Planner Agent、Decision Agent、Review Agent和Report Agent；
* 将前三周的问题解析、Skill Registry、动力系统Skills和RAG Pipeline接入统一工作流；
* 支持知识问答、数据分析和故障诊断等任务；
* 对参数寻优和研发分析等后续能力进行安全延后；
* 建立工作流重试、重新规划、人工复核和终止机制；
* 使用Mock组件完成不依赖外部API和向量库的端到端测试；
* 为第五周数字孪生与参数寻优能力接入提供统一执行框架。

---

## 2. 本周整体工作流程

```text
用户输入动力系统问题
        ↓
Issue Parser将自然语言转换为PowerSystemIssue
        ↓
Router Agent读取结构化任务类型
        ↓
判断任务当前可执行、延后、信息不足或不支持
        ↓
Planner Agent读取Skill Registry能力白名单
        ↓
生成顺序明确的结构化执行计划
        ↓
Executor读取当前WorkflowStep
        ↓
调用RAG Pipeline或Skill Registry
        ↓
将执行结果写入统一工作流状态
        ↓
Decision Agent判断继续、完成、重试、重新规划或人工复核
        ↓
存在后续步骤时继续执行
        ↓
计划完成或自动执行停止后进入Review Agent
        ↓
Review Agent二次校验Skill、RAG和候选诊断结果
        ↓
归一化关键发现、风险、建议、证据和未解决事项
        ↓
Report Agent构造ReportGenerationInput
        ↓
调用ReportGenerationSkill生成最终结构化报告
        ↓
保存执行轨迹、审核状态和人工复核标志
        ↓
工作流结束
```

---

## 3. LangGraph状态管理设计

第四周使用TypedDict和Pydantic组合建立统一工作流状态。

### TypedDict职责

TypedDict用于定义LangGraph节点共享的顶层状态，包括：

* 原始用户输入；
* 工作流追踪ID；
* 结构化动力系统问题；
* 路由结果；
* 执行计划；
* 当前步骤索引；
* Skill输入；
* Tool Calling结果；
* RAG回答；
* Decision结果；
* Review结果；
* 最终报告；
* 错误记录；
* 节点执行轨迹；
* 重试和重新规划次数。

### Pydantic职责

Pydantic用于校验工作流中的核心业务对象，包括：

* `PowerSystemIssue`
* `WorkflowStep`
* `WorkflowError`
* `WorkflowTraceEvent`
* `RouterDecision`
* `PlannerResult`
* `DecisionResult`
* `ReviewResult`
* `FinalWorkflowReport`
* `ToolCallingResult`
* `RAGAnswer`

### Reducer字段

以下状态字段使用Reducer追加而不是覆盖：

```text
tool_results
retrieved_chunks
rag_answers
errors
execution_trace
```

以下字段保存当前最新值：

```text
current_node
current_step_index
decision
latest_tool_result
latest_rag_answer
latest_error
review_result
final_report
```

---

## 4. 各Agent主要职责

### Router Agent

Router Agent读取第一周生成的`PowerSystemIssue.task_type`，通过确定性规则选择工作流类型。

支持的路由状态：

```text
available
deferred
needs_information
unsupported
```

当前可执行任务：

```text
knowledge_query
data_analysis
fault_diagnosis
```

后续阶段任务：

```text
parameter_optimization
rnd_analysis
```

Router Agent不重复调用LLM，避免增加调用成本、响应延迟和分类不一致风险。

### Planner Agent

Planner Agent根据Router结果生成结构化执行步骤。

主要能力：

* 从Skill Registry读取真实Skill；
* 使用能力白名单验证执行目标；
* 区分RAG节点和Skill节点；
* 生成连续、唯一的步骤编号；
* 检测未注册能力；
* 阻止后续阶段任务产生虚假计划。

典型故障诊断计划：

```text
battery_analysis
        ↓
rag_pipeline
        ↓
diagnosis
```

Planner Agent只生成计划，不执行具体业务逻辑。

### Decision Agent

Decision Agent根据当前步骤结果控制流程。

支持的决策：

```text
continue
finish
retry
replan
human_review
abort
```

核心规则：

* 步骤成功且存在后续步骤时继续；
* 最后一步成功后进入Review；
* 参数错误进入重新规划；
* 只有明确标记为可恢复的工作流错误才能重试；
* 重试和重新规划均受到次数限制；
* RAG证据不足时停止后续诊断；
* LLM内部重试耗尽后不叠加无限工作流重试。

### Review Agent

Review Agent审核工作流执行结果，而不是重新执行分析。

主要功能：

* 对不同Skill输出进行二次Pydantic校验；
* 提取关键发现、风险、建议和证据；
* 区分规则证据和证据不足说明；
* 保留候选诊断的不确定性边界；
* 防止将相关性或规则触发升级为确定故障结论；
* 识别失败、跳过和未完成步骤；
* 处理RAG证据充分性；
* 保留关键安全问题的人工复核标志。

### Report Agent

Report Agent只处理经过Review Agent审核的结果。

主要流程：

```text
ReviewResult
        ↓
ReportGenerationInput
        ↓
ReportGenerationSkill
        ↓
FinalWorkflowReport
```

没有可靠发现或建议时，Report Agent返回`blocked`状态，不生成虚假报告。

---

## 5. Skill和RAG执行机制

### Skill执行

Planner确定执行目标后，Executor直接调用：

```text
SkillRegistry.invoke()
```

不再重新调用Tool Calling选择工具。

该调用仍然经过BaseSkill统一执行链：

```text
输入校验
    ↓
业务执行
    ↓
输出校验
```

用户显式提供的业务参数保存在：

```text
skill_inputs
```

例如：

```python
{
    "battery_analysis": {
        "cell_voltages_v": [
            3.54,
            3.63,
            3.62
        ],
        "spread_threshold_v": 0.05
    }
}
```

### Diagnosis输入

Diagnosis Skill所需的风险信号由Executor根据前序分析结果自动构造，包括：

```text
battery_risk
thermal_risk
charging_risk
abnormal_cell_numbers
abnormal_sensor_numbers
violated_constraints
```

用户不需要直接提供已经完成分析后才能获得的风险标志。

### RAG执行

知识问答和故障诊断中的知识检索调用RAG Pipeline。

RAG Pipeline负责：

* Retriever检索；
* 无证据拒答；
* 结构化回答；
* 引用白名单；
* 来源重建；
* 证据文本校验；
* 人工复核标记。

RAG执行成功但证据不足时，当前步骤不视为程序故障，但工作流不能继续生成可靠候选诊断。

---

## 6. 当前支持的端到端场景

### 知识问答

```text
Issue Parser
    ↓
Router
    ↓
Planner
    ↓
RAG Pipeline
    ↓
Decision
    ↓
Review
    ↓
Report
```

### 电池数据分析

```text
Issue Parser
    ↓
Router
    ↓
Planner
    ↓
BatteryAnalysisSkill
    ↓
Decision
    ↓
Review
    ↓
Report
```

### 故障诊断

```text
Issue Parser
    ↓
Router
    ↓
Planner
    ↓
Analysis Skill
    ↓
Decision
    ↓
RAG Pipeline
    ↓
Decision
    ↓
Diagnosis Skill
    ↓
Decision
    ↓
Review
    ↓
Report
```

### 参数寻优

```text
Issue Parser
    ↓
Router识别parameter_optimization
    ↓
标记为deferred
    ↓
Planner不生成虚假Optimization步骤
    ↓
Review
    ↓
返回受限报告
```

---

## 7. 错误处理与可靠性机制

第四周建立的主要可靠性机制包括：

* 所有节点共享工作流`trace_id`；
* Planner只引用真实注册能力；
* Skill输入和输出经过Pydantic校验；
* RAG引用经过白名单和来源重建；
* Tool Calling历史结果与当前步骤结果分开保存；
* 节点错误转换为统一`WorkflowError`；
* 可恢复错误采用有限次数重试；
* 参数错误进入重新规划而不是无效重试；
* 重试和重新规划具有次数上限；
* 无证据时停止自动诊断；
* 失败步骤和跳过步骤进入Review；
* 候选诊断不被表述为确认故障；
* 无可靠发现时阻断正常报告；
* 关键安全风险保留人工复核标志；
* 完整节点执行过程写入`execution_trace`。

---

## 8. 第四周新增目录结构

```text
PowerAgent/
├── agent_core/
│   ├── state.py
│   ├── workflow_models.py
│   ├── router_agent.py
│   ├── planner_agent.py
│   ├── decision_agent.py
│   ├── review_agent.py
│   ├── report_agent.py
│   └── workflow.py
├── examples/
│   └── agent_workflow_demo.py
├── tests/
│   ├── test_workflow_state.py
│   ├── test_router_agent.py
│   ├── test_planner_agent.py
│   ├── test_decision_agent.py
│   ├── test_review_agent.py
│   ├── test_report_agent.py
│   └── test_workflow.py
└── docs/
    └── week4_agent_workflow.md
```

---

## 9. 当前系统限制

第四周工作流仍存在以下明确边界：

1. 当前主要支持电池、热管理和充电场景；
2. 电驱分析Skill尚未实现；
3. 多系统数据输入尚未建立统一Schema；
4. Skill业务参数暂时通过`skill_inputs`显式提供；
5. Executor尚未实现自然语言到复杂Skill参数的统一映射；
6. 参数寻优和数字孪生能力将在第五周接入；
7. 研发流程自动化将在第六周接入；
8. 工作流评测数据集和批量指标将在第七周建立；
9. 当前Demo使用Mock Issue Parser和Mock RAG Pipeline；
10. FastAPI和Docker部署将在第八周完成。

---

## 10. 第五周扩展接口

第五周可以在当前框架中新增：

```text
digital_twin
optimization
cloud_dispatch
```

接入步骤：

```text
新增Skill
    ↓
注册到Skill Registry
    ↓
扩展Planner计划模板
    ↓
Executor通过Registry统一调用
    ↓
Decision控制步骤执行
    ↓
Review审核仿真和寻优结果
    ↓
Report生成策略建议报告
```

LangGraph主框架无需重新设计，只需扩展真实能力和计划模板。

---

## 11. 简历项目描述

基于LangGraph构建面向动力系统研发与诊断场景的多Agent工作流平台，设计Router、Planner、Decision、Review和Report等状态节点，集成结构化问题解析、RAG知识检索及可复用Skills，实现知识问答、数据分析、候选故障诊断和结构化报告生成闭环；通过能力白名单、条件路由、证据校验、有限重试、重新规划和人工复核机制，提升Agent系统的可追踪性、可靠性与扩展能力。
