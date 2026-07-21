下面内容可直接保存为 `docs/week6_acceptance.md`。其中测试通过数量需要替换为你本地最终运行结果，其他内容已经按照第六周实际设计整理。

# 第六周：研发流程自动化与跨团队协同验收文档

## 1. 本周学习目标

第六周的核心目标是在前五周已完成的 PowerAgent 通用多 Agent 工作流基础上，构建面向动力系统研发问题的自动化分析与跨团队协同能力。

前五周的通用工作流已经能够通过 LangGraph 串联 Issue Parser、Router、Planner、Executor、Decision、Review 和 Report 等节点，并通过统一状态保存执行结果、错误和追踪信息。

本周重点不是重新实现一套 Agent 框架，而是在现有通用工作流之上增加研发业务层，使系统能够围绕一个复杂研发问题完成以下任务：

1. 将用户提出的研发问题转换为标准化研发请求。
2. 调用现有 PowerAgent 工作流获得经过审核的事实和知识证据。
3. 区分已知事实、缺失信息、候选根因和已确认根因。
4. 根据可信上下文生成候选根因及其证据状态。
5. 为候选根因设计可执行的验证实验。
6. 将验证实验映射到具体研发团队。
7. 描述团队之间的输入依赖、交付物和交接条件。
8. 识别研发风险并设置人工复核门槛。
9. 生成可用于研发评审的结构化 Markdown 报告。
10. 通过 Mock 测试和端到端 Demo 验证完整流程。

---

## 2. 本周解决的核心问题

前五周系统已经具备知识检索、数据分析、故障诊断、数字孪生预测、参数寻优和模拟云端策略生成能力，但其输出仍主要面向单次技术分析。

真实动力系统研发问题通常具有以下特点：

* 一个现象可能涉及电池、热管理、充电控制等多个子系统；
* 当前数据通常不足以直接确认根因；
* 需要同时保留支持证据和反向证据；
* 候选根因必须通过实验验证；
* 一个实验可能需要多个团队协作；
* 上游数据、试验资源和审核意见之间存在依赖关系；
* 高风险分析和实验不能直接自动执行；
* 最终交付物不仅是分析结论，还包括实验计划、责任分工和未解决事项。

因此，第六周在通用 PowerAgent 工作流上增加研发业务编排层，形成如下能力闭环：

```text
研发问题输入
    ↓
结构化问题解析
    ↓
研发任务路由
    ↓
证据检索与通用工作流执行
    ↓
Review阶段可信结果
    ↓
研发上下文构建
    ↓
候选根因生成
    ↓
验证实验设计
    ↓
团队分工与协作依赖
    ↓
风险和人工复核
    ↓
研发分析Markdown报告
```

---

## 3. 本周完成内容

### 3.1 建立研发分析数据契约

新增 `workflows/rnd_models.py`，使用 Pydantic 建立研发分析全流程的数据契约。

主要枚举包括：

```text
EvidenceSource
RootCauseStatus
RndPriority
RndAnalysisStatus
TeamName
```

主要数据模型包括：

```text
RndAnalysisRequest
KnownFact
MissingInformation
RootCauseHypothesis
ExperimentCriterion
ValidationExperiment
TeamAssignment
CollaborationDependency
RndRisk
RndGenerationOutput
RndAnalysisContext
RndAnalysisResult
```

这些模型解决了以下问题：

* 事实与假设分离；
* 根因证据状态分级；
* 根因与实验通过稳定 ID 关联；
* 实验与团队任务通过稳定 ID 关联；
* 团队任务之间通过依赖对象关联；
* 高风险实验和高严重度问题强制进入人工复核；
* 缺少关键数据时禁止输出已确认根因；
* LLM 生成结果必须再次经过 Pydantic 全链路校验。

### 3.2 定义根因证据状态

候选根因不再只使用简单的“正确”或“错误”判断，而是按照证据成熟度划分为：

```text
unsupported
    ↓
weak_hypothesis
    ↓
supported_hypothesis
    ↓
confirmed
```

各状态含义如下：

