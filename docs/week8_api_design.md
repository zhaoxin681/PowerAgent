# PowerAgent API 设计

## 1. 文档说明

本文档定义 PowerAgent 第八周 FastAPI 服务化阶段的第一版 API 契约。

PowerAgent 是一个面向动力系统研发与运维场景的多 Agent 工作流平台。系统已经具备动力系统问题结构化解析、任务路由、执行规划、RAG 知识检索、Skills 调用、数字孪生预测、参数寻优、模拟云端策略生成、研发流程分析、结果审核和结构化报告生成能力。

API 层的目标不是重新实现这些业务逻辑，而是将已有能力封装为稳定、安全、可测试的 HTTP 服务。

本文档用于冻结以下内容：

* FastAPI 服务的整体分层；
* 第一版公开接口；
* 请求和响应数据结构；
* 健康检查规则；
* 通用工作流调用规则；
* 研发分析调用规则；
* 文档上传边界；
* HTTP 状态码语义；
* 人工复核和安全边界；
* 当前不支持的能力。

---

## 2. 设计目标

PowerAgent API 应满足以下设计目标。

### 2.1 复用现有核心能力

API 不重新实现 Router Agent、Planner Agent、Decision Agent、Review Agent、Report Agent、RAG Pipeline 或具体动力系统 Skill。

通用业务请求统一调用：

```python
PowerAgentWorkflow.invoke()
```

研发问题分析请求统一调用：

```python
RndAnalysisWorkflow.analyze()
```

### 2.2 保持 API 层轻量

API 层主要负责：

* 接收 HTTP 请求；
* 使用 Pydantic 校验请求；
* 生成或传递 `trace_id`；
* 将请求转换为工作流输入；
* 调用现有服务；
* 将内部结果转换为公开响应；
* 映射业务异常和系统异常；
* 记录请求日志。

API 层不负责：

* 推断动力系统根因；
* 生成执行计划；
* 直接调用具体 Skill；
* 判断证据是否充分；
* 修改数字孪生计算规则；
* 绕过 Review Agent 直接输出报告。

### 2.3 保持公开契约稳定

LangGraph 内部状态可能随着项目迭代发生变化，但公开 API 不应直接依赖完整的 `PowerAgentState`。

API 只返回对调用方有明确业务价值的字段，避免暴露瞬时状态和内部控制信息。

### 2.4 保留可靠性边界

API 必须保留现有系统的以下可靠性机制：

* 证据不足时允许拒答；
* 严重问题保留人工复核标志；
* 报告被阻断时不伪造正常报告；
* 参数寻优无可行解时不生成伪推荐；
* 云端策略只进行模拟下发；
* 研发根因未得到充分证据时不得标记为已确认。

### 2.5 支持本地和容器部署

第一版 API 应同时支持：

* 本地 Uvicorn 启动；
* Docker 镜像运行；
* docker-compose 启动；
* Swagger/OpenAPI 调试；
* pytest 自动化测试；
* 健康检查和容器健康状态判断。

---

## 3. 系统分层

PowerAgent 服务化后采用以下分层结构：

```text
HTTP客户端
    ↓
FastAPI应用层
    ↓
API路由层
    ↓
服务适配层
    ↓
依赖管理层
    ↓
PowerAgent核心工作流
    ↓
Agent / RAG / Skills / Report
```

### 3.1 FastAPI 应用层

推荐文件：

```text
app/main.py
```

主要职责：

* 创建 FastAPI 应用；
* 设置项目名称和版本；
* 注册 API Router；
* 注册异常处理器；
* 注册请求追踪中间件；
* 配置应用生命周期；
* 提供 OpenAPI 和 Swagger 文档。

### 3.2 API 路由层

推荐文件：

```text
app/api.py
```

主要职责：

* 定义 HTTP 路径；
* 接收并校验请求模型；
* 获取服务层依赖；
* 调用服务层方法；
* 返回统一响应模型。

路由层不直接创建 LLM Client、Chroma、Skill Registry 或 LangGraph 工作流。

### 3.3 服务适配层

推荐文件：

```text
app/services.py
```

主要职责：

* 将 API 请求转换为工作流参数；
* 调用 `PowerAgentWorkflow.invoke()`；
* 调用 `RndAnalysisWorkflow.analyze()`；
* 从内部状态提取公开字段；
* 隐藏不应公开的内部状态；
* 生成统一业务响应。

