"""PowerAgent知识文档上传API核心测试。"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import cast

from fastapi.testclient import TestClient

from app.config import (
    AppSettings,
    EmbeddingBackend,
    RuntimeEnvironment,
)
from app.dependencies import ApplicationServices
from app.main import create_app
from rag.schemas import DocumentType

from app.document_service import (
    DocumentDeletionResult,
    DocumentIngestionResult,
    DuplicateDocumentError,
    KnowledgeBaseStatusResult,
)


class FakeDocumentService:
    """记录上传参数并返回固定入库结果。"""

    def __init__(
        self,
        *,
        raise_duplicate: bool = False,
    ) -> None:
        self.raise_duplicate = raise_duplicate
        self.call_count = 0
        self.received_file_path: Path | None = None
        self.received_filename: str | None = None
        self.received_subsystem: object | None = None
        self.received_topic: str | None = None
        self.received_overwrite: bool | None = None
        self.temp_file_existed_during_call = False

    def ingest_file(
        self,
        file_path: str | Path,
        *,
        original_filename: str,
        subsystem: object | None = None,
        topic: str | None = None,
        overwrite: bool = False,
    ) -> DocumentIngestionResult:
        """模拟知识文档入库。"""

        self.call_count += 1
        self.received_file_path = Path(file_path)
        self.received_filename = original_filename
        self.received_subsystem = subsystem
        self.received_topic = topic
        self.received_overwrite = overwrite

        self.temp_file_existed_during_call = (
            self.received_file_path.exists()
        )

        if self.raise_duplicate:
            raise DuplicateDocumentError(
                ["battery_note"]
            )

        return DocumentIngestionResult(
            document_id="battery_note",
            filename="battery_note.txt",
            file_type=DocumentType.TEXT,
            chunk_count=2,
            upserted_count=2,
            updated=overwrite,
        )

    def get_status(
        self,
    ) -> KnowledgeBaseStatusResult:
        """返回固定知识库状态。"""

        return KnowledgeBaseStatusResult(
            collection_name=(
                "knowledge_upload_test"
            ),
            chunk_count=12,
            embedding_provider=(
                "hash_ngram_1_3_256"
            ),
        )

    def delete_document(
        self,
        document_id: str,
    ) -> DocumentDeletionResult:
        """返回固定删除结果。"""

        deleted = (
            document_id != "not_found"
        )

        return DocumentDeletionResult(
            document_id=document_id,
            deleted_chunk_count=(
                2 if deleted else 0
            ),
            deleted=deleted,
        )


def make_settings(
    tmp_path: Path,
    *,
    max_upload_mb: int = 1,
) -> AppSettings:
    """构造隔离于本地环境的API测试配置。"""

    return AppSettings(
        service_name="PowerAgent Test",
        service_version="0.1.0-test",
        environment=RuntimeEnvironment.TEST,
        api_prefix="/api/v1",
        host="127.0.0.1",
        port=8000,
        log_level="INFO",
        log_dir=tmp_path / "logs",
        chroma_path=tmp_path / "chroma",
        chroma_collection=(
            "knowledge_upload_test"
        ),
        embedding_backend=EmbeddingBackend.HASH,
        hash_embedding_dimension=256,
        max_replans=1,
        max_upload_mb=max_upload_mb,
        upload_temp_dir=(
            tmp_path / "uploads" / "tmp"
        ),
        document_chunk_size=600,
        document_chunk_overlap=80,
    )


def build_test_app(
    tmp_path: Path,
    document_service: FakeDocumentService,
    *,
    max_upload_mb: int = 1,
):
    """创建注入假文档服务的FastAPI应用。"""

    settings = make_settings(
        tmp_path,
        max_upload_mb=max_upload_mb,
    )

    def build_fake_services(
        _: AppSettings,
    ) -> ApplicationServices:
        return cast(
            ApplicationServices,
            SimpleNamespace(
                document_service=document_service,
            ),
        )

    application = create_app(
        settings,
        service_builder=build_fake_services,
    )

    return application, settings


def assert_temp_directory_empty(
    temp_dir: Path,
) -> None:
    """确认上传临时目录中没有残留文件。"""

    if not temp_dir.exists():
        return

    assert list(temp_dir.iterdir()) == []


def test_upload_document_returns_index_result(
    tmp_path: Path,
) -> None:
    """合法TXT文件应写入服务并返回统一响应。"""

    document_service = FakeDocumentService()

    application, settings = build_test_app(
        tmp_path,
        document_service,
    )

    with TestClient(application) as client:
        response = client.post(
            "/api/v1/knowledge/documents",
            files={
                "file": (
                    "battery_note.txt",
                    (
                        "动力电池单体压差扩大可能与"
                        "电芯一致性或采样误差有关。"
                    ).encode("utf-8"),
                    "text/plain",
                )
            },
            data={
                "topic": "电池一致性",
                "subsystem": "battery",
                "overwrite": "false",
            },
        )

    payload = response.json()

    assert response.status_code == 200
    assert payload["status"] == "success"
    assert payload["trace_id"] is None
    assert payload["error"] is None
    assert isinstance(
        payload["request_id"],
        str,
    )
    assert payload["request_id"]

    assert payload["data"] == {
        "document_id": "battery_note",
        "filename": "battery_note.txt",
        "format": "text",
        "chunk_count": 2,
        "upserted_count": 2,
        "status": "indexed",
    }

    assert document_service.call_count == 1
    assert (
        document_service
        .temp_file_existed_during_call
        is True
    )
    assert (
        document_service.received_filename
        == "battery_note.txt"
    )
    assert (
        document_service.received_topic
        == "电池一致性"
    )
    assert (
        getattr(
            document_service.received_subsystem,
            "value",
            None,
        )
        == "battery"
    )
    assert (
        document_service.received_overwrite
        is False
    )

    assert_temp_directory_empty(
        settings.upload_temp_dir
    )


def test_upload_document_rejects_unsupported_type(
    tmp_path: Path,
) -> None:
    """不支持的文件扩展名应返回400。"""

    document_service = FakeDocumentService()

    application, settings = build_test_app(
        tmp_path,
        document_service,
    )

    with TestClient(application) as client:
        response = client.post(
            "/api/v1/knowledge/documents",
            files={
                "file": (
                    "unsafe.exe",
                    b"not-a-document",
                    "application/octet-stream",
                )
            },
        )

    assert response.status_code == 400
    assert (
        "仅支持md/txt/pdf文件"
        in response.json()["detail"]
    )
    assert document_service.call_count == 0

    assert_temp_directory_empty(
        settings.upload_temp_dir
    )


def test_upload_document_rejects_oversized_file(
    tmp_path: Path,
) -> None:
    """超过配置上限的文件应返回413并清理临时文件。"""

    document_service = FakeDocumentService()

    application, settings = build_test_app(
        tmp_path,
        document_service,
        max_upload_mb=1,
    )

    oversized_content = (
        b"x"
        * (1024 * 1024 + 1)
    )

    with TestClient(application) as client:
        response = client.post(
            "/api/v1/knowledge/documents",
            files={
                "file": (
                    "large_document.txt",
                    oversized_content,
                    "text/plain",
                )
            },
        )

    assert response.status_code == 413
    assert (
        "上传文件超过大小限制"
        in response.json()["detail"]
    )
    assert document_service.call_count == 0

    assert_temp_directory_empty(
        settings.upload_temp_dir
    )


def test_upload_duplicate_document_returns_409(
    tmp_path: Path,
) -> None:
    """重复文档未允许覆盖时应返回409。"""

    document_service = FakeDocumentService(
        raise_duplicate=True
    )

    application, settings = build_test_app(
        tmp_path,
        document_service,
    )

    with TestClient(application) as client:
        response = client.post(
            "/api/v1/knowledge/documents",
            files={
                "file": (
                    "battery_note.txt",
                    b"duplicate document",
                    "text/plain",
                )
            },
            data={
                "overwrite": "false",
            },
        )

    assert response.status_code == 409
    assert (
        "battery_note"
        in response.json()["detail"]
    )
    assert document_service.call_count == 1
    assert (
        document_service
        .temp_file_existed_during_call
        is True
    )

    assert_temp_directory_empty(
        settings.upload_temp_dir
    )


def test_get_knowledge_status(
    tmp_path: Path,
) -> None:
    """知识库状态接口应返回集合和知识块数量。"""

    document_service = FakeDocumentService()

    application, _ = build_test_app(
        tmp_path,
        document_service,
    )

    with TestClient(application) as client:
        response = client.get(
            "/api/v1/knowledge/status"
        )

    payload = response.json()

    assert response.status_code == 200
    assert payload["status"] == "success"
    assert payload["data"] == {
        "collection_name": (
            "knowledge_upload_test"
        ),
        "chunk_count": 12,
        "embedding_provider": (
            "hash_ngram_1_3_256"
        ),
    }


def test_delete_knowledge_document(
    tmp_path: Path,
) -> None:
    """已存在文档应返回删除数量。"""

    document_service = FakeDocumentService()

    application, _ = build_test_app(
        tmp_path,
        document_service,
    )

    with TestClient(application) as client:
        response = client.delete(
            (
                "/api/v1/knowledge/"
                "documents/battery_note"
            )
        )

    payload = response.json()

    assert response.status_code == 200
    assert payload["data"] == {
        "document_id": "battery_note",
        "deleted_chunk_count": 2,
        "deleted": True,
    }


def test_delete_missing_document_returns_404(
    tmp_path: Path,
) -> None:
    """删除不存在文档时应返回404。"""

    document_service = FakeDocumentService()

    application, _ = build_test_app(
        tmp_path,
        document_service,
    )

    with TestClient(application) as client:
        response = client.delete(
            (
                "/api/v1/knowledge/"
                "documents/not_found"
            )
        )

    assert response.status_code == 404
    assert (
        "not_found"
        in response.json()["detail"]
    )