* `unsupported`：当前没有足够证据支持，不得进入正式验证实验。
* `weak_hypothesis`：存在一定可能性，但证据不足。
* `supported_hypothesis`：已有事实或知识证据支持，值得优先验证。
* `confirmed`：已经获得充分且经过验证的事实或实验结果。

自动生成阶段原则上主要输出：

```text
weak_hypothesis
supported_hypothesis
```

只有在已存在经过验证的事实时，才允许输出：

```text
confirmed
```

### 3.3 构建研发分析上下文适配层

新增或扩展：

```text
workflows/rnd_analysis_workflow.py
```

该模块不重新实现 Router、Planner、Executor 或 Review，而是调用现有 `PowerAgentWorkflow`，将通用工作流状态转换为研发分析上下文。

转换关系如下：

```text
PowerAgentState
    ↓
Issue、RAG、Review、错误和执行轨迹提取
    ↓
审核后的发现转换为KnownFact
    ↓
Issue、RAG和Review中的缺失信息合并去重
    ↓
RndAnalysisContext
```

研发适配层保留以下信息：

* `trace_id`
* 原始研发请求
* 标准化 `PowerSystemIssue`
* Tool Calling 结果
* RAG 回答
* Review 结果
* 通用报告结果
* 工作流错误
* 执行轨迹
* 已知事实
* 缺失信息
* 上游是否完成
* 上游是否失败
* 是否需要人工复核

### 3.4 只采用经过 Review 的可信发现

研发上下文不会直接将所有原始 Tool 输出转换为事实，而是优先读取：

```python
review_result.findings
```

这是因为现有 Review Agent 已经完成：

```text
执行状态检查
→ Skill输出模型二次校验
→ 风险等级归一化
→ 发现、证据和建议提取
→ 缺失信息汇总
→ 内容去重
→ 人工复核判断
```

这种设计避免研发层绕过现有审核机制，也避免出现两套事实生成逻辑。

通过 Review 的发现被转换为：

```text
KnownFact
```

但默认仍设置：

```python
is_verified = False
```

因为“经过工作流审核”只代表可以进入研发分析，并不等同于已经通过真实试验确认。

### 3.5 接通研发任务路由

修改：

```text
agent_core/router_agent.py
```

将：

```python
TaskType.RND_ANALYSIS
```

从延后任务调整为当前可执行任务。

研发问题经过 Router 后，应得到：

```text
route = rnd_analysis
status = available
```

Router 仍保持确定性规则，不依赖 LLM。

### 3.6 增加研发分析计划模板

修改：

```text
agent_core/planner_agent.py
```

为 `TaskType.RND_ANALYSIS` 增加底层执行计划。

当前研发分析底层计划为：

```text
步骤0：调用rag_pipeline检索研发问题相关证据
```

Planner 会继续执行既有能力白名单校验，确保计划中的目标确实属于：

* 已注册 Skill；
* 或系统内置的 `rag_pipeline`。

Planner 原有数据模型还会校验执行步骤不能为空、顺序必须连续、步骤 ID 不能重复。

### 3.7 增加研发分析结构化 Prompt

新增：

```text
workflows/rnd_prompts.py
```

Prompt 约束 LLM 只能根据输入中的可信上下文生成：

* 候选根因；
* 验证实验；
* 团队分工；
* 协作依赖；
* 研发风险；
* 未解决事项。

Prompt 中明确规定：

1. `known_facts` 是唯一事实白名单。
2. 根因中的事实 ID 只能引用真实存在的 `fact_id`。
3. 缺失信息不得被描述为已知事实。
4. 没有已验证事实时不得输出 `confirmed`。
5. `supported_hypothesis` 必须引用支持事实。
6. `unsupported` 根因不得关联验证实验。
7. 每个有效根因必须有对应实验。
8. 每个实验必须有步骤、指标、判定标准和交付物。
9. 每个实验必须分配责任团队。
10. 高风险实验必须设置安全要求和人工审批。
11. 不得生成真实车辆控制命令。
12. 不得虚构输入中不存在的测量数据和试验结果。

### 3.8 增加 LLM 中间输出模型

为避免 LLM 修改可信上游字段，新增：

