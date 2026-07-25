# PowerAgent 系统架构

## 1. 分层架构

```text
调用层
├── Swagger
├── API Client
└── Smoke Test

服务层
├── FastAPI Router
├── Request Context Middleware
├── Exception Handlers
├── Workflow Service
├── RND Analysis Service
└── Document Ingestion Service

Agent工作流层
├── Issue Parser
├── Router Agent
├── Planner Agent
├── Executor
├── Decision Agent
├── Review Agent
└── Report Agent

能力层
├── Skill Registry
├── Power System Skills
├── RAG Pipeline
└── RND Analysis Workflow

数据与基础设施层
├── DeepSeek API
├── Chroma Vector Store
├── Knowledge Documents
├── Structured Logging
└── Docker Volumes
```

## 2. 请求处理流程

```text
HTTP请求
→ Request ID中间件
→ Pydantic请求校验
→ API路由
→ Application Service
→ Agent工作流或知识服务
→ 结构化业务结果
→ API统一响应信封
→ 响应头写入X-Request-ID
→ 访问日志
```

## 3. Agent工作流

```text
raw_input
→ PowerSystemIssueParser
→ PowerSystemIssue
→ Router Agent
→ Planner Agent
→ RAG或Skill执行
→ Decision Agent
→ Review Agent
→ Report Agent
→ FinalWorkflowReport
```

## 4. RAG链路

```text
文档上传
→ 文件校验
→ 安全临时文件
→ DocumentLoader
→ TextSplitter
→ EmbeddingProvider
→ ChromaVectorStore
→ Retriever
→ RAG Pipeline
→ 引用白名单校验
→ RAGAnswer
```

## 5. Request ID

Request ID 标识一次 HTTP 请求。

主要用途：

- 关联请求和响应；
- 关联访问日志与异常日志；
- 排查 API 调用问题；
- 不跨多个独立 HTTP 请求共享。

来源：

```text
合法X-Request-ID
或
服务端自动生成UUID
```

## 6. Trace ID

Trace ID 标识一次 Agent 工作流执行。

主要用途：

- 关联问题解析、路由、规划和执行；
- 关联 Tool、RAG、Review 和 Report；
- 在业务结果和日志间建立追踪关系；
- 可以由客户端提供，也可以由服务端生成。

非 Agent 接口可以没有 Trace ID。

## 7. 错误边界

### 请求错误

```text
字段缺失
字段类型错误
非法枚举
非法参数范围
```

返回 HTTP 422 或对应的 4xx。

### 业务资源错误

```text
文档不存在
重复文档
文件过大
不支持的文件格式
```

返回 4xx。

### 上游和系统错误

```text
LLM认证失败
LLM限流
连接失败
依赖不可用
未处理异常
```

返回 5xx，并对未知异常脱敏。

### 结构化业务失败

```text
证据不足
需要人工复核
Review未通过
报告被阻断
研发方案生成失败
```

API 调用本身成功时仍返回 HTTP 200，由 `data.status`、`needs_human_review` 和 `failure_reason` 表达业务状态。

## 8. 安全边界

- 不记录请求正文和真实密钥；
- 不在客户端响应中泄露堆栈；
- 不执行真实设备策略下发；
- 高风险结果必须人工审核；
- Docker以非root用户运行；
- `.env`不进入镜像和Git；
- Chroma和日志使用持久化卷；
- 容器仅暴露API端口。