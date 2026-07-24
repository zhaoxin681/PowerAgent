"""PowerAgent API业务路由核心测试。"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any, cast

from fastapi.testclient import TestClient

from agent_core.schemas import (
    PowerSystemIssue,
    Severity,
    Subsystem,
    TaskType,
)
from app.config import (
    AppSettings,
    RuntimeEnvironment,
)
from app.dependencies import (
    ApplicationServices,
    create_skill_registry,
)
from app.main import create_app
from app.schemas import (
    RndAnalysisApiRequest,
    WorkflowAnalysisData,
)
from app.services import WorkflowServiceResult
from skills.schemas import RiskLevel
from workflows.rnd_models import (
    RndAnalysisResult,
    RndAnalysisStatus,
)

def make_settings() -> AppSettings:
    """构造API路由测试配置。"""

    return AppSettings(
        service_name="PowerAgent Test",
        service_version="0.1.0-test",
        environment=RuntimeEnvironment.TEST,
        api_prefix="/api/v1",
        host="127.0.0.1",
        port=8000,
        log_level="INFO",
        log_dir="logs/test",
        chroma_path="data/test_chroma",
        chroma_collection="test_collection",
        embedding_backend="hash",
        hash_embedding_dimension=256,
        max_replans=1,
    )


def make_issue(
    task_type: TaskType,
) -> PowerSystemIssue:
    """构造API测试问题。"""

    return PowerSystemIssue(
        raw_text="测试动力系统请求",
        subsystem=Subsystem.BATTERY,
        task_type=task_type,
        symptoms=["单体压差扩大"],
        operating_conditions=[],
        user_hypotheses=[],
        requested_outputs=["分析结果"],
        missing_information=[],
        severity=Severity.MEDIUM,
        confidence=0.95,
    )

class FakeWorkflowService:
    """返回固定通用工作流结果。"""

    def analyze(
        self,
        request: Any,
    ) -> WorkflowServiceResult:
        return WorkflowServiceResult(
            trace_id="trace_api_workflow",
            data=WorkflowAnalysisData(
                issue=make_issue(
                    TaskType.FAULT_DIAGNOSIS
                ),
                route=(
                    TaskType.FAULT_DIAGNOSIS
                ),
                route_status="available",
                route_reason="测试路由",
                review_result=None,
                final_report=None,
                needs_human_review=False,
                warnings=[],
                execution_trace=None,
                intermediate_results=None,
            ),
        )


class FakeRndAnalysisService:
    """返回固定研发分析结果。"""

    def analyze(
        self,
        request: RndAnalysisApiRequest,
    ) -> RndAnalysisResult:
        return RndAnalysisResult(
            status=(
                RndAnalysisStatus.EXECUTION_FAILED
            ),
            trace_id=request.trace_id,
            issue=make_issue(
                TaskType.RND_ANALYSIS
            ),
            summary="测试研发分析失败结果",
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
            failure_reason="测试失败原因",
        )


def build_fake_services(
    _: AppSettings,
) -> ApplicationServices:
    """创建业务路由测试服务。"""

    return cast(
        ApplicationServices,
        SimpleNamespace(
            registry=create_skill_registry(),
            workflow_service=(
                FakeWorkflowService()
            ),
            rnd_analysis_service=(
                FakeRndAnalysisService()
            ),
        ),
    )


def test_list_skills_returns_registered_catalog(
) -> None:
    """Skill接口应返回真实注册目录。"""

    application = create_app(
        make_settings(),
        service_builder=build_fake_services,
    )

    with TestClient(application) as client:
        response = client.get(
            "/api/v1/skills"
        )

    payload = response.json()

    assert response.status_code == 200
    assert payload["status"] == "success"
    assert payload["trace_id"] is None
    assert payload["data"]["count"] == 9
    assert (
        len(payload["data"]["skills"])
        == 9
    )


def test_workflow_route_returns_trace_id(
) -> None:
    """通用接口应返回工作流真实trace_id。"""

    application = create_app(
        make_settings(),
        service_builder=build_fake_services,
    )

    with TestClient(application) as client:
        response = client.post(
            "/api/v1/workflows/analyze",
            json={
                "raw_input": "分析电池异常",
            },
        )

    payload = response.json()

    assert response.status_code == 200
    assert (
        payload["trace_id"]
        == "trace_api_workflow"
    )
    assert (
        payload["data"]["route"]
        == "fault_diagnosis"
    )
    assert (
        payload["request_id"]
        == response.headers[
            "X-Request-ID"
        ]
    )

    assert (
        payload["request_id"]
        != payload["trace_id"]
    )


def test_rnd_route_returns_domain_result(
) -> None:
    """研发接口应返回结构化领域结果。"""

    application = create_app(
        make_settings(),
        service_builder=build_fake_services,
    )

    with TestClient(application) as client:
        response = client.post(
            "/api/v1/rnd/analyze",
            json={
                "raw_input": "分析高温快充异常",
                "requested_deliverables": [
                    "候选根因"
                ],
            },
        )

    payload = response.json()

    assert response.status_code == 200
    assert (
        payload["status"]
        == "success"
    )
    assert (
        payload["data"]["status"]
        == "execution_failed"
    )
    assert (
        payload["data"][
            "needs_human_review"
        ]
        is True
    )


def test_business_route_returns_503_when_services_fail(
) -> None:
    """核心服务失败时业务接口不得继续执行。"""

    def failed_builder(
        _: AppSettings,
    ) -> ApplicationServices:
        raise RuntimeError(
            "测试依赖初始化失败"
        )

    application = create_app(
        make_settings(),
        service_builder=failed_builder,
    )

    with TestClient(application) as client:
        ready_response = client.get(
            "/health/ready"
        )

        skills_response = client.get(
            "/api/v1/skills"
        )

    assert ready_response.status_code == 503
    assert skills_response.status_code == 503