### 3.4 依赖管理层

推荐文件：

```text
app/dependencies.py
```

主要职责：

* 初始化 LLM Client；
* 初始化 Skill Registry；
* 初始化 RAG Pipeline；
* 初始化各 Agent；
* 初始化 `PowerAgentWorkflow`；
* 初始化 `RndAnalysisWorkflow`；
* 复用重量级对象；
* 支持测试时覆盖依赖。

### 3.5 配置层

推荐文件：

```text
app/config.py
```

主要职责：

* 加载服务名称；
* 加载服务版本；
* 加载运行环境；
* 加载 API 前缀；
* 加载日志配置；
* 加载上传文件大小限制；
* 加载 Chroma 路径；
* 加载 DeepSeek 配置；
* 加载默认重试次数。

### 3.6 核心业务层

现有目录：

```text
agent_core/
skills/
rag/
workflows/
report/
```

该层继续负责所有业务推理、知识检索、工具执行、审核和报告生成。

---

## 4. API 基础约定

### 4.1 服务地址

本地默认地址：

```text
http://127.0.0.1:8000
```

### 4.2 API 版本前缀

业务接口统一使用：

```text
/api/v1
```

健康检查不使用版本前缀。

### 4.3 数据格式

除文件上传接口外，请求和响应统一使用：

```text
Content-Type: application/json
```

文档上传接口使用：

```text
Content-Type: multipart/form-data
```

### 4.4 字符编码

所有 JSON、文本和日志统一使用 UTF-8。

### 4.5 追踪标识

系统使用两个追踪字段：

* `request_id`：一次 HTTP 请求的标识；
* `trace_id`：一次完整 PowerAgent 工作流的标识。

`request_id` 由 API 中间件生成。

`trace_id` 可以由调用方传入，也可以由工作流自动生成。

同一个 HTTP 请求通常对应一个 `trace_id`，但二者职责不同：

```text
request_id
用于追踪HTTP请求、访问日志和接口异常

trace_id
用于追踪Issue Parser、Router、Planner、Executor、
Decision、Review、Report等完整工作流
```

---

## 5. 公开接口清单

第一版 API 包含以下接口：

| 方法   | 路径                            | 功能                  |
| ---- | ----------------------------- | ------------------- |
| GET  | `/health/live`                | 服务存活检查              |
| GET  | `/health/ready`               | 服务就绪检查              |
| GET  | `/api/v1/skills`              | 查询已注册 Skill         |
| POST | `/api/v1/workflows/analyze`   | 执行通用 PowerAgent 工作流 |
| POST | `/api/v1/rnd/analyze`         | 执行研发问题分析工作流         |
| POST | `/api/v1/knowledge/documents` | 上传文档并写入知识库          |

第一版不单独提供：

```text
/issues/diagnose
/strategies/optimize
/reports/generate
```

故障诊断、参数寻优和通用报告生成均通过：

```text
POST /api/v1/workflows/analyze
```

进入统一工作流，由 Issue Parser、Router 和 Planner 决定实际执行路径。

---

## 6. 健康检查接口

## 6.1 服务存活检查

### 接口

```http
GET /health/live
```

### 目的

判断 FastAPI 和 Uvicorn 进程是否正在运行，并且能够正常处理 HTTP 请求。

### 检查范围

存活检查只检查：

* FastAPI 应用是否可以响应；
* Uvicorn 进程是否正常；
* 路由是否正确注册。

存活检查不检查：

* DeepSeek API 是否可用；
* Chroma 是否可以检索；
* RAG Pipeline 是否有知识；
* LangGraph 是否能完成完整工作流；
* Skill 是否能够执行；
* 外部网络是否可用。

即使 DeepSeek 暂时不可用，只要 FastAPI 进程可以响应，存活检查仍然应返回成功。

### 成功响应

HTTP 状态码：

```text
200 OK
```

响应示例：

```json
{
  "status": "ok",
  "service": "poweragent",
  "version": "0.1.0"
}
```

### 失败条件

如果无法连接该接口，通常说明：

* Uvicorn 没有启动；
* FastAPI 应用启动失败；
* 容器已经退出；
* 端口没有监听；
* 应用导入失败。

---

## 6.2 服务就绪检查

### 接口

```http
GET /health/ready
```

### 目的

判断服务是否已经完成关键依赖初始化，可以接收真实业务请求。

### 检查范围

