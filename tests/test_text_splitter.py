"""TextSplitter核心功能测试。"""
"""
两组行为：章节路径与元数据的正确传递，以及超长文本切分的长度控制与ID稳定性。
"""

from agent_core.schemas import Subsystem
from rag.schemas import (
    DocumentRecord,
    DocumentType,
)
from rag.text_splitter import TextSplitter


def make_document(
    content: str,
) -> DocumentRecord:
    """构造文本切分测试文档。"""

    return DocumentRecord(
        document_id="battery_test",
        title="动力电池测试文档",
        content=content,
        source_path="docs/battery_test.md",
        file_type=DocumentType.MARKDOWN,
        subsystem=Subsystem.BATTERY,
        topic="voltage",
        metadata={
            "source_type": "test",
        },
    )

# 测试1
def test_splitter_preserves_section_metadata() -> None:
    """标题章节和原始元数据应传递到Chunk。"""

    document = make_document(
        """# 定义

单体电压不一致是不同单体电压响应存在差异。

# 可能原因

可能与容量、内阻和连接状态有关。
"""
    )

    splitter = TextSplitter(
        chunk_size=200,
        chunk_overlap=20,
    )

    chunks = splitter.split_document(document)

    assert len(chunks) == 2
    assert chunks[0].section_path == "定义"
    assert chunks[1].section_path == "可能原因"
    assert chunks[0].subsystem == Subsystem.BATTERY
    assert chunks[0].metadata["source_type"] == "test"
    assert chunks[0].chunk_index == 0
    assert chunks[1].chunk_index == 1

# 测试2
def test_splitter_limits_length_and_keeps_stable_ids() -> None:
    """超长章节应被切分，相同输入应产生稳定ID。"""

    long_content = (
        "# 验证步骤\n\n"
        + "检查单体电压、电流和温度数据。"
        * 30
    )

    document = make_document(long_content)

    splitter = TextSplitter(
        chunk_size=150,
        chunk_overlap=30,
    )

    first_chunks = splitter.split_document(
        document
    )
    second_chunks = splitter.split_document(
        document
    )

    assert len(first_chunks) > 1

    assert all(
        len(chunk.content) <= 150
        for chunk in first_chunks
    )

    assert [
        chunk.chunk_id
        for chunk in first_chunks
    ] == [
        chunk.chunk_id
        for chunk in second_chunks
    ]