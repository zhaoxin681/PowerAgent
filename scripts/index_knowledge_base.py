"""Index bundled knowledge-base documents into the configured Chroma store."""

from __future__ import annotations

import argparse
from pathlib import Path

from app.config import AppSettings
from app.dependencies import create_embedding_provider
from rag.document_loader import DocumentLoader
from rag.text_splitter import TextSplitter
from rag.vector_store import ChromaVectorStore


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_KNOWLEDGE_DIR = PROJECT_ROOT / "docs" / "knowledge_base"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Index PowerAgent bundled knowledge-base documents.",
    )
    parser.add_argument(
        "--knowledge-dir",
        default=str(DEFAULT_KNOWLEDGE_DIR),
        help="Directory containing Markdown/TXT/PDF knowledge documents.",
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Reset the configured Chroma collection before indexing.",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=64,
        help="Vector-store upsert batch size.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    settings = AppSettings.from_env()
    knowledge_dir = Path(args.knowledge_dir)

    if not knowledge_dir.exists():
        raise SystemExit(
            f"Knowledge directory does not exist: {knowledge_dir}"
        )

    embedding_provider = create_embedding_provider(settings)
    vector_store = ChromaVectorStore(
        persist_directory=settings.chroma_path,
        embedding_provider=embedding_provider,
        collection_name=settings.chroma_collection,
    )

    if args.reset:
        vector_store.reset()

    loader = DocumentLoader(source_root=PROJECT_ROOT)
    splitter = TextSplitter(
        chunk_size=settings.document_chunk_size,
        chunk_overlap=settings.document_chunk_overlap,
    )

    documents = loader.load_directory(knowledge_dir, recursive=True)
    chunks = splitter.split_documents(documents)
    upserted_count = vector_store.add_chunks(
        chunks,
        batch_size=args.batch_size,
    )

    print("PowerAgent knowledge-base indexing completed")
    print(f"knowledge_dir={knowledge_dir}")
    print(f"collection={settings.chroma_collection}")
    print(f"embedding_provider={embedding_provider.name}")
    print(f"documents={len(documents)}")
    print(f"chunks={len(chunks)}")
    print(f"upserted={upserted_count}")
    print(f"total_chunks={vector_store.count()}")


if __name__ == "__main__":
    main()