就绪检查可以检查：

* 应用配置是否加载成功；
* Skill Registry 是否成功创建；
* 默认 Skill 是否完成注册；
* PowerAgentWorkflow 是否完成初始化；
* RAG Pipeline 是否完成初始化；
* Chroma 数据目录是否可以访问；
* 必要环境变量是否存在。

### 禁止行为

就绪检查不得在每次调用时：

* 向 DeepSeek 发送真实请求；
* 执行完整 LangGraph 工作流；
* 写入生产知识库；
* 执行参数寻优；
* 生成真实研发分析结果。

健康检查可能被 Docker 或部署平台频繁调用，因此必须保持轻量和确定性。

### 成功响应

```json
{
  "status": "ready",
  "service": "poweragent",
  "version": "0.1.0",
  "checks": {
    "configuration": "ok",
    "skill_registry": "ok",
    "workflow": "ok",
    "rag_pipeline": "ok"
  }
}
```

### 未就绪响应

HTTP 状态码：

```text
503 Service Unavailable
```

响应示例：

```json
{
  "status": "not_ready",
  "service": "poweragent",
  "version": "0.1.0",
  "checks": {
    "configuration": "ok",
    "skill_registry": "ok",
    "workflow": "ok",
    "rag_pipeline": "failed"
  }
}
```

### 存活检查与就绪检查区别

```text
/health/live
服务进程是否活着

/health/ready
服务是否具备处理业务请求的条件
```

---

## 7. Skill 目录接口

### 接口

```http
GET /api/v1/skills
```

### 目的

查询当前 Skill Registry 中已经注册的能力。

### 数据来源

接口必须从 `SkillRegistry` 动态读取，不能在 API 文件中维护静态 Skill 名称列表。

当前默认目录包括：

* 知识查询；
* 电池分析；
* 热管理分析；
* 充电分析；
* 数字孪生预测；
* 参数寻优；
* 模拟云端下发；
* 候选诊断；
* 报告生成。

### 成功响应

```json
{
  "request_id": "9c3f47c8a7214f448962a8a5cc7f4a6b",
  "trace_id": null,
  "status": "success",
  "data": {
    "count": 9,
    "skills": [
      {
        "name": "battery_analysis",
        "description": "分析电池组单体电压一致性和越界风险",
        "version": "1.0.0",
        "input_schema": {}
      }
    ]
  },
  "error": null
}
```

### 返回字段

每个 Skill 至少返回：

* `name`；
* `description`；
* `version`；
* `input_schema`。

不得返回：

* Skill Python 对象；
* 内部函数地址；
* 本地文件路径；
* 运行时可变状态；
* API Key；
* Prompt 内容。

---

## 8. 通用工作流接口

## 8.1 接口

```http
POST /api/v1/workflows/analyze
```

## 8.2 支持任务

该接口支持：

* 动力系统知识查询；
* 电池数据分析；
* 热管理数据分析；
* 充电约束分析；
* 故障诊断；
* 数字孪生预测；
* 参数寻优；
* 模拟云端策略生成；
* 通用结构化报告生成。

任务类型由 Issue Parser 根据 `raw_input` 解析，随后由 Router Agent 和 Planner Agent 决定执行路径。

## 8.3 请求模型

推荐模型名称：

```python
WorkflowAnalysisRequest
```

字段定义：

| 字段                             | 类型                | 必填 |     默认值 | 说明              |
| ------------------------------ | ----------------- | -: | ------: | --------------- |
| `raw_input`                    | `str`             |  是 |       无 | 原始动力系统问题        |
| `trace_id`                     | `str \| None`     |  否 |  `None` | 工作流追踪标识         |
| `max_retries`                  | `int`             |  否 |     `2` | 最大自动重试次数        |
| `skill_inputs`                 | `dict[str, dict]` |  否 |    `{}` | 各 Skill 的显式业务输入 |
| `include_trace`                | `bool`            |  否 | `False` | 是否返回执行轨迹        |
| `include_intermediate_results` | `bool`            |  否 | `False` | 是否返回中间结果        |

### 请求示例：知识查询

```json
{
  "raw_input": "动力电池出现单体压差扩大时，常见原因有哪些？",
  "trace_id": null,
  "max_retries": 2,
  "skill_inputs": {},
  "include_trace": false,
  "include_intermediate_results": false
}
```

### 请求示例：电池异常诊断

