"""构建独立RAG评测向量库并输出Manifest。"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from evaluation.rag_fixture import (
    RAG_EVAL_CHUNK_OVERLAP,
    RAG_EVAL_CHUNK_SIZE,
    RAG_EVAL_COLLECTION_NAME,
    RAG_EVAL_PERSIST_DIRECTORY,
    build_rag_evaluation_resources,
    calculate_file_sha256,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]

DEFAULT_MANIFEST_FILE = (
    PROJECT_ROOT
    / "evaluation"
    / "results"
    / "rag_eval_manifest.json"
)


def build_manifest(
    resources,
) -> dict[str, object]:
    """生成本次RAG评测知识库清单。"""

    document_records = []

    for path, document in zip(
        resources.document_paths,
        resources.documents,
        strict=True,
    ):
        document_records.append(
            {
                "document_id": (
                    document.document_id
                ),
                "title": document.title,
                "subsystem": (
                    document.subsystem.value
                ),
                "topic": document.topic,
                "version": document.version,
                "source_path": (
                    document.source_path
                ),
                "content_sha256": (
                    calculate_file_sha256(
                        path
                    )
                ),
            }
        )

    chunk_records = [
        {
            "chunk_id": chunk.chunk_id,
            "document_id": (
                chunk.document_id
            ),
            "section_path": (
                chunk.section_path
            ),
            "chunk_index": (
                chunk.chunk_index
            ),
            "content_chars": len(
                chunk.content
            ),
        }
        for chunk in resources.chunks
    ]

    return {
        "collection_name": (
            RAG_EVAL_COLLECTION_NAME
        ),
        "persist_directory": str(
            RAG_EVAL_PERSIST_DIRECTORY
        ),
        "embedding_provider": (
            resources.embedding_provider_name
        ),
        "chunk_size": (
            RAG_EVAL_CHUNK_SIZE
        ),
        "chunk_overlap": (
            RAG_EVAL_CHUNK_OVERLAP
        ),
        "document_count": len(
            resources.documents
        ),
        "chunk_count": len(
            resources.chunks
        ),
        "vector_store_count": (
            resources.vector_store.count()
        ),
        "documents": document_records,
        "chunks": chunk_records,
    }


def parse_arguments() -> argparse.Namespace:
    """解析命令行参数。"""

    parser = argparse.ArgumentParser(
        description=(
            "构建PowerAgent独立RAG评测知识库"
        ),
    )

    parser.add_argument(
        "--manifest-file",
        type=Path,
        default=DEFAULT_MANIFEST_FILE,
        help="评测知识库Manifest输出路径",
    )

    return parser.parse_args()


def main() -> None:
    """构建评测知识库并写入Manifest。"""

    args = parse_arguments()

    resources = (
        build_rag_evaluation_resources(
            reset=True
        )
    )

    manifest = build_manifest(
        resources
    )

    args.manifest_file.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    args.manifest_file.write_text(
        json.dumps(
            manifest,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    print("=" * 72)
    print("RAG评测知识库构建完成")
    print("=" * 72)
    print(
        f"知识文档数量："
        f"{len(resources.documents)}"
    )
    print(
        f"知识块数量："
        f"{len(resources.chunks)}"
    )
    print(
        f"向量库数量："
        f"{resources.vector_store.count()}"
    )
    print(
        "Embedding实现："
        f"{resources.embedding_provider_name}"
    )
    print(
        f"Collection："
        f"{RAG_EVAL_COLLECTION_NAME}"
    )
    print(
        f"持久化目录："
        f"{RAG_EVAL_PERSIST_DIRECTORY}"
    )
    print(
        f"Manifest："
        f"{args.manifest_file}"
    )


if __name__ == "__main__":
    main()