"""PowerAgent Chroma向量知识库封装。"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import chromadb

from agent_core.schemas import Subsystem
from rag.embeddings import EmbeddingProvider
from rag.exceptions import VectorStoreError
from rag.schemas import (
    DocumentChunk,
    RetrievedChunk,
)


class ChromaVectorStore:
    """保存、更新和查询动力系统知识块。"""

    def __init__(
        self,
        *,
        persist_directory: str | Path,
        embedding_provider: EmbeddingProvider,
        collection_name: str = "poweragent_knowledge",
    ) -> None:
        """初始化持久化Chroma向量库。"""

        self.persist_directory = Path(
            persist_directory
        )
        self.persist_directory.mkdir(
            parents=True,
            exist_ok=True,
        )

        self.embedding_provider = (
            embedding_provider
        )
        self.collection_name = collection_name

        try:
            self.client = chromadb.PersistentClient(
                path=str(self.persist_directory)
            )

            self.collection = (
                self.client.get_or_create_collection(
                    name=self.collection_name,
                    embedding_function=None,   # 不让Chroma自己算向量
                    configuration={
                        "hnsw": {
                            "space": "cosine",
                        }
                    },  # 配置向量索引使用余弦相似度作为距离度量方式
                ) # 如果这个名字集合已存在就直接获取，不存在就自动创建
            )
        except Exception as exc:
            raise VectorStoreError(
                (
                    "初始化Chroma向量库失败："
                    f"{type(exc).__name__}: {exc}"
                ),
                component="chroma_vector_store",
            ) from exc

    def add_chunks(
        self,
        chunks: list[DocumentChunk],
        *,
        batch_size: int = 64,
    ) -> int:
        """写入或更新知识块，返回处理数量。"""

        if not chunks:
            return 0

        if batch_size < 1:
            raise ValueError(
                "batch_size必须大于0"
            )

        processed_count = 0

        try:
            for start in range(
                0,
                len(chunks),
                batch_size,
            ):  # 分批处理
                batch = chunks[
                    start : start + batch_size
                ]

                embedding_texts = [
                    self._build_embedding_text(chunk)
                    for chunk in batch
                ]

                embeddings = (
                    self.embedding_provider
                    .embed_documents(
                        embedding_texts
                    )
                )
                # 存在即更新，不存在即插入
                self.collection.upsert(
                    ids=[
                        chunk.chunk_id
                        for chunk in batch
                    ],
                    embeddings=embeddings,
                    documents=[
                        chunk.content
                        for chunk in batch
                    ],  # 原始文本内容
                    metadatas=[
                        self._build_metadata(chunk)
                        for chunk in batch
                    ],
                )

                processed_count += len(batch)

            return processed_count

        except Exception as exc:
            raise VectorStoreError(
                (
                    "写入知识块失败："
                    f"{type(exc).__name__}: {exc}"
                ),
                component="chroma_vector_store",
            ) from exc

    def search(
        self,
        *,
        query: str,
        top_k: int = 5,
        filters: dict[str, Any] | None = None,
    ) -> list[RetrievedChunk]:
        """使用查询文本检索相似知识块。"""

        if not query.strip():
            raise VectorStoreError(
                "检索问题不能为空",
                component="chroma_vector_store",
            )

        if top_k < 1:
            raise ValueError("top_k必须大于0")

        record_count = self.count()

        if record_count == 0:
            return []

        result_limit = min(
            top_k,
            record_count,
        )

        try:
            query_embedding = (
                self.embedding_provider
                .embed_query(query)
            )

            result = self.collection.query(
                query_embeddings=[
                    query_embedding
                ],
                n_results=result_limit,
                where=filters,  # 可选择的元数据过滤条件
                include=[
                    "documents",
                    "metadatas",
                    "distances",
                ],  # 要求返回的附属信息
            )

            ids = self._first_result_list(
                result.get("ids")
            )
            documents = self._first_result_list(
                result.get("documents")
            )
            metadatas = self._first_result_list(
                result.get("metadatas")
            )
            distances = self._first_result_list(
                result.get("distances")
            )

            # 解析并转换返回结果
            retrieved_chunks: list[
                RetrievedChunk
            ] = []

            for rank, chunk_id in enumerate(
                ids,
                start=1,
            ):
                metadata = (
                    metadatas[rank - 1] or {}
                )
                document_content = (
                    documents[rank - 1] or ""
                )
                distance = float(
                    distances[rank - 1]
                )

                score = self._cosine_distance_to_score(
                    distance
                )

                retrieved_chunks.append(
                    RetrievedChunk(
                        chunk_id=str(chunk_id),
                        document_id=str(
                            metadata["document_id"]
                        ),
                        title=str(
                            metadata["title"]
                        ),
                        content=document_content,
                        score=score,
                        rank=rank,
                        source_path=str(
                            metadata["source_path"]
                        ),
                        section_path=str(
                            metadata.get(
                                "section_path",
                                "",
                            )
                        ),
                        page_number=self._optional_int(
                            metadata.get(
                                "page_number"
                            )
                        ),
                        subsystem=Subsystem(
                            str(
                                metadata.get(
                                    "subsystem",
                                    Subsystem.UNKNOWN.value,
                                )
                            )
                        ),
                        topic=self._optional_string(
                            metadata.get("topic")
                        ),
                        metadata=self._extract_custom_metadata(
                            metadata
                        ),
                    )
                )

            return retrieved_chunks

        except VectorStoreError:
            raise
        except Exception as exc:
            raise VectorStoreError(
                (
                    "查询向量知识库失败："
                    f"{type(exc).__name__}: {exc}"
                ),
                component="chroma_vector_store",
            ) from exc

    def delete_document(
        self,
        document_id: str,
    ) -> int:
        """删除指定文档对应的全部知识块。"""

        normalized_id = document_id.strip()

        if not normalized_id:
            raise ValueError(
                "document_id不能为空"
            )

        try:
            matched = self.collection.get(
                where={
                    "document_id": normalized_id
                },
                include=[],
            )

            matched_ids = list(
                matched.get("ids") or []
            )

            if not matched_ids:
                return 0

            self.collection.delete(
                ids=matched_ids
            )

            return len(matched_ids)

        except Exception as exc:
            raise VectorStoreError(
                (
                    "删除文档知识块失败："
                    f"{type(exc).__name__}: {exc}"
                ),
                component="chroma_vector_store",
                document_id=normalized_id,
            ) from exc

    def count(self) -> int:
        """返回查询当前知识块数量。"""

        try:
            return int(self.collection.count())
        except Exception as exc:
            raise VectorStoreError(
                (
                    "读取向量库数量失败："
                    f"{type(exc).__name__}: {exc}"
                ),
                component="chroma_vector_store",
            ) from exc

    def reset(self) -> None:
        """删除并重新创建当前知识集合。"""

        try:
            try:
                self.client.delete_collection(
                    name=self.collection_name
                )
            except Exception:
                # 集合不存在时允许继续重建。
                pass

            self.collection = (
                self.client.get_or_create_collection(
                    name=self.collection_name,
                    embedding_function=None,
                    configuration={
                        "hnsw": {
                            "space": "cosine",
                        }
                    },
                )
            )
        except Exception as exc:
            raise VectorStoreError(
                (
                    "重置向量知识库失败："
                    f"{type(exc).__name__}: {exc}"
                ),
                component="chroma_vector_store",
            ) from exc

    @staticmethod
    def _build_embedding_text(
        chunk: DocumentChunk,
    ) -> str:
        """组合标题、章节和正文作为Embedding输入。构造成一段更丰富的带上下文提示的文本再做embedding"""

        text_parts = [
            f"标题：{chunk.title}",
        ]

        if chunk.section_path:
            text_parts.append(
                f"章节：{chunk.section_path}"
            )

        if chunk.topic:
            text_parts.append(
                f"主题：{chunk.topic}"
            )

        text_parts.append(
            f"正文：{chunk.content}"
        )

        return "\n".join(text_parts)

    # @staticmethod
    # def _build_metadata(
    #     chunk: DocumentChunk,
    # ) -> dict[str, str | int | float | bool]:
    def _build_metadata(
        self,
        chunk: DocumentChunk,
    ) -> dict[str, str | int | float | bool]:
        """将知识块元数据转换为Chroma支持的简单类型。
        Chroma元数据字段不支持None或嵌套结构，与schema文件中定义的MetadataValue略有差异，
        故要做一次清洗转换"""

        metadata: dict[
            str,
            str | int | float | bool
        ] = {}

        # 过滤掉None
        for key, value in chunk.metadata.items():
            if value is None:
                continue

            if isinstance(
                value,
                (str, int, float, bool),
            ):
                metadata[key] = value

        # 保留字段覆盖自定义元数据中的同名键。
        metadata.update(
            {
                "document_id": chunk.document_id,
                "title": chunk.title,
                "chunk_index": chunk.chunk_index,
                "source_path": chunk.source_path,
                "file_type": chunk.file_type.value,
                "section_path": chunk.section_path,
                "subsystem": chunk.subsystem.value,
                "embedding_provider": (self.embedding_provider.name),
            }
        )

        if chunk.topic is not None:
            metadata["topic"] = chunk.topic

        if chunk.page_number is not None:
            metadata["page_number"] = (
                chunk.page_number
            )

        return metadata

    @staticmethod
    def _cosine_distance_to_score(
        distance: float,
    ) -> float:
        """将Chroma余弦距离转换为0到1的相关性分数。"""

        score = 1.0 - distance

        return max(
            0.0,
            min(1.0, score),
        )

    @staticmethod
    def _first_result_list(
        value: Any,
    ) -> list[Any]:
        """读取Chroma批量查询结果中的第一组数据。"""

        if not value:
            return []

        first_value = value[0]

        if first_value is None:
            return []

        return list(first_value)

    @staticmethod
    def _optional_int(
        value: Any,
    ) -> int | None:
        if value is None:
            return None

        return int(value)

    @staticmethod
    def _optional_string(
        value: Any,
    ) -> str | None:
        if value is None:
            return None

        normalized_value = str(value).strip()

        return normalized_value or None

    @staticmethod
    def _extract_custom_metadata(
        metadata: dict[str, Any],
    ) -> dict[str, str | int | float | bool | None]:
        """移除已映射到RetrievedChunk字段中的保留元数据。只保留真正属于用户自定义的额外元数据"""

        reserved_keys = {
            "document_id",
            "title",
            "chunk_index",
            "source_path",
            "file_type",
            "section_path",
            "subsystem",
            "topic",
            "page_number",
            "embedding_provider",
        }

        return {
            key: value
            for key, value in metadata.items()
            if key not in reserved_keys
        }