```json
{
  "raw_input": "充电末期第3号单体电压达到4.25 V，其他单体约4.16 V，请分析风险并生成诊断报告",
  "max_retries": 2,
  "skill_inputs": {
    "battery_analysis": {
      "cell_voltages": [
        4.16,
        4.17,
        4.25,
        4.16
      ]
    }
  },
  "include_trace": true,
  "include_intermediate_results": true
}
```

### 请求示例：参数寻优

```json
{
  "raw_input": "根据当前SOC、电压和温度，对充电电流与冷却功率进行参数寻优，并生成模拟云端下发策略",
  "max_retries": 2,
  "skill_inputs": {
    "digital_twin": {
      "current_soc": 0.62,
      "pack_voltage": 360.0,
      "max_temperature": 36.0,
      "charging_current": 80.0,
      "cooling_power": 1.5
    },
    "parameter_optimization": {
      "current_soc": 0.62,
      "pack_voltage": 360.0,
      "max_temperature": 36.0,
      "candidate_charging_currents": [
        60.0,
        70.0,
        80.0
      ],
      "candidate_cooling_powers": [
        1.0,
        1.5,
        2.0
      ]
    },
    "cloud_dispatch": {
      "target_device": "vehicle_demo_001",
      "allow_dispatch": true,
      "approval_required": true
    }
  },
  "include_trace": true,
  "include_intermediate_results": true
}
```

具体 Skill 输入字段以各 Skill 的实际 Pydantic 输入模型为准。

## 8.4 服务调用流程

```text
WorkflowAnalysisRequest
    ↓
提取raw_input、trace_id、max_retries和skill_inputs
    ↓
PowerAgentWorkflow.invoke()
    ↓
PowerAgentState
    ↓
公开结果转换
    ↓
WorkflowAnalysisResponse
```

调用形式：

```python
state = workflow.invoke(
    request.raw_input,
    trace_id=request.trace_id,
    max_retries=request.max_retries,
    skill_inputs=request.skill_inputs,
)
```

## 8.5 公开响应字段

默认返回：

* `issue`；
* `route`；
* `route_status`；
* `route_reason`；
* `review_result`；
* `final_report`；
* `needs_human_review`；
* `warnings`。

根据请求参数可选返回：

* `execution_trace`；
* `tool_results`；
* `rag_answers`；
* `errors`。

默认不返回：

* `skill_inputs`；
* `retrieved_chunks` 原始全文；
* `latest_tool_result`；
* `latest_rag_answer`；
* `latest_error`；
* `retry_count`；
* `replan_count`；
* 内部对象实例；
* Python 异常堆栈。

## 8.6 成功响应示例

```json
{
  "request_id": "4d847f393ffc4a38ad18d60082da3508",
  "trace_id": "2522dc4010ef46688ef95ba8ad09dd52",
  "status": "success",
  "data": {
    "issue": {
      "raw_text": "充电末期第3号单体电压达到4.25 V，请分析风险",
      "subsystem": "battery",
      "task_type": "fault_diagnosis",
      "symptoms": [
        "第3号单体电压达到4.25 V"
      ],
      "operating_conditions": [],
      "user_hypotheses": [],
      "requested_outputs": [
        "风险分析"
      ],
      "missing_information": [],
      "severity": "high",
      "confidence": 0.92
    },
    "route": "fault_diagnosis",
    "route_status": "available",
    "route_reason": "问题属于可执行的电池故障诊断任务",
    "review_result": {
      "status": "approved_with_warnings",
      "approved_for_report": true,
      "findings": [
        "第3号单体存在过压风险"
      ],
      "recommendations": [
        "检查采样准确性并限制继续充电"
      ],
      "evidence": [
        "第3号单体电压达到4.25 V"
      ],
      "unresolved_items": [
        "缺少连续电压变化数据"
      ],
      "risk_level": "high",
      "issue_severity": "high",
      "review_issues": [],
      "needs_human_review": true
    },
    "final_report": {
      "status": "generated",
      "trace_id": "2522dc4010ef46688ef95ba8ad09dd52",
      "review_status": "approved_with_warnings",
      "issue_severity": "high",
      "needs_human_review": true,
      "report": {},
      "blocked_reason": null
    },
    "needs_human_review": true,
    "warnings": [
      "当前结果需要动力系统专业人员复核"
    ],
    "execution_trace": null,
    "intermediate_results": null
  },
  "error": null
}
```

