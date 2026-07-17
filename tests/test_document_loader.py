"""DocumentLoader核心行为测试。"""

from pathlib import Path

import pytest

from agent_core.schemas import Subsystem
from rag.document_loader import DocumentLoader
from rag.exceptions import (
    EmptyDocumentError,
    UnsupportedDocumentTypeError,
)
from rag.schemas import DocumentType

# 完整正向路径
def test_load_markdown_with_front_matter(
    tmp_path: Path,
) -> None:
    """Markdown正文和元数据应转换为DocumentRecord。"""

    file_path = tmp_path / "battery_voltage.md"
    file_path.write_text(
        """---
document_id: battery_voltage
title: 动力电池电压知识
subsystem: battery
topic: voltage
version: "1.0"
source_type: test
---

# 定义

这是测试正文。
""",
        encoding="utf-8",
    )

    loader = DocumentLoader(source_root=tmp_path)
    documents = loader.load_file(file_path)

    assert len(documents) == 1

    document = documents[0]

    assert document.document_id == "battery_voltage"
    assert document.title == "动力电池电压知识"
    assert document.subsystem == Subsystem.BATTERY
    assert document.topic == "voltage"
    assert document.file_type == DocumentType.MARKDOWN
    assert document.source_path == "battery_voltage.md"
    assert document.metadata["source_type"] == "test"
    assert "这是测试正文" in document.content


def test_load_text_uses_default_metadata(
    tmp_path: Path,
) -> None:
    """TXT应使用文件名生成默认文档信息。"""

    file_path = tmp_path / "charging_notes.txt"
    file_path.write_text(
        "充电过程中需要检查电压、电流和温度约束。",
        encoding="utf-8",
    )

    loader = DocumentLoader(source_root=tmp_path)
    document = loader.load_file(file_path)[0]

    assert document.document_id == "charging_notes"
    assert document.title == "charging_notes"
    assert document.file_type == DocumentType.TEXT
    assert document.subsystem == Subsystem.UNKNOWN
    assert document.topic is None


def test_loader_rejects_unsupported_file_type(
    tmp_path: Path,
) -> None:
    """不支持的文件类型应返回明确异常。"""

    file_path = tmp_path / "data.csv"
    file_path.write_text(
        "voltage,current",
        encoding="utf-8",
    )

    loader = DocumentLoader(source_root=tmp_path)

    with pytest.raises(UnsupportedDocumentTypeError):
        loader.load_file(file_path)


def test_loader_rejects_empty_document(
    tmp_path: Path,
) -> None:
    """空文档不得进入后续知识库。"""

    file_path = tmp_path / "empty.md"
    file_path.write_text(
        "   \n",
        encoding="utf-8",
    )

    loader = DocumentLoader(source_root=tmp_path)

    with pytest.raises(EmptyDocumentError):
        loader.load_file(file_path)