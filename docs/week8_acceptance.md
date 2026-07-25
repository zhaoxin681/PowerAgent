### 第八周

第八周主题为：**FastAPI 服务化、可观测性、容器部署与项目交付**。

主要目标：

- 使用 FastAPI 将 PowerAgent 多 Agent 工作流封装为统一 HTTP 服务；
- 建立存活检查、就绪检查、Skill 目录、通用分析、研发分析和知识管理接口；
- 使用 Application Service 和依赖容器隔离 API 层与领域工作流；
- 支持 Markdown、TXT 和文本型 PDF 动态上传、切分、入库、状态查询和删除；
- 建立稳定文档 ID、重复检测、覆盖更新和临时文件清理机制；
- 建立统一 API 成功和错误响应信封；
- 使用 Request ID 追踪 HTTP 请求，使用 Trace ID 追踪 Agent 工作流；
- 建立请求校验、业务异常、RAG 异常、LLM 异常和未知异常的统一映射；
- 使用结构化访问日志记录路径、状态、延迟和错误码，同时保护请求正文和密钥；
- 构建 HTTP API 客户端、离线 Smoke Test 和外部部署 Smoke Test；
- 使用 Dockerfile 和 Docker Compose 完成非 root 容器化部署；
- 使用命名卷持久化 Chroma、日志和 Embedding 缓存；
- 完成 README、架构说明、演示流程、最终验收、简历描述和 Git Tag。


### 第八周

```text
本地配置或Docker运行环境
        ↓
FastAPI create_app 创建应用
        ↓
lifespan 初始化日志和核心服务容器
        ↓
装配 LLMClient、Skill Registry、Chroma、RAG 和工作流
        ↓
健康检查确认应用与依赖就绪
        ↓
客户端发送 HTTP 请求
        ↓
Request Context Middleware 读取或生成 Request ID
        ↓
Pydantic 校验请求模型
        ↓
API Router 选择健康、Skill、知识、通用工作流或研发工作流接口
        ↓
Application Service 将 API 请求转换为领域请求
        ↓
通用 LangGraph 工作流或研发分析工作流执行
        ↓
文档接口执行加载、切分、Embedding、Upsert、状态查询或删除
        ↓
业务结果转换为统一 API 响应
        ↓
Trace ID 写入 Agent 工作流响应和日志
        ↓
异常处理器映射请求、业务、RAG、LLM 和系统异常
        ↓
响应头写入 X-Request-ID
        ↓
访问日志记录 method、path、status、latency、request_id 和 trace_id
        ↓
pytest、MockTransport、TestClient 和 Smoke Test 验证接口闭环
        ↓
Docker Compose 启动非 root API 容器
        ↓
健康检查、端口映射和命名卷验证
        ↓
完成 README、架构、演示、最终验收和简历包装



## 4. 将项目目录更新为

```text
PowerAgent/
├── agent_core/
├── app/
│   ├── __init__.py
│   ├── api.py
│   ├── config.py
│   ├── dependencies.py
│   ├── document_service.py
│   ├── error_handlers.py
│   ├── exceptions.py
│   ├── main.py
│   ├── middleware.py
│   ├── schemas.py
│   └── services.py
├── rag/
├── skills/
├── workflows/
├── report/
├── evaluation/
├── examples/
│   ├── api_client_demo.py
│   └── api_smoke_test.py
├── tests/
│   ├── test_api_client_demo.py
│   └── test_api_smoke.py
├── scripts/
├── docs/
│   ├── architecture.md
│   ├── demo.md
│   ├── final_acceptance.md
│   └── knowledge_base/
├── data/
├── logs/
├── .dockerignore
├── .env
├── .env.example
├── .gitignore
├── Dockerfile
├── docker-compose.yml
├── README.md
└── requirements.txt


### `app/`

存放 PowerAgent FastAPI 服务层、运行配置、依赖装配、知识文档服务、统一异常和可观测性实现。

主要功能：

- 创建 FastAPI 应用和生命周期；
- 加载本地及容器环境变量；
- 装配 LLM、Skill Registry、Chroma、RAG、通用工作流和研发工作流；
- 暴露健康检查、Skill 目录、知识管理和 Agent 分析接口；
- 将 API 请求转换为领域工作流请求；
- 管理知识文档上传、切分、入库、覆盖和删除；
- 生成并透传 Request ID；
- 绑定和返回 Trace ID；
- 处理请求校验、业务、RAG、LLM 和未知异常；
- 输出统一成功和错误响应信封；
- 记录脱敏后的结构化访问日志。

主要文件：

- `config.py`：定义服务、路径、Embedding、上传和工作流配置；
- `dependencies.py`：装配 FastAPI 生命周期内共享服务；
- `services.py`：隔离 API 模型和领域工作流；
- `document_service.py`：管理知识文档入库、更新和删除；
- `exceptions.py`：定义 API 异常层级；
- `error_handlers.py`：将异常转换为统一 HTTP 错误响应；
- `middleware.py`：管理 Request ID、Trace ID 和访问日志；
- `schemas.py`：定义 API 请求、响应和错误模型；
- `api.py`：定义健康、Skill、工作流、研发分析和知识接口；
- `main.py`：创建应用并管理启动与停止生命周期。


### example中添加的功能
- 演示通过统一命令行客户端调用健康、Skill、知识和 Agent 工作流接口；
- 演示 API 4xx、5xx 和结构化业务失败结果；
- 使用外部 HTTP Smoke Test 验证 Uvicorn 或 Docker 部署后的真实服务；
- 验证 Swagger、OpenAPI、知识上传、删除和 Request ID/Trace ID。


### test中添加的功能
- 验证 FastAPI 配置、生命周期和健康检查；
- 验证路由与 Service 层边界；
- 验证知识文档上传、稳定 ID、覆盖和删除；
- 验证 API 统一错误响应；
- 验证 Request ID、Trace ID 和结构化访问日志；
- 使用 MockTransport 验证 API 客户端请求契约；
- 使用离线 Hash Embedding 和临时 Chroma 验证完整 API Smoke 闭环。


### 根目录部署文件

- `Dockerfile`：构建 PowerAgent 非 root API 镜像；
- `docker-compose.yml`：管理 API 服务、端口、环境变量、健康检查和持久化卷；
- `.dockerignore`：排除密钥、虚拟环境、测试缓存、日志和本地数据；
- `.env.example`：提供不包含真实密钥的运行配置模板；
- `README.md`：说明项目背景、架构、启动、API、测试、评测和边界。