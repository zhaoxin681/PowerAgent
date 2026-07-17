"""演示PowerAgent证据约束RAG回答。组装 检索器、大模型客户端、RAG流水线"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from agent_core.llm_client import LLMClient
from rag.embeddings import (
    ChromaDefaultEmbeddingProvider,
    HashEmbeddingProvider,
)
from rag.rag_pipeline import RAGPipeline
from rag.retriever import Retriever
from rag.schemas import (
    RAGAnswer,
    RAGCitation,
)
from rag.vector_store import ChromaVectorStore


PROJECT_ROOT = Path(__file__).resolve().parents[1]
CHROMA_DIRECTORY = PROJECT_ROOT / "data" / "chroma"


class MockRAGLLMClient:
    """不访问真实API的RAG回答生成器。不调用大模型跑通 检索->生成->引用校验重建"""

    def parse_structured(
        self,
        *,
        developer_prompt: str,
        user_input: str,
        response_model: type[RAGAnswer],
    ) -> RAGAnswer:
        evidence_text = user_input.split(
            "EVIDENCE_JSON_START",
            maxsplit=1,
        )[1].split(
            "EVIDENCE_JSON_END",
            maxsplit=1,
        )[0].strip()

        evidence_records: list[
            dict[str, Any]
        ] = json.loads(evidence_text)

        first_evidence = evidence_records[0]

        content = str(
            first_evidence["content"]
        )

        excerpt = content[: min(80, len(content))]

        return RAGAnswer(
            question="由Pipeline覆盖为原始问题",
            answer=(
                "Mock模式已根据首条检索证据"
                "生成结构化回答。"
            ),
            citations=[
                RAGCitation(
                    chunk_id=str(
                        first_evidence["chunk_id"]
                    ),
                    document_id=str(
                        first_evidence["document_id"]
                    ),
                    title=str(
                        first_evidence["title"]
                    ),
                    section_path=str(
                        first_evidence.get(
                            "section_path",
                            "",
                        )
                    ),
                    page_number=(
                        first_evidence.get(
                            "page_number"
                        )
                    ),
                    supported_claim=(
                        "该证据支撑当前知识回答。"
                    ),
                    evidence_text=excerpt,
                )
            ],
            confidence=0.70,
            sufficient_evidence=True,
            missing_information=[],
            needs_human_review=True,
        )


def create_embedding_provider(
    provider_name: str,
):
    """创建Embedding实现。"""

    if provider_name == "default":
        return ChromaDefaultEmbeddingProvider()

    return HashEmbeddingProvider(
        dimension=256
    )


def main() -> None:
    """运行RAG回答Demo。"""

    parser = argparse.ArgumentParser(
        description="运行PowerAgent RAG回答Demo"
    )
    parser.add_argument(
        "--mode",
        choices=("mock", "real"),
        default="mock",
        help="mock不访问API，real调用DeepSeek",
    )
    parser.add_argument(
        "--embedding-provider",
        choices=("default", "hash"),
        default="default",
    )
    parser.add_argument(
        "--question",
        default=(
            "为什么动力电池单体压差"
            "会持续扩大？"
        ),
    )

    args = parser.parse_args()

    embedding_provider = create_embedding_provider(
        args.embedding_provider
    )

    vector_store = ChromaVectorStore(
        persist_directory=CHROMA_DIRECTORY,
        embedding_provider=embedding_provider,
        collection_name="poweragent_knowledge",
    )

    retriever = Retriever(
        vector_store=vector_store
    )

    llm_client = (
        MockRAGLLMClient()
        if args.mode == "mock"
        else LLMClient()
    )

    pipeline = RAGPipeline(
        retriever=retriever,
        llm_client=llm_client,
    )

    result = pipeline.answer(
        args.question,
        top_k=4,
        min_score=0.20,
    )

    print(
        result.model_dump_json(
            indent=2,
        )
    )


if __name__ == "__main__":
    main()