```text
RndGenerationOutput
```

LLM 只负责生成：

```text
summary
hypotheses
experiments
team_assignments
dependencies
risks
overall_risk_level
needs_human_review
unresolved_items
```

以下字段由程序确定，不交给 LLM：

```text
trace_id
issue
known_facts
missing_information
```

最终拼装过程为：

```text
通用工作流可信字段
        +
LLM生成的研发方案字段
        ↓
RndAnalysisResult
        ↓
Pydantic跨对象校验
```

### 3.9 实现根因、实验和团队映射

通过稳定 ID 建立完整追踪关系：

```text
fact_temp_high
    ↓ 支撑
hyp_cooling_limit
    ↓ 验证
exp_cooling_ab
    ↓ 执行
assign_cooling_test
```

同时支持跨团队依赖：

```text
assign_data_prepare
    ↓ 提供对齐日志
assign_cooling_test
```

每个团队任务包含：

* 负责人；
* 协作团队；
* 审核团队；
* 关联实验；
* 输入依赖；
* 具体任务；
* 交付物；
* 完成标准；
* 阻塞项。

### 3.10 增加研发分析报告模板

新增：

```text
report/rnd_report_template.py
```

研发报告模板不调用 LLM，而是将经过校验的 `RndAnalysisResult` 确定性渲染为 Markdown。

现有 `ReportGenerationSkill` 主要生成通用异常分析报告，字段集中在发现、风险、建议、证据和未解决事项。

现有 `ReportAgent` 则负责将 `ReviewResult` 转换为 `FinalWorkflowReport`，并处理报告生成或阻断。

因此研发报告独立负责表达：

* 已知事实；
* 缺失信息；
* 根因状态；
* 验证实验；
* 团队分工；
* 协作依赖；
* 研发风险；
* 人工复核；
* Trace ID。

报告主要章节为：

```text
1. 研发问题概述
2. 已知事实
3. 缺失信息
4. 候选根因及优先级
5. 验证实验计划
6. 团队分工
7. 跨团队依赖
8. 风险与缓解措施
9. 未解决事项
10. 人工复核要求
11. 执行追踪
```

### 3.11 完成第六周 Mock Demo

新增：

```text
examples/rnd_workflow_demo.py
```

Demo 场景为：

```text
部分车辆在快充过程中，
SOC超过80%后充电电流频繁下降，
同时最高温度偏高且单体压差扩大，
但没有明确故障码。
```

Demo 使用：

* 固定研发问题解析器；
* 模拟 RAG 管线；
* 模拟结构化 LLM；
* 真实 Router；
* 真实 Planner；
* 真实 Decision；
* 真实 Review；
* 真实 Report；
* 真实研发上下文适配；
* 真实 Pydantic 数据校验；
* 真实 Markdown 报告模板。

Demo 不访问真实 DeepSeek API，也不访问真实向量数据库，从而保证：

* 可重复运行；
* 不消耗 API 额度；
* 不依赖网络；
* 输出结果稳定；
* 便于演示和测试。

---

## 4. 第六周整体工作流程

### 4.1 底层通用工作流

```text
用户输入
    ↓
Issue Parser
    ↓
PowerSystemIssue
    ↓
Router Agent
    ↓
TaskType.RND_ANALYSIS
    ↓
Planner Agent
    ↓
RAG执行计划
    ↓
Executor
    ↓
Decision Agent
    ↓
Review Agent
    ↓
通用结构化报告
```

### 4.2 研发分析业务层

```text
RndAnalysisRequest
    ↓
RndAnalysisWorkflow.build_context()
    ↓
PowerAgentWorkflow.invoke()
    ↓
审核后的事实与缺失信息
    ↓
RndAnalysisContext
    ↓
结构化LLM生成
    ↓
RndGenerationOutput
    ↓
程序拼装可信字段
    ↓
RndAnalysisResult
    ↓
跨对象ID校验
    ↓
RndReportTemplate
    ↓
研发分析Markdown报告
```

### 4.3 失败处理流程

```text
上游工作流异常
    ↓
构造受限RndAnalysisContext
    ↓
upstream_failed = True
    ↓
needs_human_review = True
    ↓
返回execution_failed结果
```

