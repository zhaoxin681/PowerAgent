"""构建PowerAgent本地Chroma向量知识库。
将文档加载、切分、向量化和存储检索串联成一条完整的RAG数据库构建流水线。
"""

from __future__ import annotations

import argparse
from pathlib import Path

from rag.document_loader import DocumentLoader
from rag.embeddings import (
    ChromaDefaultEmbeddingProvider,
    HashEmbeddingProvider,
)
from rag.text_splitter import TextSplitter
from rag.vector_store import ChromaVectorStore


PROJECT_ROOT = Path(__file__).resolve().parents[1]
KNOWLEDGE_BASE_DIR = (
    PROJECT_ROOT / "docs" / "knowledge_base"
)
CHROMA_DIRECTORY = (
    PROJECT_ROOT / "data" / "chroma"
) # 构建向量库模式！！！


def create_embedding_provider(
    provider_name: str,
):
    """根据命令行参数创建Embedding实现。"""

    if provider_name == "default":
        return ChromaDefaultEmbeddingProvider()

    if provider_name == "hash":
        return HashEmbeddingProvider(
            dimension=256
        )

    raise ValueError(
        f"未知Embedding实现：{provider_name}"
    )


def main() -> None:
    """构建知识库并执行一次示例检索。"""

    parser = argparse.ArgumentParser(
        description="构建PowerAgent动力系统向量知识库"
    )
    parser.add_argument(
        "--embedding-provider",
        choices=("default", "hash"),
        default="default",
        help=(
            "default使用Chroma本地Embedding；"
            "hash用于离线流程测试"
        ),
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help="构建前清空现有知识集合",
    )

    args = parser.parse_args()

    loader = DocumentLoader(
        source_root=PROJECT_ROOT
    )
    splitter = TextSplitter(
        chunk_size=600,
        chunk_overlap=80,
    )
    embedding_provider = (
        create_embedding_provider(
            args.embedding_provider
        )
    )

    vector_store = ChromaVectorStore(
        persist_directory=CHROMA_DIRECTORY,
        embedding_provider=embedding_provider,
        collection_name="poweragent_knowledge",
    )

    if args.reset:
        vector_store.reset()
    
    documents = loader.load_directory(
        KNOWLEDGE_BASE_DIR
    )
    chunks = splitter.split_documents(
        documents
    )
    processed_count = vector_store.add_chunks(
        chunks
    )

    print("=" * 72)
    print("PowerAgent向量知识库构建完成")
    print("=" * 72)
    print(f"知识文档数量：{len(documents)}")
    print(f"知识块数量：{len(chunks)}")
    print(f"本次写入数量：{processed_count}")
    print(f"向量库总数量：{vector_store.count()}")
    print(
        "Embedding实现："
        f"{embedding_provider.name}"
    )
    print(f"持久化目录：{CHROMA_DIRECTORY}")

    sample_query = (
        "动力电池单体压差持续扩大可能是什么原因？"
    )

    results = vector_store.search(
        query=sample_query,
        top_k=3,
    )

    print("\n示例问题：")
    print(sample_query)

    print("\n检索结果：")

    for result in results:
        print("-" * 72)
        print(f"排名：{result.rank}")
        print(f"相关性：{result.score:.4f}")
        print(f"标题：{result.title}")
        print(f"章节：{result.section_path}")
        print(f"来源：{result.source_path}")
        print(f"内容：{result.content[:160]}")

    print("=" * 72)


if __name__ == "__main__":
    main()