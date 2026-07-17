"""PowerAgent动力系统知识文档加载器。
将磁盘上文件转换成schema里定义的标准化DocumentRecord对象。
"""

from __future__ import annotations

import hashlib
import re
from pathlib import Path

from pydantic import ValidationError
from pypdf import PdfReader

from agent_core.schemas import Subsystem
from rag.exceptions import (
    DocumentLoadError,
    EmptyDocumentError,
    RAGError,
    UnsupportedDocumentTypeError,
)
from rag.schemas import (
    DocumentRecord,
    DocumentType,
    MetadataValue,
)


class DocumentLoader:
    """将Markdown、TXT和文本型PDF转换为DocumentRecord。"""

    SUPPORTED_FILE_TYPES: dict[str, DocumentType] = {
        ".md": DocumentType.MARKDOWN,
        ".txt": DocumentType.TEXT,
        ".pdf": DocumentType.PDF,
    }  # 后续可增加支持类型，只需要加一行而不用改判断逻辑的分支结构

    def __init__(
        self,
        *,
        source_root: str | Path | None = None,
        encoding: str = "utf-8-sig",
    ) -> None:
        """初始化文档加载器。

        Args:
            source_root:
                用于生成相对source_path的根目录。
                未指定时使用当前工作目录。
            encoding:
                Markdown和TXT的读取编码。
        """

        self.source_root = (
            Path(source_root).resolve()
            if source_root is not None
            else Path.cwd().resolve()
        )
        self.encoding = encoding

    # 单文件加载入口
    def load_file(
        self,
        file_path: str | Path,
    ) -> list[DocumentRecord]:
        """加载单个文件并返回标准文档对象列表。"""

        path = Path(file_path)

        if not path.exists():
            raise DocumentLoadError(
                f"文件不存在：{path}",
                component="document_loader",
            )

        if not path.is_file():
            raise DocumentLoadError(
                f"目标路径不是文件：{path}",
                component="document_loader",
            )

        suffix = path.suffix.lower()

        if suffix not in self.SUPPORTED_FILE_TYPES:
            raise UnsupportedDocumentTypeError(
                f"当前不支持文件类型：{suffix or '无扩展名'}",
                component="document_loader",
            )

        try:
            if suffix == ".md":
                return [self._load_markdown(path)]

            if suffix == ".txt":
                return [self._load_text(path)]

            if suffix == ".pdf":
                return self._load_pdf(path)

        except RAGError:
            raise
        except ValidationError as exc:
            raise DocumentLoadError(
                f"文档元数据或内容未通过数据模型校验：{exc}",
                component="document_loader",
            ) from exc
        except (OSError, UnicodeError) as exc:
            raise DocumentLoadError(
                f"读取文档失败：{type(exc).__name__}: {exc}",
                component="document_loader",
            ) from exc
        except Exception as exc:
            raise DocumentLoadError(
                f"解析文档失败：{type(exc).__name__}: {exc}",
                component="document_loader",
            ) from exc

        raise UnsupportedDocumentTypeError(
            f"当前不支持文件类型：{suffix}",
            component="document_loader",
        )
    # 批量加载目录
    def load_directory(
        self,
        directory: str | Path,
        *,
        recursive: bool = True,
    ) -> list[DocumentRecord]:
        """批量加载目录中的受支持文件。

        不支持的文件不会被扫描。
        检测到重复document_id时直接抛出异常。
        """

        directory_path = Path(directory)

        if not directory_path.exists():
            raise DocumentLoadError(
                f"目录不存在：{directory_path}",
                component="document_loader",
            )

        if not directory_path.is_dir():
            raise DocumentLoadError(
                f"目标路径不是目录：{directory_path}",
                component="document_loader",
            )

        iterator = (
            directory_path.rglob("*")
            if recursive
            else directory_path.iterdir()
        ) # 递归遍历所有子目录下的文件

        supported_files = sorted(
            path
            for path in iterator
            if path.is_file()
            and path.suffix.lower() in self.SUPPORTED_FILE_TYPES
        )

        documents: list[DocumentRecord] = []
        document_sources: dict[str, str] = {}

        for path in supported_files:
            loaded_documents = self.load_file(path)

            for document in loaded_documents:
                previous_source = document_sources.get(
                    document.document_id
                )

                if previous_source is not None:
                    raise DocumentLoadError(
                        (
                            f"发现重复document_id="
                            f"{document.document_id}；"
                            f"来源分别为{previous_source}和"
                            f"{document.source_path}"
                        ),
                        component="document_loader",
                        document_id=document.document_id,
                    )

                document_sources[document.document_id] = (
                    document.source_path
                )
                documents.append(document)

        return documents

    def _load_markdown(self, path: Path) -> DocumentRecord:
        """加载Markdown文档及其头部元数据。"""

        raw_text = path.read_text(encoding=self.encoding)
        front_matter, content = self._parse_front_matter(
            raw_text,
            path=path,
        )

        if not content:
            raise EmptyDocumentError(
                "Markdown文档没有有效正文",
                component="document_loader",
                document_id=self._fallback_document_id(path),
            )

        document_id_value = front_matter.pop(
            "document_id",
            self._fallback_document_id(path),
        )
        title_value = front_matter.pop("title", path.stem)
        subsystem_value = front_matter.pop(
            "subsystem",
            Subsystem.UNKNOWN.value,
        )
        topic_value = front_matter.pop("topic", None)
        version_value = front_matter.pop("version", "1.0")

        document_id = str(document_id_value).strip()
        title = str(title_value).strip() or path.stem
        version = str(version_value).strip() or "1.0"

        if subsystem_value is None:
            subsystem_value = Subsystem.UNKNOWN.value

        topic = self._optional_text(topic_value)

        return DocumentRecord(
            document_id=document_id,
            title=title,
            content=content,
            source_path=self._build_source_path(path),
            file_type=DocumentType.MARKDOWN,
            subsystem=subsystem_value,
            topic=topic,
            version=version,
            metadata=front_matter,
        )

    def _load_text(self, path: Path) -> DocumentRecord:
        """加载纯文本文件。"""

        content = path.read_text(encoding=self.encoding).strip()
        document_id = self._fallback_document_id(path)

        if not content:
            raise EmptyDocumentError(
                "TXT文档没有有效正文",
                component="document_loader",
                document_id=document_id,
            )

        return DocumentRecord(
            document_id=document_id,
            title=path.stem,
            content=content,
            source_path=self._build_source_path(path),
            file_type=DocumentType.TEXT,
            subsystem=Subsystem.UNKNOWN,
            topic=None,
            version="1.0",
            metadata={},
        )

    def _load_pdf(self, path: Path) -> list[DocumentRecord]:
        """按有效文本页加载PDF文档。按页拆分加载"""

        reader = PdfReader(str(path), strict=False)
        source_path = self._build_source_path(path)
        parent_document_id = self._fallback_document_id(path)

        pdf_metadata = reader.metadata
        metadata_title = (
            getattr(pdf_metadata, "title", None)
            if pdf_metadata is not None
            else None
        )

        title = (
            str(metadata_title).strip()
            if metadata_title
            else path.stem
        )

        total_pages = len(reader.pages)
        documents: list[DocumentRecord] = []

        for page_number, page in enumerate(
            reader.pages,
            start=1,
        ):
            page_text = (page.extract_text() or "").strip()

            if not page_text:
                continue

            page_document_id = (
                f"{parent_document_id}_p{page_number:04d}"
            )

            documents.append(
                DocumentRecord(
                    document_id=page_document_id,
                    title=title,
                    content=page_text,
                    source_path=source_path,
                    file_type=DocumentType.PDF,
                    subsystem=Subsystem.UNKNOWN,
                    topic=None,
                    version="1.0",
                    page_number=page_number,
                    metadata={
                        "parent_document_id": parent_document_id,
                        "total_pages": total_pages,
                    },
                )
            )

        if not documents:
            raise EmptyDocumentError(
                (
                    "PDF没有可提取的文本内容；"
                    "当前版本不支持扫描图片OCR"
                ),
                component="document_loader",
                document_id=parent_document_id,
            )

        return documents

    # 手写轻量YAML解析器
    def _parse_front_matter(
        self,
        raw_text: str,
        *,
        path: Path,
    ) -> tuple[dict[str, MetadataValue], str]:
        """解析仅包含简单标量值的Markdown头部元数据。"""

        lines = raw_text.splitlines()

        if not lines or lines[0].strip() != "---":
            return {}, raw_text.strip()

        closing_index: int | None = None

        for index in range(1, len(lines)):
            if lines[index].strip() == "---":
                closing_index = index
                break

        if closing_index is None:
            raise DocumentLoadError(
                f"Markdown头部元数据未闭合：{path.name}",
                component="document_loader",
            )

        metadata: dict[str, MetadataValue] = {}

        for line in lines[1:closing_index]:
            stripped_line = line.strip()

            if not stripped_line or stripped_line.startswith("#"):
                continue

            if ":" not in stripped_line:
                raise DocumentLoadError(
                    (
                        "Markdown头部元数据格式错误："
                        f"{stripped_line}"
                    ),
                    component="document_loader",
                )

            key, raw_value = stripped_line.split(":", maxsplit=1)
            normalized_key = key.strip()

            if not normalized_key:
                raise DocumentLoadError(
                    "Markdown头部元数据包含空字段名",
                    component="document_loader",
                )

            metadata[normalized_key] = self._parse_scalar(
                raw_value.strip()
            )

        content = "\n".join(
            lines[closing_index + 1 :]
        ).strip()

        return metadata, content

    # 标量类型推断
    @staticmethod
    def _parse_scalar(value: str) -> MetadataValue:
        """解析简单的字符串、布尔值、数字和空值。"""

        if not value:
            return ""

        if (
            len(value) >= 2
            and value[0] == value[-1]
            and value[0] in {'"', "'"}
        ):
            return value[1:-1]

        lower_value = value.lower()

        if lower_value in {"null", "none", "~"}:
            return None

        if lower_value == "true":
            return True

        if lower_value == "false":
            return False

        if re.fullmatch(r"-?\d+", value):
            return int(value)

        if re.fullmatch(
            r"-?(?:\d+\.\d*|\d*\.\d+)",
            value,
        ):
            return float(value)

        return value

    def _build_source_path(self, path: Path) -> str:
        """生成不暴露无关绝对目录的可追溯来源路径。"""

        resolved_path = path.resolve()

        try:
            return resolved_path.relative_to(
                self.source_root
            ).as_posix()
        except ValueError:
            return path.name

    def _fallback_document_id(self, path: Path) -> str:
        """根据文件名生成稳定的备用document_id。"""

        normalized_stem = re.sub(
            r"[^a-z0-9_-]+",
            "_",
            path.stem.lower(),
        ).strip("_-")

        if normalized_stem:
            return normalized_stem

        source_digest = hashlib.sha256(
            self._build_source_path(path).encode("utf-8")
        ).hexdigest()[:12]

        return f"document_{source_digest}"

    # 可选字符串规范化
    @staticmethod
    def _optional_text(
        value: MetadataValue,
    ) -> str | None:
        """将可选元数据转换为非空字符串或None。"""

        if value is None:
            return None

        normalized_value = str(value).strip()

        return normalized_value or None