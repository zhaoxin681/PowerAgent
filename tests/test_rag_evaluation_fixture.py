"""RAG评测知识库固定构建测试。"""

from pathlib import Path

from evaluation.rag_fixture import (
    RAG_EVAL_DOCUMENT_FILES,
    build_rag_evaluation_resources,
    load_rag_evaluation_documents,
    resolve_rag_evaluation_documents,
    split_rag_evaluation_documents,
)


def test_rag_evaluation_documents_are_fixed() -> None:
    """评测知识库应只加载指定的六份文档。"""

    paths = (
        resolve_rag_evaluation_documents()
    )

    documents = (
        load_rag_evaluation_documents(
            paths
        )
    )

    assert len(paths) == len(
        RAG_EVAL_DOCUMENT_FILES
    )

    assert len(documents) == len(
        RAG_EVAL_DOCUMENT_FILES
    )

    assert {
        document.document_id
        for document in documents
    } == {
        "battery_internal_short_circuit",
        "charging_communication_faults",
        "power_system_safety_terms",
        "battery_digital_twin",
        "battery_fault_verification",
        "battery_thermal_runaway",
    }



def test_rag_evaluation_chunk_ids_are_stable() -> None:
    """相同文档和切分参数应产生相同Chunk ID。"""

    paths = (
        resolve_rag_evaluation_documents()
    )

    documents = (
        load_rag_evaluation_documents(
            paths
        )
    )

    first_chunks = (
        split_rag_evaluation_documents(
            documents
        )
    )

    second_chunks = (
        split_rag_evaluation_documents(
            documents
        )
    )

    assert [
        chunk.chunk_id
        for chunk in first_chunks
    ] == [
        chunk.chunk_id
        for chunk in second_chunks
    ]



def test_rag_evaluation_store_is_isolated(
    tmp_path: Path,
) -> None:
    """评测知识库应写入独立临时目录。"""

    evaluation_directory = (
        tmp_path
        / "rag_eval_chroma"
    )

    resources = (
        build_rag_evaluation_resources(
            persist_directory=(
                evaluation_directory
            ),
            reset=True,
        )
    )

    assert evaluation_directory.exists()

    assert (
        resources.vector_store.count()
        == len(resources.chunks)
    )

    assert (
        resources.embedding_provider_name
        == "hash_ngram_1_3_256"
    )