LLM 生成或校验失败时：

```text
LLM调用失败
或
JSON未通过Pydantic校验
或
跨对象ID引用非法
    ↓
RndAnalysisResult.status = execution_failed
    ↓
保留failure_reason
    ↓
强制人工复核
```

---

## 5. 新增和修改文件

### 5.1 新增目录结构

```text
PowerAgent/
├── workflows/
│   ├── __init__.py
│   ├── rnd_models.py
│   ├── rnd_prompts.py
│   └── rnd_analysis_workflow.py
│
├── report/
│   ├── __init__.py
│   └── rnd_report_template.py
│
├── examples/
│   └── rnd_workflow_demo.py
│
├── tests/
│   ├── rnd_test_helpers.py
│   ├── test_rnd_models.py
│   ├── test_rnd_planning.py
│   ├── test_rnd_analysis_workflow.py
│   └── test_rnd_report_template.py
│
└── docs/
    └── week6_acceptance.md
```

如果没有单独创建 `tests/rnd_test_helpers.py`，则将该项从目录中删除。

### 5.2 修改的已有文件

```text
agent_core/router_agent.py
agent_core/planner_agent.py
tests/test_workflow.py
```

各文件职责如下。

#### `agent_core/router_agent.py`

* 将 `TaskType.RND_ANALYSIS` 调整为已上线能力；
* 研发分析任务返回 `RouteStatus.AVAILABLE`；
* 保持未知系统、未知任务和信息不足的防御性路由。

#### `agent_core/planner_agent.py`

* 增加研发分析任务分支；
* 为研发分析构建 RAG 证据计划；
* 继续使用现有步骤顺序校验和能力白名单校验。

#### `workflows/rnd_models.py`

* 定义研发分析全部数据契约；
* 校验事实、根因、实验、团队和依赖之间的关系；
* 限制根因证据状态；
* 执行高风险人工复核规则。

#### `workflows/rnd_prompts.py`

* 定义研发方案生成边界；
* 禁止模型伪造事实、测量数据和实验结果；
* 约束根因、实验和团队之间的映射关系。

#### `workflows/rnd_analysis_workflow.py`

* 调用通用 PowerAgent 工作流；
* 构建研发分析上下文；
* 合并缺失信息；
* 调用结构化 LLM；
* 生成最终 `RndAnalysisResult`；
* 在失败情况下返回受限结果。

#### `report/rnd_report_template.py`

* 将 `RndAnalysisResult` 确定性渲染为 Markdown；
* 保留所有稳定 ID；
* 输出根因、实验、团队、依赖、风险和人工复核状态；
* 不额外执行推理。

#### `examples/rnd_workflow_demo.py`

* 演示完整研发分析闭环；
* 使用 Mock 避免调用真实 API；
* 打印结构化结果和 Markdown 报告。

#### `tests/test_rnd_models.py`

* 验证研发分析数据契约；
* 检查证据不足、高风险和非法引用等情况。

#### `tests/test_rnd_planning.py`

* 验证研发任务路由已经上线；
* 验证 Planner 能生成合法 RAG 计划。

#### `tests/test_rnd_analysis_workflow.py`

* 验证通用工作流状态向研发上下文转换；
* 验证缺失信息合并；
* 验证上游异常受限处理；
* 验证根因、实验和团队方案生成。

#### `tests/test_rnd_report_template.py`

* 验证报告核心章节；
* 验证对象 ID 得到保留；
* 验证相同输入产生稳定输出。

#### `tests/test_workflow.py`

* 增加真实 LangGraph 研发分析底层流程测试；
* 验证 Router、Planner、RAG、Decision、Review 和 Report 可以完整运行。

---

## 6. 数据契约与可靠性机制

### 6.1 严格字段校验

全部研发业务模型继承项目已有的严格基础模型，确保：

* 禁止额外字段；
* 自动去除字符串首尾空格；
* 字段赋值后重新校验；
* 枚举值只能从合法集合中选择；
* 置信度限制在 0 到 1；
* ID 必须符合指定前缀规则。

