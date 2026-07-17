"""演示PowerAgent动力系统知识文档加载。"""

from __future__ import annotations

from collections import Counter
from pathlib import Path

from rag.document_loader import DocumentLoader


PROJECT_ROOT = Path(__file__).resolve().parents[1]
KNOWLEDGE_BASE_DIR = PROJECT_ROOT / "docs" / "knowledge_base"


def main() -> None:
    """加载知识库并输出统计信息。"""

    loader = DocumentLoader(
        source_root=PROJECT_ROOT,
    )

    documents = loader.load_directory(
        KNOWLEDGE_BASE_DIR,
        recursive=True,
    )  # 递归扫描所有子目录，将全部文档加载成DocumentRecord列表

    subsystem_counts = Counter(
        document.subsystem.value
        for document in documents
    ) # 每个子系统各有多少篇文档
    file_type_counts = Counter(
        document.file_type.value
        for document in documents
    ) # 每种文件类型各有多少
    topic_counts = Counter(
        document.topic or "unknown"
        for document in documents
    ) # 每个主题多少篇

    print("=" * 72)
    print("PowerAgent 动力系统知识文档加载结果")
    print("=" * 72)
    print(f"知识库目录：{KNOWLEDGE_BASE_DIR}")
    print(f"标准文档对象数量：{len(documents)}")

    print("\n子系统分布：")
    for subsystem, count in sorted(
        subsystem_counts.items()
    ):
        print(f"  {subsystem}: {count}")

    print("\n文件类型分布：")
    for file_type, count in sorted(
        file_type_counts.items()
    ):
        print(f"  {file_type}: {count}")

    print("\n主题分布：")
    for topic, count in sorted(topic_counts.items()):
        print(f"  {topic}: {count}")

    print("\n前5份文档：")

    for document in documents[:5]:
        print("-" * 72)
        print(f"document_id：{document.document_id}")
        print(f"title：{document.title}")
        print(f"subsystem：{document.subsystem.value}")
        print(f"topic：{document.topic}")
        print(f"source：{document.source_path}")
        print(f"content_length：{len(document.content)}")

    print("=" * 72)


if __name__ == "__main__":
    main()