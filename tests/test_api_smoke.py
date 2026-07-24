"""PowerAgent API离线端到端Smoke Test。"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import (
    Any,
    cast,
)

from fastapi.testclient import TestClient

from agent_core.schemas import (
    PowerSystemIssue,
    Severity,
    Subsystem,
    TaskType,
)
from app.config import (
    AppSettings,
    EmbeddingBackend,
    RuntimeEnvironment,
)
from app.dependencies import (
    ApplicationServices,
    create_skill_registry,
)
from app.document_service import (
    DocumentIngestionService,
)
from app.main import create_app
from app.services import (
    RndAnalysisService,
    WorkflowService,
)
from rag.document_loader import (
    DocumentLoader,
)
from rag.embeddings import (
    HashEmbeddingProvider,
)
from rag.text_splitter import (
    TextSplitter,
)
from rag.vector_store import (
    ChromaVectorStore,
)
from skills.schemas import RiskLevel
from workflows.rnd_models import (
    RndAnalysisRequest,
    RndAnalysisResult,
    RndAnalysisStatus,
)


def make_settings(
    tmp_path: Path,
) -> AppSettings:
    """构造完全隔离的Smoke Test配置。"""

    return AppSettings(
        service_name="PowerAgent Smoke Test",
        service_version="0.1.0-test",
        environment=RuntimeEnvironment.TEST,
        api_prefix="/api/v1",
        host="127.0.0.1",
        port=8000,
        log_level="INFO",
        log_dir=tmp_path / "logs",
        chroma_path=tmp_path / "chroma",
        chroma_collection=(
            "poweragent_smoke"
        ),
        embedding_backend=(
            EmbeddingBackend.HASH
        ),
        hash_embedding_dimension=256,
        max_replans=1,
        upload_temp_dir=(
            tmp_path / "uploads" / "tmp"
        ),
        document_chunk_size=200,
        document_chunk_overlap=20,
    )


def make_issue(
    task_type: TaskType,
) -> PowerSystemIssue:
    """构造离线工作流返回的问题模型。"""

    return PowerSystemIssue(
        raw_text=(
            "分析高SOC快充阶段的"
            "单体压差扩大问题"
        ),
        subsystem=Subsystem.BATTERY,
        task_type=task_type,
        symptoms=[
            "高SOC阶段单体压差扩大"
        ],
        operating_conditions=[],
        user_hypotheses=[],
        requested_outputs=[
            "分析结果"
        ],
        missing_information=[],
        severity=Severity.MEDIUM,
        confidence=0.95,
    )


class OfflinePowerAgentWorkflow:
    """不调用真实LLM的通用工作流。"""

    def invoke(
        self,
        raw_input: str,
        *,
        trace_id: str | None = None,
        max_retries: int = 2,
        skill_inputs: (
            dict[str, dict[str, Any]]
            | None
        ) = None,
    ) -> dict[str, Any]:
        """返回满足Service契约的固定状态。"""

        del raw_input
        del max_retries
        del skill_inputs

        return {
            "trace_id": trace_id,
            "issue": make_issue(
                TaskType.FAULT_DIAGNOSIS
            ),
            "route": (
                TaskType.FAULT_DIAGNOSIS
            ),
            "route_status": "available",
            "route_reason": (
                "离线Smoke Test路由"
            ),
            "review_result": None,
            "final_report": None,
            "needs_human_review": False,
            "execution_trace": [],
            "tool_results": [],
            "rag_answers": [],
            "errors": [],
        }


class OfflineRndAnalysisWorkflow:
    """不调用真实LLM的研发分析工作流。"""

    def analyze(
        self,
        request: RndAnalysisRequest,
        *,
        skill_inputs: (
            dict[str, dict[str, Any]]
            | None
        ) = None,
        max_retries: int = 2,
    ) -> RndAnalysisResult:
        """返回结构化业务失败结果。"""

        del skill_inputs
        del max_retries

        return RndAnalysisResult(
            status=(
                RndAnalysisStatus
                .EXECUTION_FAILED
            ),
            trace_id=request.trace_id,
            issue=make_issue(
                TaskType.RND_ANALYSIS
            ),
            summary=(
                "离线Smoke Test不调用"
                "真实研发分析LLM。"
            ),
            known_facts=[],
            missing_information=[],
            hypotheses=[],
            experiments=[],
            team_assignments=[],
            dependencies=[],
            risks=[],
            overall_risk_level=(
                RiskLevel.MEDIUM
            ),
            needs_human_review=True,
            unresolved_items=[],
            failure_reason=(
                "离线模式使用固定研发结果"
            ),
        )


def build_smoke_services(
    settings: AppSettings,
) -> ApplicationServices:
    """创建离线Smoke Test服务容器。"""

    vector_store = ChromaVectorStore(
        persist_directory=(
            settings.chroma_path
        ),
        embedding_provider=(
            HashEmbeddingProvider(
                dimension=(
                    settings
                    .hash_embedding_dimension
                )
            )
        ),
        collection_name=(
            settings.chroma_collection
        ),
    )

    document_service = (
        DocumentIngestionService(
            loader=DocumentLoader(
                source_root=(
                    settings
                    .upload_temp_dir
                    .parent
                    .parent
                )
            ),
            splitter=TextSplitter(
                chunk_size=(
                    settings.document_chunk_size
                ),
                chunk_overlap=(
                    settings
                    .document_chunk_overlap
                ),
            ),
            vector_store=vector_store,
        )
    )

    return cast(
        ApplicationServices,
        SimpleNamespace(
            registry=create_skill_registry(),
            workflow_service=WorkflowService(
                workflow=(
                    OfflinePowerAgentWorkflow()
                )
            ),
            rnd_analysis_service=(
                RndAnalysisService(
                    workflow=(
                        OfflineRndAnalysisWorkflow()
                    )
                )
            ),
            document_service=document_service,
        ),
    )


def test_offline_api_smoke_loop(
    tmp_path: Path,
) -> None:
    """验证API完整核心链路和状态变化。"""

    application = create_app(
        make_settings(tmp_path),
        service_builder=(
            build_smoke_services
        ),
    )

    with TestClient(application) as client:
        live_response = client.get(
            "/health/live"
        )

        ready_response = client.get(
            "/health/ready"
        )

        docs_response = client.get(
            "/docs"
        )

        openapi_response = client.get(
            "/openapi.json"
        )

        skills_response = client.get(
            "/api/v1/skills"
        )

        upload_response = client.post(
            "/api/v1/knowledge/documents",
            files={
                "file": (
                    "smoke_charging_note.txt",
                    (
                        "高SOC快充阶段出现限流时，"
                        "应检查最高温度、单体电压"
                        "和热管理冷却能力。"
                    ).encode("utf-8"),
                    "text/plain",
                )
            },
            data={
                "topic": "高SOC快充限流",
                "subsystem": "charging",
                "overwrite": "false",
            },
        )

        uploaded_document_id = (
            upload_response
            .json()["data"]["document_id"]
        )

        status_after_upload = client.get(
            "/api/v1/knowledge/status"
        )

        workflow_response = client.post(
            "/api/v1/workflows/analyze",
            headers={
                "X-Request-ID": (
                    "smoke-workflow-request"
                ),
            },
            json={
                "raw_input": (
                    "分析动力电池单体压差扩大"
                ),
                "trace_id": (
                    "smoke_workflow_trace"
                ),
                "max_retries": 1,
                "include_trace": True,
                "include_intermediate_results": (
                    False
                ),
            },
        )

        rnd_response = client.post(
            "/api/v1/rnd/analyze",
            json={
                "raw_input": (
                    "分析高SOC快充限流问题"
                ),
                "trace_id": (
                    "smoke_rnd_trace"
                ),
                "affected_scope": [
                    "部分车辆"
                ],
                "available_data": [
                    "充电电流",
                    "单体电压",
                ],
                "operating_conditions": [],
                "requested_deliverables": [
                    "候选根因",
                    "验证实验",
                ],
                "max_retries": 1,
                "skill_inputs": {},
            },
        )

        delete_response = client.delete(
            (
                "/api/v1/knowledge/"
                "documents/"
                f"{uploaded_document_id}"
            )
        )

        missing_response = client.delete(
            (
                "/api/v1/knowledge/"
                "documents/"
                f"{uploaded_document_id}"
            )
        )

        status_after_delete = client.get(
            "/api/v1/knowledge/status"
        )

    assert live_response.status_code == 200

    assert ready_response.status_code == 200
    assert (
        ready_response.json()["status"]
        == "ready"
    )

    assert docs_response.status_code == 200

    assert (
        "Swagger UI"
        in docs_response.text
    )

    assert (
        openapi_response.status_code
        == 200
    )

    openapi_paths = (
        openapi_response.json()["paths"]
    )

    expected_paths = {
        "/health/live",
        "/health/ready",
        "/api/v1/skills",
        "/api/v1/knowledge/status",
        "/api/v1/knowledge/documents",
        (
            "/api/v1/knowledge/"
            "documents/{document_id}"
        ),
        "/api/v1/workflows/analyze",
        "/api/v1/rnd/analyze",
    }

    assert expected_paths.issubset(
        set(openapi_paths)
    )

    assert skills_response.status_code == 200
    assert (
        skills_response.json()[
            "data"
        ]["count"]
        > 0
    )

    assert upload_response.status_code == 200

    upload_payload = (
        upload_response.json()
    )

    assert (
        uploaded_document_id
        == "smoke_charging_note"
    )

    assert (
        status_after_upload.status_code
        == 200
    )

    assert (
        status_after_upload.json()[
            "data"
        ]["chunk_count"]
        >= 1
    )

    assert (
        workflow_response.status_code
        == 200
    )

    workflow_payload = (
        workflow_response.json()
    )

    assert (
        workflow_payload["request_id"]
        == workflow_response.headers[
            "X-Request-ID"
        ]
    )

    assert (
        workflow_payload["request_id"]
        == "smoke-workflow-request"
    )

    assert (
        workflow_payload["trace_id"]
        == "smoke_workflow_trace"
    )

    assert (
        workflow_payload["data"]["route"]
        == "fault_diagnosis"
    )

    assert rnd_response.status_code == 200

    rnd_payload = rnd_response.json()

    assert (
        rnd_payload["trace_id"]
        == "smoke_rnd_trace"
    )

    assert (
        rnd_payload["data"]["trace_id"]
        == "smoke_rnd_trace"
    )

    assert (
        rnd_payload["data"]["status"]
        == "execution_failed"
    )

    assert (
        rnd_payload["data"][
            "needs_human_review"
        ]
        is True
    )

    assert delete_response.status_code == 200

    assert (
        delete_response.json()["data"][
            "deleted"
        ]
        is True
    )

    assert missing_response.status_code == 404

    assert (
        missing_response.json()["error"][
            "code"
        ]
        == "resource_not_found"
    )

    assert (
        status_after_delete.status_code
        == 200
    )

    assert (
        status_after_delete.json()["data"][
            "chunk_count"
        ]
        == 0
    )