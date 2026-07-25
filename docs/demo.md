# PowerAgent 项目演示

## 1. 演示目标

展示以下完整闭环：

```text
容器启动
→ 健康检查
→ Skill目录
→ 文档上传
→ 知识库状态
→ RAG知识查询
→ Request ID与Trace ID
→ 结构化业务结果
→ 错误响应
→ 日志追踪
→ 文档删除
```

## 2. 启动

```powershell
docker compose up `
  -d `
  --build
```

```powershell
docker compose ps
```

预期：

```text
Up ... (healthy)
```

## 3. 健康检查

```powershell
python -m examples.api_client_demo `
  health

python -m examples.api_client_demo `
  ready
```

说明：

- `live` 表示进程存活；
- `ready` 表示核心依赖初始化完成。

## 4. 查询 Skill

```powershell
python -m examples.api_client_demo `
  skills
```

展示：

- Skill 名称；
- 版本；
- 描述；
- 输入 JSON Schema。

## 5. 上传知识文档

```powershell
@"
高SOC快充阶段发生限流时，
应检查单体电压上限、单体压差、
最高温度和热管理冷却能力。
"@ | Set-Content `
  -Path ".\demo_charging_note.txt" `
  -Encoding utf8
```

```powershell
python -m examples.api_client_demo `
  document-upload `
  --file ".\demo_charging_note.txt" `
  --topic "高SOC快充限流" `
  --subsystem charging
```

展示：

```text
document_id
chunk_count
upserted_count
```

## 6. 查询知识库状态

```powershell
python -m examples.api_client_demo `
  knowledge-status
```

展示上传后 `chunk_count` 增加。

## 7. 执行知识查询

```powershell
python -m examples.api_client_demo `
  --request-id "interview-demo-001" `
  workflow-analyze `
  --input "请基于知识库说明高SOC快充限流需要检查哪些因素" `
  --include-trace `
  --include-intermediate-results
```

重点展示：

```text
route
route_status
rag_answers
citations
review_result
final_report
needs_human_review
Request ID
Trace ID
```

## 8. 说明可观测性

```text
Request ID
→ 定位一次HTTP请求

Trace ID
→ 定位一次完整Agent工作流
```

查看日志：

```powershell
docker compose logs `
  --tail 100 `
  api
```

搜索演示 Request ID：

```powershell
docker compose logs api |
  Select-String "interview-demo-001"
```

## 9. 展示错误响应

删除不存在的文档：

```powershell
python -m examples.api_client_demo `
  document-delete `
  --document-id "not_found"
```

展示：

```text
HTTP 404
status=error
error.code=resource_not_found
retryable=false
```

说明错误响应不会泄露 Python 堆栈和内部路径。

## 10. 展示业务失败区别

说明以下结果可以是 HTTP 200：

```text
evidence_insufficient
needs_human_review=true
execution_failed
failure_reason非空
```

其含义是 API 已成功完成执行，但 Agent 不能形成可信自动结论。

## 11. 删除演示文档

```powershell
python -m examples.api_client_demo `
  document-delete `
  --document-id "demo_charging_note"
```

## 12. 停止服务

```powershell
docker compose down
```

不会删除 Chroma 和日志卷。

## 13. 面试讲解重点

```text
1. 不是普通聊天机器人，而是严格Schema驱动的Agent平台。
2. Tool Calling和Skills负责确定性能力。
3. RAG负责证据约束，不允许自由编造来源。
4. Review Agent负责证据、风险和人工复核边界。
5. Request ID和Trace ID支持问题定位。
6. HTTP失败和业务失败被明确区分。
7. pytest、评测、Smoke Test和Docker形成工程闭环。
```