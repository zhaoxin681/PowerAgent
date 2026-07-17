"""演示动力系统知识检索。"""

from __future__ import annotations

import argparse
from pathlib import Path

from agent_core.schemas import Subsystem
from rag.embeddings import (
    ChromaDefaultEmbeddingProvider,
    HashEmbeddingProvider,
)
from rag.retriever import Retriever
from rag.vector_store import ChromaVectorStore


PROJECT_ROOT = Path(__file__).resolve().parents[1]
CHROMA_DIRECTORY = PROJECT_ROOT / "data" / "chroma"


def create_embedding_provider(
    provider_name: str,
):
    """创建与知识库构建时一致的Embedding。"""

    if provider_name == "default":
        return ChromaDefaultEmbeddingProvider()

    return HashEmbeddingProvider(
        dimension=256
    )


def main() -> None:
    """运行检索Demo。"""

    parser = argparse.ArgumentParser(
        description="测试PowerAgent动力系统Retriever"
    )
    parser.add_argument(
        "--embedding-provider",
        choices=("default", "hash"),
        default="default",
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

    questions = [
        (
            "为什么动力电池单体压差"
            "会持续扩大？"
        ),
        (
            "快充过程中温度过高"
            "应该检查哪些因素？"
        ),
        (
            "充电机与BMS通信异常"
            "可能涉及哪些检查项？"
        ),
    ]

    for question in questions:
        print("=" * 72)
        print(f"问题：{question}")

        results = retriever.retrieve(
            question,
            top_k=3,
            min_score=0.20,
        )

        if not results:
            print("没有检索到满足阈值的证据。")
            continue

        for result in results:
            print("-" * 72)
            print(f"排名：{result.rank}")
            print(f"分数：{result.score:.4f}")
            print(f"文档：{result.title}")
            print(f"章节：{result.section_path}")
            print(f"chunk_id：{result.chunk_id}")
            print(f"内容：{result.content[:180]}")


if __name__ == "__main__":
    main()