### 6.2 事实白名单

LLM 只能引用输入中的：

```text
known_facts
```

不能引用不存在的事实 ID。

根因中的：

```text
supporting_fact_ids
contradicting_fact_ids
```

必须属于真实 `fact_id` 集合。

### 6.3 根因确认门槛

以下条件之一不满足时，不能输出 `confirmed`：

* 根因没有支持事实；
* 支持事实未经过验证；
* 根因置信度低于设定门槛；
* 仍存在影响该根因确认的必要缺失信息；
* 整体状态为 `insufficient_evidence`。

### 6.4 实验映射约束

每个验证实验必须：

* 至少关联一个合法候选根因；
* 不得关联 `unsupported` 根因；
* 包含实验目标；
* 包含步骤；
* 包含观察指标；
* 包含通过和失败标准；
* 包含交付物；
* 被至少一个团队任务接收。

### 6.5 团队角色冲突校验

同一团队不能同时承担：

```text
负责人和协作方
负责人和审核方
协作方和审核方
```

协作团队和审核团队内部也不能出现重复项。

### 6.6 协作依赖校验

每条依赖必须引用真实存在的：

```text
upstream_assignment_id
downstream_assignment_id
```

上游任务和下游任务不能相同。

每条依赖必须说明：

* 上游提供什么交付物；
* 达到什么条件后可以交接；
* 下游任务依赖什么输入。

### 6.7 高风险人工复核

以下任一情况出现时，最终结果必须：

```python
needs_human_review = True
```

触发条件包括：

* 整体风险等级为 `high`；
* 问题严重程度为 `high` 或 `critical`；
* 某个根因要求人工复核；
* 某个实验要求人工审批；
* 某项研发风险要求人工复核；
* 上游工作流执行失败；
* 最终状态为 `human_review_required`。

### 6.8 失败状态一致性

当状态为：

```text
execution_failed
```

必须包含：

```text
failure_reason
```

其他状态不能携带失败原因。

### 6.9 可追踪性

统一使用 `trace_id` 贯穿：

```text
研发请求
→ 通用工作流
→ RAG与Review
→ 研发分析结果
→ Markdown报告
```

根因、实验、团队任务和依赖使用稳定 ID，确保报告中的结论可以追溯到原始对象。

---

## 7. 测试与验收

### 7.1 语法检查

```bash
python -m py_compile agent_core/router_agent.py
python -m py_compile agent_core/planner_agent.py
python -m py_compile workflows/rnd_models.py
python -m py_compile workflows/rnd_prompts.py
python -m py_compile workflows/rnd_analysis_workflow.py
python -m py_compile report/rnd_report_template.py
python -m py_compile examples/rnd_workflow_demo.py
```

验收标准：

```text
所有文件均无SyntaxError。
```

### 7.2 研发模型测试

```bash
python -m pytest tests/test_rnd_models.py -q
```

核心验收项：

* 合法研发结果通过校验；
* 有证据状态的根因必须引用事实；
* 高风险实验必须人工审批；
* 实验不能引用不存在的根因；
* 已确认根因必须由已验证事实支撑；
* 高严重度问题必须人工复核。

本地结果：

```text
通过数量：<填写实际数量>
失败数量：0
```

### 7.3 路由和计划测试

```bash
python -m pytest tests/test_rnd_planning.py -q
```

核心验收项：

* `RND_ANALYSIS` 路由状态为 `available`；
* Planner 状态为 `ready`；
* 研发计划包含 RAG 步骤；
* RAG 属于合法内置能力；
* 执行步骤顺序和 ID 合法。

本地结果：

```text
通过数量：<填写实际数量>
失败数量：0
```

### 7.4 研发上下文与生成测试

```bash
python -m pytest tests/test_rnd_analysis_workflow.py -q
```

核心验收项：

* Review 发现转换为研发事实；
* `trace_id` 正确传递；
* Issue、RAG 和 Review 缺失信息合并去重；
* 上游异常不会直接导致程序崩溃；
* LLM 只能生成规定的研发方案字段；
* 根因引用真实事实 ID；
* 实验与根因正确关联；
* 团队任务与实验正确关联；
* 最终结果通过跨对象校验。