---

## 9. 研发分析接口

## 9.1 接口

```http
POST /api/v1/rnd/analyze
```

## 9.2 目的

面向跨子系统研发问题，生成：

* 已知事实；
* 缺失信息；
* 候选根因；
* 验证实验；
* 团队任务；
* 协作依赖；
* 研发风险；
* 未解决事项；
* 人工复核要求。

## 9.3 请求模型

请求主体复用 `RndAnalysisRequest` 的业务字段。

字段包括：

| 字段                       | 类型                         | 必填 | 说明         |
| ------------------------ | -------------------------- | -: | ---------- |
| `raw_input`              | `str`                      |  是 | 原始研发问题     |
| `trace_id`               | `str`                      |  否 | 研发流程追踪标识   |
| `affected_scope`         | `list[str]`                |  否 | 车型、批次或工况范围 |
| `available_data`         | `list[str]`                |  否 | 当前可用数据     |
| `operating_conditions`   | `list[OperatingCondition]` |  否 | 异常运行条件     |
| `requested_deliverables` | `list[str]`                |  否 | 需要的交付物     |

请求示例：

```json
{
  "raw_input": "高温快充时部分车辆出现单体压差扩大，请制定研发排查方案",
  "affected_scope": [
    "某车型",
    "环境温度高于40℃",
    "直流快充后半程"
  ],
  "available_data": [
    "单体电压",
    "电池温度",
    "充电电流",
    "SOC"
  ],
  "operating_conditions": [
    {
      "name": "环境温度",
      "value": "40",
      "unit": "℃"
    },
    {
      "name": "SOC",
      "value": "80",
      "unit": "%"
    }
  ],
  "requested_deliverables": [
    "候选根因",
    "验证实验",
    "团队分工",
    "风险说明"
  ]
}
```

## 9.4 调用流程

```text
RndAnalysisRequest
    ↓
RndAnalysisWorkflow.build_context()
    ↓
通用PowerAgent工作流
    ↓
Review审核后的可信上下文
    ↓
结构化LLM生成
    ↓
Pydantic跨对象引用校验
    ↓
RndAnalysisResult
```

服务层调用：

```python
result = rnd_workflow.analyze(request)
```

## 9.5 响应原则

`RndAnalysisResult` 已经包含完整领域数据契约，API 不修改其中的根因、实验、团队任务和风险语义，只在外层增加统一响应信封。

响应示例：

```json
{
  "request_id": "43e9a999db7f41259d1a6433ac3d0058",
  "trace_id": "16bdc8d071f54a1ca2f9f60cd0544f58",
  "status": "success",
  "data": {
    "status": "human_review_required",
    "trace_id": "16bdc8d071f54a1ca2f9f60cd0544f58",
    "issue": {},
    "summary": "初步分析表明问题可能与高温下单体一致性及充电控制边界有关",
    "known_facts": [],
    "missing_information": [],
    "hypotheses": [],
    "experiments": [],
    "team_assignments": [],
    "dependencies": [],
    "risks": [],
    "overall_risk_level": "high",
    "needs_human_review": true,
    "unresolved_items": [],
    "failure_reason": null
  },
  "error": null
}
```

## 9.6 研发业务状态

以下状态均属于有效业务响应：

```text
completed
insufficient_evidence
human_review_required
execution_failed
```

其中：

* `completed`：已生成完整研发方案；
* `insufficient_evidence`：流程正常，但可信事实不足；
* `human_review_required`：已生成方案，但必须人工复核；
* `execution_failed`：研发分析流程未能形成有效方案。

`insufficient_evidence` 和 `human_review_required` 不属于 HTTP 异常。

---

## 10. 文档上传接口

## 10.1 接口

```http
POST /api/v1/knowledge/documents
```

## 10.2 目的

接收动力系统知识文档，完成解析、切分、向量化和 Chroma 入库。

## 10.3 支持格式

第一版仅支持：

* `.md`
* `.txt`
* 文本型 `.pdf`

第一版不支持：

* 图片型 PDF OCR；
* Word；
* Excel；
* PowerPoint；
* ZIP；
* 任意二进制文件；
* 远程 URL 导入；
* 任意服务器路径导入。

## 10.4 请求方式

```text
multipart/form-data
```

字段：

