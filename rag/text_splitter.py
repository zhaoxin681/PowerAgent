"""PowerAgent章节感知文本切分器。优先按Markdown标题层级切分，超长章节再做字符窗口二次切分"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass

from rag.exceptions import TextSplitError
from rag.schemas import DocumentChunk, DocumentRecord

# 中间态数据结构，不直接对外暴露
@dataclass(frozen=True)
class SectionBlock:
    """从文档中解析出的章节文本块。"""

    section_path: str
    content: str


class TextSplitter:
    """将DocumentRecord转换为可检索DocumentChunk。"""

    HEADING_PATTERN = re.compile(
        r"^(#{1,6})\s+(.+?)\s*$"
    )  # 匹配Markdown标题的 正则

    def __init__(
        self,
        *,
        chunk_size: int = 600,
        chunk_overlap: int = 80,
    ) -> None:
        """初始化文本切分器。

        Args:
            chunk_size:
                单个知识块允许的最大字符数。
            chunk_overlap:
                超长章节切分时，相邻知识块重复保留的字符数。
        """

        if chunk_size < 100:
            raise ValueError("chunk_size不能小于100")

        if chunk_overlap < 0:
            raise ValueError("chunk_overlap不能为负数")

        if chunk_overlap >= chunk_size:
            raise ValueError(
                "chunk_overlap必须小于chunk_size"
            )

        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    def split_document(
        self,
        document: DocumentRecord,
    ) -> list[DocumentChunk]:
        """切分单份标准文档。"""

        try:
            sections = self._extract_sections(
                document.content
            )  # 将整篇文档按Markdown标题拆成若干章节块

            chunks: list[DocumentChunk] = []
            chunk_index = 0

            for section in sections:
                rendered_text = self._render_section(
                    section
                )  # 将章节路径信息拼进正文里

                for piece in self._split_oversized_text(
                    rendered_text
                ):  # 超过chunk_size的话按字符窗口进一步细分成多片
                    normalized_piece = piece.strip()

                    if not normalized_piece:
                        continue

                    chunk_id = self._build_chunk_id(
                        document_id=document.document_id,
                        section_path=section.section_path,
                        chunk_index=chunk_index,
                        content=normalized_piece,
                    )

                    metadata = dict(document.metadata)
                    metadata["document_version"] = (
                        document.version
                    )

                    chunks.append(
                        DocumentChunk(
                            chunk_id=chunk_id,
                            document_id=document.document_id,
                            title=document.title,
                            content=normalized_piece,
                            chunk_index=chunk_index,
                            source_path=document.source_path,
                            file_type=document.file_type,
                            section_path=section.section_path,
                            page_number=document.page_number,
                            subsystem=document.subsystem,
                            topic=document.topic,
                            metadata=metadata,
                        )
                    )

                    chunk_index += 1

            # 空文档保护
            if not chunks:
                raise TextSplitError(
                    "文档切分后没有生成有效知识块",
                    component="text_splitter",
                    document_id=document.document_id,
                )

            return chunks
        # 统一异常处理
        except TextSplitError:
            raise
        except Exception as exc:
            raise TextSplitError(
                (
                    "文档切分失败："
                    f"{type(exc).__name__}: {exc}"
                ),
                component="text_splitter",
                document_id=document.document_id,
            ) from exc

    # 批量切分
    def split_documents(
        self,
        documents: list[DocumentRecord],
    ) -> list[DocumentChunk]:
        """批量切分标准文档。"""

        chunks: list[DocumentChunk] = []

        for document in documents:
            chunks.extend(
                self.split_document(document)
            )

        return chunks

    # 按标题层级切分章节
    def _extract_sections(
        self,
        content: str,
    ) -> list[SectionBlock]:
        """根据Markdown标题提取章节及章节路径。"""

        lines = content.splitlines()
        heading_stack: list[str] = []   # 记录当前“标题层级路径”的栈
        current_lines: list[str] = []   # 暂存“当前章节”下正在收集的正文行
        current_section_path = ""
        sections: list[SectionBlock] = []

        def flush_current_section() -> None:
            section_content = "\n".join(
                current_lines
            ).strip()

            if section_content:
                sections.append(
                    SectionBlock(
                        section_path=current_section_path,
                        content=section_content,
                    )
                )

            current_lines.clear()

        for line in lines:
            heading_match = self.HEADING_PATTERN.match(
                line.strip()
            )
            # 不是标题行继续收集当前章节正文
            if heading_match is None:
                current_lines.append(line)
                continue
            # 是标题行，将累积的正文打包成一个SectionBlock，存进sections列表，清空crrent_lines，准备收集下一段
            flush_current_section()
            # 解析这一行标题的层级和文字内容
            heading_level = len(
                heading_match.group(1)
            )
            heading_text = (
                heading_match.group(2).strip()
            )

            heading_stack = heading_stack[
                : heading_level - 1
            ]

            heading_stack.append(heading_text)

            current_section_path = " / ".join(
                heading_stack
            )

        flush_current_section()

        if not sections and content.strip():
            sections.append(
                SectionBlock(
                    section_path="",
                    content=content.strip(),
                )
            )

        return sections

    @staticmethod
    def _render_section(
        section: SectionBlock,
    ) -> str:
        """将章节路径与正文合成为用于检索的文本。提升检索质量"""

        if not section.section_path:
            return section.content.strip()

        return (
            f"章节：{section.section_path}\n\n"
            f"{section.content.strip()}"
        )

    def _split_oversized_text(
        self,
        text: str,
    ) -> list[str]:
        """对超长章节使用带重叠的字符窗口切分。"""

        normalized_text = text.strip()

        if len(normalized_text) <= self.chunk_size:
            return [normalized_text]

        pieces: list[str] = []
        start = 0
        text_length = len(normalized_text)

        while start < text_length:
            expected_end = min(
                start + self.chunk_size,
                text_length,
            ) # 应该切断的位置
            # 在理论切点附近找一个更合适的实际切断点，避免把句子从中间硬切断
            end = self._find_safe_breakpoint(
                text=normalized_text,
                start=start,
                expected_end=expected_end,
            )

            piece = normalized_text[start:end].strip()

            if piece:
                pieces.append(piece)

            if end >= text_length:
                break
            # 重叠机制
            next_start = end - self.chunk_overlap

            # 防止异常断点造成死循环。
            if next_start <= start:
                next_start = end

            start = next_start

        return pieces

    # 寻找语义友好的切分点
    def _find_safe_breakpoint(
        self,
        *,
        text: str,
        start: int,
        expected_end: int,
    ) -> int:
        """优先在段落、换行或中文标点处断开。"""

        if expected_end >= len(text):
            return len(text)

        minimum_end = start + int(
            self.chunk_size * 0.6
        )

        separators = (
            "\n\n",
            "。",
            "；",
            "！",
            "？",
            "\n",
        )

        candidate_positions: list[int] = []

        for separator in separators:
            position = text.rfind(
                separator,
                minimum_end,
                expected_end,
            )

            if position == -1:
                continue

            candidate_positions.append(
                position + len(separator)
            )

        if not candidate_positions:
            return expected_end

        return max(candidate_positions)

    # 确定性知识块ID生成
    @staticmethod
    def _build_chunk_id(
        *,
        document_id: str,
        section_path: str,
        chunk_index: int,
        content: str,
    ) -> str:
        """根据来源和内容生成稳定知识块ID。"""

        identity_text = "|".join(
            (
                document_id,
                section_path,
                str(chunk_index),
                content,
            )
        )

        digest = hashlib.sha256(
            identity_text.encode("utf-8")
        ).hexdigest()[:16]

        return f"{document_id}:{digest}"