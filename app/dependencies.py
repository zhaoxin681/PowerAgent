"""PowerAgent API真实依赖装配。组装根模式"""

from __future__ import annotations

from dataclasses import dataclass

from agent_core.decision_agent import DecisionAgent
from agent_core.issue_parser import (
    PowerSystemIssueParser,
)
from agent_core.llm_client import LLMClient
from agent_core.planner_agent import PlannerAgent
from agent_core.report_agent import ReportAgent
from agent_core.review_agent import ReviewAgent
from agent_core.router_agent import RouterAgent
from agent_core.skill_registry import SkillRegistry
from agent_core.workflow import PowerAgentWorkflow
from app.config import (
    AppSettings,
    EmbeddingBackend,
)
from rag.embeddings import (
    ChromaDefaultEmbeddingProvider,
    EmbeddingProvider,
    HashEmbeddingProvider,
)
from rag.rag_pipeline import RAGPipeline
from rag.retriever import Retriever
from rag.vector_store import ChromaVectorStore
from skills.catalog import create_default_skills
from workflows.rnd_analysis_workflow import (
    RndAnalysisWorkflow,
)
from app.services import (
    RndAnalysisService,
    WorkflowService,
)
from app.document_service import (
    DocumentIngestionService,
)
from rag.document_loader import DocumentLoader
from rag.text_splitter import TextSplitter

# 服务容器，该容器会被挂载到app.state上，避免每个请求都重新创建
@dataclass(frozen=True, slots=True)
class ApplicationServices:
    """FastAPI生命周期内共享的PowerAgent服务。"""

    llm_client: LLMClient
    registry: SkillRegistry
    vector_store: ChromaVectorStore
    rag_pipeline: RAGPipeline
    poweragent_workflow: PowerAgentWorkflow
    rnd_analysis_workflow: RndAnalysisWorkflow
    workflow_service: WorkflowService
    rnd_analysis_service: RndAnalysisService
    document_service: DocumentIngestionService


def create_skill_registry() -> SkillRegistry:
    """创建并注册全部默认动力系统Skill。"""

    registry = SkillRegistry()

    for skill in create_default_skills():
        registry.register(skill)

    return registry

# 根据配置选择Embedding实现
def create_embedding_provider(
    settings: AppSettings,
) -> EmbeddingProvider:
    """根据应用配置创建Embedding实现。"""

    if (
        settings.embedding_backend
        == EmbeddingBackend.HASH
    ):
        return HashEmbeddingProvider(
            dimension=(
                settings.hash_embedding_dimension
            )
        )

    return ChromaDefaultEmbeddingProvider()

# 核心装配函数
def build_application_services(
    settings: AppSettings,
    *,
    llm_client: LLMClient | None = None,
    embedding_provider: (
        EmbeddingProvider | None
    ) = None,
) -> ApplicationServices:
    """装配PowerAgent API使用的全部真实依赖。

    可选依赖参数用于测试，避免测试连接真实DeepSeek。
    """

    resolved_llm_client = (
        llm_client
        if llm_client is not None
        else LLMClient()
    )

    registry = create_skill_registry()

    resolved_embedding_provider = (
        embedding_provider
        if embedding_provider is not None
        else create_embedding_provider(settings)
    )

    vector_store = ChromaVectorStore(
        persist_directory=settings.chroma_path,  # 数据落盘路径
        embedding_provider=(
            resolved_embedding_provider
        ),
        collection_name=(
            settings.chroma_collection
        ),
    )

    document_service = (
        DocumentIngestionService(
            loader=DocumentLoader(),
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

    # 启动阶段执行一次轻量本地访问，
    # 确认Chroma集合可以正常读取。
    vector_store.count()

    retriever = Retriever(
        vector_store=vector_store,
    )

    rag_pipeline = RAGPipeline(
        retriever=retriever,
        llm_client=resolved_llm_client,
    )

    # 整个装配函数的核心
    poweragent_workflow = PowerAgentWorkflow(
        issue_parser=PowerSystemIssueParser(
            llm_client=resolved_llm_client,
        ),
        router_agent=RouterAgent(),
        planner_agent=PlannerAgent(
            registry=registry,
        ),
        decision_agent=DecisionAgent(
            max_replans=settings.max_replans,
        ),
        review_agent=ReviewAgent(),
        report_agent=ReportAgent(),
        registry=registry,
        rag_pipeline=rag_pipeline,
    )

    rnd_analysis_workflow = (
        RndAnalysisWorkflow(
            base_workflow=poweragent_workflow,
            llm_client=resolved_llm_client,
        )
    )

    workflow_service = WorkflowService(
        workflow=poweragent_workflow,
    )

    rnd_analysis_service = RndAnalysisService(
        workflow=rnd_analysis_workflow,
    )

    return ApplicationServices(
        llm_client=resolved_llm_client,
        registry=registry,
        vector_store=vector_store,
        rag_pipeline=rag_pipeline,
        poweragent_workflow=(
            poweragent_workflow
        ),
        rnd_analysis_workflow=(
            rnd_analysis_workflow
        ),
        workflow_service=workflow_service,
        rnd_analysis_service=(
            rnd_analysis_service
        ),
        document_service=document_service,
    )