| 字段          | 类型  | 必填 | 说明         |
| ----------- | --- | -: | ---------- |
| `file`      | 文件  |  是 | 待上传文档      |
| `subsystem` | 字符串 |  否 | 文档所属子系统    |
| `topic`     | 字符串 |  否 | 文档主题       |
| `overwrite` | 布尔值 |  否 | 是否允许更新同源文档 |

## 10.5 处理流程

```text
接收上传文件
    ↓
校验文件名和扩展名
    ↓
校验文件大小
    ↓
生成安全临时文件名
    ↓
写入受控临时目录
    ↓
DocumentLoader解析
    ↓
TextSplitter切分
    ↓
EmbeddingProvider生成向量
    ↓
ChromaVectorStore执行Upsert
    ↓
删除临时文件
    ↓
返回入库结果
```

## 10.6 安全要求

必须处理：

* 空文件；
* 文件过大；
* 不支持格式；
* 扩展名伪造；
* 文件名路径穿越；
* PDF 无可提取文本；
* 文档解析失败；
* 向量生成失败；
* Chroma 写入失败；
* 临时文件未清理；
* 重复文档。

不得直接使用客户端文件名作为服务器完整路径。

不得允许客户端指定任意本地保存路径。

## 10.7 成功响应

```json
{
  "request_id": "8cd78008bc8444e2b163fed45d894360",
  "trace_id": null,
  "status": "success",
  "data": {
    "document_id": "doc_battery_overvoltage",
    "filename": "battery_overvoltage.md",
    "format": "markdown",
    "chunk_count": 12,
    "upserted_count": 12,
    "status": "indexed"
  },
  "error": null
}
```

---

## 11. 统一响应结构

所有业务接口使用统一响应信封。

推荐模型：

```python
ApiResponse[T]
```

逻辑结构：

```json
{
  "request_id": "HTTP请求追踪标识",
  "trace_id": "工作流追踪标识或null",
  "status": "success或error",
  "data": {},
  "error": null
}
```

### 11.1 成功响应

```json
{
  "request_id": "request-id",
  "trace_id": "trace-id",
  "status": "success",
  "data": {},
  "error": null
}
```

### 11.2 错误响应

```json
{
  "request_id": "request-id",
  "trace_id": "trace-id或null",
  "status": "error",
  "data": null,
  "error": {
    "code": "stable_error_code",
    "message": "面向调用方的错误说明",
    "retryable": false,
    "details": []
  }
}
```

### 11.3 统一错误模型

推荐字段：

| 字段          | 类型          | 说明         |
| ----------- | ----------- | ---------- |
| `code`      | `str`       | 稳定错误码      |
| `message`   | `str`       | 安全、简洁的错误说明 |
| `retryable` | `bool`      | 是否建议客户端重试  |
| `details`   | `list[str]` | 可选字段级错误信息  |

错误响应不得包含：

* Python Traceback；
* 异常对象字符串；
* API Key；
* 完整 Prompt；
* 模型原始响应；
* 本地绝对路径；
* 数据库内部路径；
* 服务器环境变量。

---

## 12. HTTP 状态语义

## 12.1 HTTP 200

以下情况返回 HTTP 200，因为系统已经正常完成业务判断：

* 工作流成功生成报告；
* 报告被 Review Agent 阻断；
* 证据不足；
* 需要人工复核；
* 参数寻优没有可行候选；
* 云端模拟策略状态为 `blocked`；
* 云端模拟策略状态为 `requires_review`；
* 研发分析状态为 `insufficient_evidence`；
* 研发分析状态为 `human_review_required`；
* RAG 根据证据边界执行拒答。

这些属于业务状态，不属于服务异常。

## 12.2 HTTP 400

适用于：

* 请求格式合法，但业务语义明显不成立；
* Skill 参数组合冲突；
* 请求的操作不允许执行；
* 调用方要求执行明确禁止的真实设备控制。

## 12.3 HTTP 404

适用于：

* 请求的文档不存在；
* 请求的 Skill 不存在；
* 请求的资源标识不存在。

## 12.4 HTTP 409

适用于：

* 文档已经存在且禁止覆盖；
* 资源状态与请求操作冲突；
* 重复提交导致状态冲突。

## 12.5 HTTP 413

适用于：

* 上传文件超过配置的最大文件大小。

## 12.6 HTTP 415

适用于：

* 上传了不支持的文件类型；
* 文件内容与声明格式明显不符。

## 12.7 HTTP 422

适用于：