本地结果：

```text
通过数量：<填写实际数量>
失败数量：0
```

### 7.5 报告模板测试

```bash
python -m pytest tests/test_rnd_report_template.py -q
```

核心验收项：

* 报告包含全部核心章节；
* 报告保留根因 ID；
* 报告保留实验 ID；
* 报告保留团队任务 ID；
* 相同输入生成完全一致的 Markdown；
* 空列表能够正确显示为“无”或对应提示。

本地结果：

```text
通过数量：<填写实际数量>
失败数量：0
```

### 7.6 LangGraph 端到端测试

```bash
python -m pytest tests/test_workflow.py -q
```

研发分析新增测试应确认：

```text
is_finished = True
errors = []
route = rnd_analysis
planner_status = ready
rag_call_count = 1
plan[0].target = rag_pipeline
plan[0].status = success
review_result不为空
final_report.status = generated
```

本地结果：

```text
通过数量：<填写实际数量>
失败数量：0
```

### 7.7 第六周联合测试

```bash
python -m pytest tests/test_rnd_models.py tests/test_rnd_planning.py tests/test_rnd_analysis_workflow.py tests/test_rnd_report_template.py tests/test_workflow.py -q
```

本地结果：

```text
通过数量：<填写实际数量>
失败数量：0
警告数量：<填写实际数量>
```

ChromaDB 产生的 `DeprecationWarning` 属于第三方依赖兼容性提示，不影响当前功能测试结果。

### 7.8 完整回归测试

```bash
python -m pytest -q
```

本地结果：

```text
通过数量：<填写实际数量>
失败数量：0
跳过数量：<填写实际数量>
警告数量：<填写实际数量>
```

完整回归通过后，说明第六周新增能力没有破坏前五周已有功能。

### 7.9 Demo 验收

运行：

```bash
python -m examples.rnd_workflow_demo
```

预期关键输出：

```text
status: completed
risk_level: medium
needs_human_review: False
hypothesis_count: 2
experiment_count: 2
assignment_count: 3
rag_call_count: 1
rnd_llm_call_count: 1
```

同时应打印：

* 完整 `RndAnalysisResult` JSON；
* 根因及其证据状态；
* 两个验证实验；
* 三个团队任务；
* 两条协作依赖；
* 研发风险；
* Markdown 研发分析报告。

实际 Demo 结果：

```text
状态：<填写实际状态>
根因数量：<填写实际数量>
实验数量：<填写实际数量>
团队任务数量：<填写实际数量>
RAG调用次数：<填写实际数量>
LLM调用次数：<填写实际数量>
```

---

## 8. 第六周验收标准

以下项目全部满足后，第六周任务视为完成。

```text
[ ] RND_ANALYSIS已经从延后能力调整为可执行能力
[ ] Planner能够为研发分析生成合法RAG计划
[ ] 已建立研发请求、事实、缺失信息和根因模型
[ ] 已建立验证实验和实验判定标准模型
[ ] 已建立团队任务和跨团队依赖模型
[ ] 已建立研发风险和人工审核模型
[ ] 已建立通用工作流到研发上下文的适配层
[ ] 研发上下文只采用Review后的可信发现
[ ] LLM只能生成受限的研发方案字段
[ ] 最终结果执行跨对象ID白名单校验
[ ] 缺失关键信息时不会生成confirmed根因
[ ] 高风险实验能够触发人工审批
[ ] 每个实验都有责任团队
[ ] 报告保留根因、实验和团队任务ID
[ ] Mock Demo能够完整运行
[ ] 第六周专项测试全部通过
[ ] 项目完整回归测试全部通过
[ ] Git工作区提交后保持干净
```

---

## 9. 当前限制

### 9.1 尚未接入真实协同平台

当前团队分工和依赖以结构化模型表示，尚未真实接入：

* Jira；
* Slack；
* 邮件；
* 企业微信；
* 飞书；
* 项目管理平台。

系统目前负责生成可对接的结构化数据，而不是直接创建真实任务或发送消息。

### 9.2 研发方案仍需专业审核

