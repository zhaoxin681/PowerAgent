"""PowerAgent API依赖装配核心测试。"""

from __future__ import annotations

import logging
from pathlib import Path

from agent_core.llm_client import LLMClient
from app.config import (
    AppSettings,
    EmbeddingBackend,
    RuntimeEnvironment,
)
from app.dependencies import (
    build_application_services,
    create_skill_registry,
)
from rag.embeddings import (
    HashEmbeddingProvider,
)


EXPECTED_SKILLS = {
    "knowledge_lookup",
    "battery_analysis",
    "thermal_analysis",
    "charging_analysis",
    "digital_twin",
    "parameter_optimization",
    "cloud_dispatch",
    "diagnosis",
    "report_generation",
}


def make_test_settings(
    chroma_path: Path,
) -> AppSettings:
    """构造依赖装配测试配置。"""

    return AppSettings(
        service_name="PowerAgent Test",
        service_version="0.1.0-test",
        environment=RuntimeEnvironment.TEST,
        api_prefix="/api/v1",
        host="127.0.0.1",
        port=8000,
        log_level="INFO",
        log_dir=chroma_path.parent / "logs",
        chroma_path=chroma_path,
        chroma_collection=(
            "poweragent_test_knowledge"
        ),
        embedding_backend=(
            EmbeddingBackend.HASH
        ),
        hash_embedding_dimension=256,
        max_replans=1,
    )


def make_stub_llm_client() -> LLMClient:
    """创建不访问真实DeepSeek的LLM客户端。"""

    return LLMClient(
        client=object(),
        logger=logging.getLogger(
            "test.api.dependencies"
        ),
    )


def test_create_skill_registry_registers_defaults(
) -> None:
    """默认Registry应包含全部动力系统Skill。"""

    registry = create_skill_registry()

    actual_names = {
        definition.name
        for definition in registry.list_skills()
    }

    assert len(registry) == 9
    assert actual_names == EXPECTED_SKILLS


def test_build_application_services_wires_dependencies(
    tmp_path: Path,
) -> None:
    """应用服务应共享同一套核心依赖。"""

    settings = make_test_settings(
        tmp_path / "chroma"
    )

    llm_client = make_stub_llm_client()

    embedding_provider = (
        HashEmbeddingProvider(
            dimension=256,
        )
    )

    services = build_application_services(
        settings,
        llm_client=llm_client,
        embedding_provider=embedding_provider,
    )

    assert services.llm_client is llm_client
    assert (
        services.poweragent_workflow.registry
        is services.registry
    )
    assert (
        services.poweragent_workflow.rag_pipeline
        is services.rag_pipeline
    )
    assert (
        services.rnd_analysis_workflow
        .base_workflow
        is services.poweragent_workflow
    )
    assert services.vector_store.count() == 0