* Pydantic 请求模型校验失败；
* 缺少必填字段；
* 字段类型错误；
* 数值超出模型允许范围；
* 枚举值非法；
* 请求包含禁止的额外字段。

## 12.8 HTTP 503

适用于：

* DeepSeek 服务不可用；
* 必要配置缺失；
* RAG Pipeline 未初始化；
* Chroma 资源不可访问；
* 关键依赖尚未就绪。

## 12.9 HTTP 500

仅适用于未预期的服务端错误。

返回给客户端的错误信息必须脱敏，详细错误只记录在内部日志中。

---

## 13. 公开结果与内部状态边界

完整 `PowerAgentState` 不直接作为 API 响应。

### 13.1 默认公开

* `trace_id`
* `issue`
* `route`
* `route_status`
* `route_reason`
* `review_result`
* `final_report`
* `needs_human_review`
* 脱敏后的警告信息

### 13.2 按需公开

仅在请求明确要求时返回：

* `execution_trace`
* `tool_results`
* `rag_answers`
* 工作流错误摘要

### 13.3 默认隐藏

* `skill_inputs`
* `retrieved_chunks` 完整正文
* `latest_tool_result`
* `latest_rag_answer`
* `latest_error`
* `retry_count`
* `replan_count`
* 内部对象实例
* LLM Prompt
* API Key
* Chroma 本地路径
* Python 异常堆栈

---

## 14. 人工复核机制

API 必须完整保留核心工作流中的：

```text
needs_human_review
```

以下情况必须保留人工复核标志：

* 问题严重程度为 `high` 或 `critical`；
* Review Agent 要求人工复核；
* 报告状态存在警告；
* RAG 证据不足；
* 数字孪生模型边界未校准；
* 参数寻优结果存在高风险；
* 模拟策略需要审批；
* 研发实验属于高风险；
* 根因置信度不足；
* 通用工作流发生受限失败。

API 不得为了返回“成功”而把人工复核标志重置为 `false`。

---

## 15. 安全边界

### 15.1 云端策略边界

PowerAgent 的 CloudDispatchSkill 只生成模拟策略。

必须保持：

```text
simulation_only = true
```

API 不得提供：

* 真实车辆控制接口；
* 真实 BMS 参数写入；
* 真实充电桩控制；
* 真实冷却系统下发；
* 绕过审批的自动策略执行。

### 15.2 根因判断边界

在缺少充分事实和实验验证时：

* 不得确认根因；
* 不得把假设描述为事实；
* 不得隐藏缺失信息；
* 不得删除 `unresolved_items`；
* 不得绕过人工复核要求。

### 15.3 报告边界

当 `FinalWorkflowReport.status` 为 `blocked` 时：

* API 返回有效业务响应；
* `report` 必须为 `null`；
* 必须返回 `blocked_reason`；
* 不得生成伪报告。

### 15.4 日志安全

日志不得记录：

* DeepSeek API Key；
* `.env` 内容；
* 完整模型 Prompt；
* 上传文件全部正文；
* 用户敏感业务数据；
* Python Traceback 到公开响应。

内部日志可以记录：

* `request_id`；
* `trace_id`；
* 接口路径；
* HTTP 方法；
* 状态码；
* 耗时；
* 稳定错误码；
* 工作流节点；
* 是否要求人工复核。

---

## 16. 配置要求

后续 `app/config.py` 至少管理：

```text
POWERAGENT_SERVICE_NAME
POWERAGENT_SERVICE_VERSION
POWERAGENT_ENV
POWERAGENT_API_PREFIX
POWERAGENT_HOST
POWERAGENT_PORT
POWERAGENT_LOG_LEVEL
POWERAGENT_MAX_UPLOAD_MB
POWERAGENT_CHROMA_PATH
DEEPSEEK_API_KEY
DEEPSEEK_MODEL
```

真实 API Key 只能保存在 `.env` 或部署环境变量中。

`.env.example` 只保留字段名和示例，不保存真实密钥。

---

## 17. FastAPI 运行方式

完成 `app/main.py` 后，在 PowerAgent 项目根目录运行：

```powershell
python -m uvicorn app.main:app --reload
```

假设项目位于：

```text
E:\Poweragent
```

终端应位于：

```powershell
(.venv) PS E:\Poweragent>
```

服务启动后访问：

```text
http://127.0.0.1:8000/docs
```

查看 Swagger 页面。

