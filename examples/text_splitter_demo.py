"""演示动力系统知识文档切分。"""

from __future__ import annotations

from collections import Counter
from pathlib import Path

from rag.document_loader import DocumentLoader
from rag.text_splitter import TextSplitter


PROJECT_ROOT = Path(__file__).resolve().parents[1]
KNOWLEDGE_BASE_DIR = (
    PROJECT_ROOT / "docs" / "knowledge_base"
)


def main() -> None:
    """加载并切分知识文档。"""

    loader = DocumentLoader(
        source_root=PROJECT_ROOT
    )
    splitter = TextSplitter(
        chunk_size=600,
        chunk_overlap=80,
    )

    documents = loader.load_directory(
        KNOWLEDGE_BASE_DIR
    )
    chunks = splitter.split_documents(
        documents
    )

    chunk_lengths = [
        len(chunk.content)
        for chunk in chunks
    ]

    document_chunk_counts = Counter(
        chunk.document_id
        for chunk in chunks
    )

    print("=" * 72)
    print("PowerAgent知识文档切分结果")
    print("=" * 72)
    print(f"原始文档数量：{len(documents)}")
    print(f"知识块数量：{len(chunks)}")
    print(
        "平均知识块长度："
        f"{sum(chunk_lengths) / len(chunk_lengths):.1f}"
    )
    print(
        f"最小知识块长度：{min(chunk_lengths)}"
    )
    print(
        f"最大知识块长度：{max(chunk_lengths)}"
    )
    print(
        "重复chunk_id数量："
        f"{len(chunks) - len({chunk.chunk_id for chunk in chunks})}"
    )

    print("\n每份文档的知识块数量：")

    for document_id, count in sorted(
        document_chunk_counts.items()
    ):
        print(f"  {document_id}: {count}")

    print("\n前5个知识块：")

    for chunk in chunks[:5]:
        print("-" * 72)
        print(f"chunk_id：{chunk.chunk_id}")
        print(f"document_id：{chunk.document_id}")
        print(f"section：{chunk.section_path}")
        print(f"length：{len(chunk.content)}")
        print(f"content：{chunk.content[:100]}")

    print("=" * 72)


if __name__ == "__main__":
    main()