虽然系统能够生成候选根因和实验计划，但不应将其直接视为最终工程决策。

以下场景必须由专业人员复核：

* 涉及电池安全；
* 涉及快充控制策略；
* 涉及高压系统；
* 涉及功能安全；
* 涉及真实车辆试验；
* 需要改变标定参数；
* 存在证据冲突；
* 实验风险较高。

### 9.3 RAG 证据仍受知识库覆盖范围限制

当前根因质量取决于：

* 知识库是否包含相关规范和试验文档；
* Retriever 是否能够召回有效 Chunk；
* 文档是否及时更新；
* 问题描述是否提供足够上下文。

知识库没有证据时，系统应返回证据不足，而不是生成确定结论。

### 9.4 Mock Demo 不代表真实模型性能

Demo 使用固定解析器、模拟 RAG 和模拟结构化 LLM，验证的是系统架构、数据流和校验逻辑。

它不能用于证明：

* DeepSeek 对所有研发问题都能稳定生成正确根因；
* 知识库能够覆盖所有动力系统问题；
* 自动实验设计可以直接代替工程师；
* 输出可以直接用于真实车辆控制。

### 9.5 当前研发计划仍是串行执行

当前工作流主要按顺序执行：

```text
证据获取
→ 上下文构建
→ 方案生成
→ 报告渲染
```

后续可扩展：

* 多团队并行任务；
* 实验完成后的状态回写；
* 根因状态自动升级；
* 协作任务动态重排；
* 多轮研发评审；
* 真实项目管理平台同步。

---

## 10. 本周学习成果

通过第六周任务，完成了从“通用 Agent 工作流”到“研发业务工作流”的关键升级。

具体掌握内容包括：

1. 如何在不破坏通用框架的情况下增加业务适配层。
2. 如何使用 Pydantic 建立跨对象数据契约。
3. 如何区分事实、假设和已确认结论。
4. 如何为 LLM 建立输入和输出白名单。
5. 如何将根因映射到验证实验。
6. 如何将验证实验映射到责任团队。
7. 如何描述跨团队依赖和交接标准。
8. 如何设置高风险人工复核门槛。
9. 如何将结构化结果确定性渲染为报告。
10. 如何使用 Mock 完成可重复的端到端测试。
11. 如何通过 LangGraph 复用已有 Agent 节点。
12. 如何避免将业务逻辑重复写入 Router、Planner、Review 和 Report。

---

## 11. 简历项目描述

面向动力系统研发问题构建多 Agent 自动化分析与跨团队协同工作流，基于 LangGraph 串联任务解析、确定性路由、RAG 证据检索、执行决策、结果审核和报告生成；使用 DeepSeek 结构化输出生成可追踪的候选根因、验证实验、团队职责及协作依赖，通过 Pydantic 建立事实白名单、跨对象 ID 映射、高风险人工复核和失败状态校验机制，并基于 pytest 与 Mock Demo 完成端到端验证。

---

## 12. 第七周衔接基础

第六周完成后，PowerAgent 已具备：

```text
结构化问题理解
Tool Calling与Skills
RAG证据检索
多Agent工作流
数字孪生预测
参数寻优
模拟策略生成
研发根因分析
验证实验设计
跨团队协同
结构化报告生成
```

第七周可以在此基础上进一步开展：

* 工作流评测集构建；
* Agent 输出质量评估；
* 根因和证据一致性指标；
* 实验计划完整性评估；
* LLM 与规则结果对比；
* Prompt 版本管理；
* 自动化回归评测；
* 失败案例分析；
* 系统可观测性与性能统计；
* 面向岗位展示的项目成果整理。

---

## 13. Git 提交记录

建议第六周按照子任务保留以下提交：

```text
feat: add R&D analysis data models
feat: add R&D workflow context adapter
feat: generate R&D hypotheses and validation plans
feat: add R&D analysis report template
feat: add R&D workflow demo and acceptance
```

最终检查：

```bash
git status
git log --oneline -10
```

验收标准：

```text
工作区无未提交修改
第六周相关提交记录完整
所有专项测试和完整回归通过
```