访问：

```text
http://127.0.0.1:8000/health/live
```

执行存活检查。

PowerShell 请求方式：

```powershell
Invoke-RestMethod -Method Get -Uri "http://127.0.0.1:8000/health/live"
```

或：

```powershell
curl.exe http://127.0.0.1:8000/health/live
```

---

## 18. API 测试要求

API 自动化测试不得默认调用真实 DeepSeek。

测试应通过 FastAPI 依赖覆盖注入：

* Fake PowerAgentWorkflow；
* Fake RndAnalysisWorkflow；
* Fake RAG Pipeline；
* Fake Skill Registry。

核心测试范围：

* 存活检查返回 200；
* 就绪检查成功；
* 就绪检查失败返回 503；
* Skill 列表正常返回；
* 通用工作流请求成功；
* 参数寻优请求成功；
* 研发分析请求成功；
* 证据不足仍返回 HTTP 200；
* 人工复核状态不丢失；
* 报告阻断仍返回 HTTP 200；
* Pydantic 输入非法返回 422；
* 不支持文件返回 415；
* 文件过大返回 413；
* 未预期异常返回脱敏 500；
* 响应中包含 `request_id` 和 `trace_id`；
* 响应中不包含 API Key 和异常堆栈。

---

## 19. 计划新增文件

```text
PowerAgent/
├── app/
│   ├── __init__.py
│   ├── main.py
│   ├── api.py
│   ├── config.py
│   ├── schemas.py
│   ├── dependencies.py
│   ├── services.py
│   ├── document_service.py
│   ├── exceptions.py
│   └── middleware.py
├── tests/
│   ├── test_api_health.py
│   ├── test_api_workflows.py
│   ├── test_document_api.py
│   └── test_api_errors.py
└── docs/
    └── week8_api_design.md
```

实际实现时可以根据代码复杂度合并低价值模块，但必须保持以下职责分离：

* 路由；
* 配置；
* 依赖；
* 服务适配；
* 异常处理；
* 请求追踪。

---

## 20. 当前不支持的能力

第一版 PowerAgent API 明确不支持：

* 真实车辆控制；
* 真实 BMS 参数写入；
* 真实充电策略下发；
* 真实热管理控制；
* 生产环境权限管理；
* 多租户隔离；
* 用户登录与身份认证；
* 图片 OCR；
* Word、Excel、PowerPoint 文档解析；
* ZIP 批量上传；
* 任意服务器本地路径导入；
* 任意远程 URL 文档抓取；
* 流式工作流输出；
* WebSocket；
* 异步后台任务；
* 分布式任务队列；
* 自动确认高风险根因；
* 在证据不足时强制生成结论；
* 对外公开完整 `PowerAgentState`；
* 对外公开 Prompt、API Key 或内部异常堆栈。

---

## 21. 设计验收清单

完成 API 设计后，应检查：

```text
[ ] 通用业务只有一个主要工作流入口
[ ] 研发分析使用独立接口
[ ] 健康检查分为live和ready
[ ] live检查不调用DeepSeek
[ ] ready检查不执行完整工作流
[ ] 最终报告复用现有数据模型
[ ] 研发分析复用RndAnalysisRequest和RndAnalysisResult
[ ] 完整PowerAgentState不直接返回
[ ] blocked状态返回HTTP 200
[ ] insufficient_evidence返回HTTP 200
[ ] human_review_required返回HTTP 200
[ ] API保留needs_human_review
[ ] CloudDispatch保持simulation_only
[ ] API路由不重新实现业务规则
[ ] 文档上传不允许任意路径
[ ] 错误响应不包含异常堆栈
[ ] request_id和trace_id职责清晰
[ ] 接口使用/api/v1版本前缀
[ ] Swagger可以展示公开接口
[ ] pytest默认不访问真实外部服务
```

---

## 22. 后续实现顺序

API 设计冻结后，按以下顺序实现：

```text
任务8.1.2
建立app/schemas.py请求、响应和错误模型

任务8.2
建立FastAPI应用骨架、配置和健康检查

任务8.3
实现通用工作流和研发分析服务层

任务8.4
实现文档上传和知识库更新接口

任务8.5
实现异常处理、请求追踪和结构化日志

任务8.6
建立API自动化测试和演示客户端

任务8.7
完成Docker与docker-compose部署

任务8.8
完成README、架构图、Demo和最终验收
```
