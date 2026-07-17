"""PowerAgent Embedding统一接口与实现。"""

from __future__ import annotations

import hashlib
import math
import re
from typing import Protocol, runtime_checkable

from rag.exceptions import EmbeddingError


@runtime_checkable
class EmbeddingProvider(Protocol):
    """文档和查询向量化的统一协议。定义了embedding提供者必须具备的最小能力集"""

    @property
    def name(self) -> str:
        """返回Embedding实现名称。"""

    def embed_documents(
        self,
        texts: list[str],
    ) -> list[list[float]]:
        """批量生成文档向量。"""

    def embed_query(
        self,
        text: str,
    ) -> list[float]:
        """生成单条查询向量。"""


class HashEmbeddingProvider:
    """用于测试和离线验证的确定性哈希Embedding。

    该实现主要根据中文字符和字符片段的重合程度产生向量，
    不具备真正的深层语义理解能力。
    """

    def __init__(
        self,
        *,
        dimension: int = 256,
        min_ngram: int = 1,  # n-gram切分字符窗口范围
        max_ngram: int = 3,
    ) -> None:
        if dimension < 32:
            raise ValueError(
                "Embedding维度不能小于32"
            )

        if min_ngram < 1:
            raise ValueError(
                "min_ngram不能小于1"
            )

        if max_ngram < min_ngram:
            raise ValueError(
                "max_ngram不能小于min_ngram"
            )

        self.dimension = dimension
        self.min_ngram = min_ngram
        self.max_ngram = max_ngram

    # 可以标记向量使用什么配置生成的
    @property
    def name(self) -> str:
        return (
            f"hash_ngram_"
            f"{self.min_ngram}_"
            f"{self.max_ngram}_"
            f"{self.dimension}"
        )

    def embed_documents(
        self,
        texts: list[str],
    ) -> list[list[float]]:
        if not texts:
            return []

        return [
            self._embed_text(text)
            for text in texts
        ]

    def embed_query(
        self,
        text: str,
    ) -> list[float]:
        return self._embed_text(text)

    # 核心哈希向量生成逻辑，基于字符表层重合度的伪语义相似度衡量
    def _embed_text(
        self,
        text: str,
    ) -> list[float]:
        normalized_text = self._normalize_text(text)

        if not normalized_text:
            raise EmbeddingError(
                "不能对空文本生成Embedding",
                component="hash_embedding",
            )

        vector = [0.0] * self.dimension

        for token in self._generate_ngrams(
            normalized_text
        ):
            digest = hashlib.blake2b(
                token.encode("utf-8"),
                digest_size=16,
            ).digest()  # 对每个n-gram token做哈希投影

            index = int.from_bytes(
                digest[:8],
                byteorder="big",
            ) % self.dimension

            sign = (
                1.0
                if digest[8] % 2 == 0
                else -1.0
            )

            vector[index] += sign

        norm = math.sqrt(
            sum(value * value for value in vector)
        )

        if norm == 0.0:
            raise EmbeddingError(
                "Embedding向量归一化失败",
                component="hash_embedding",
            )

        return [
            value / norm
            for value in vector
        ]

    # 滑动窗口生成字符n-gram
    def _generate_ngrams(
        self,
        text: str,
    ) -> list[str]:
        tokens: list[str] = []

        for ngram_size in range(
            self.min_ngram,
            self.max_ngram + 1,
        ):
            if len(text) < ngram_size:
                continue

            for index in range(
                len(text) - ngram_size + 1
            ):
                tokens.append(
                    text[index : index + ngram_size]
                )

        return tokens

    @staticmethod
    def _normalize_text(
        text: str,
    ) -> str:
        return re.sub(
            r"\s+",
            "",
            text.strip().lower(),
        )


# 封装真实向量库的默认模型
class ChromaDefaultEmbeddingProvider:
    """封装Chroma默认本地Embedding函数。具备真实的语义理解能力"""

    def __init__(self) -> None:
        try:
            from chromadb.utils.embedding_functions import (
                DefaultEmbeddingFunction,
            )

            self._embedding_function = (
                DefaultEmbeddingFunction()
            )
        except Exception as exc:
            raise EmbeddingError(
                (
                    "初始化Chroma默认Embedding失败："
                    f"{type(exc).__name__}: {exc}"
                ),
                component="chroma_default_embedding",
            ) from exc

    @property
    def name(self) -> str:
        return "chroma_default_embedding"

    def embed_documents(
        self,
        texts: list[str],
    ) -> list[list[float]]:
        if not texts:
            return []

        return self._embed(texts)

    def embed_query(
        self,
        text: str,
    ) -> list[float]:
        if not text.strip():
            raise EmbeddingError(
                "查询文本不能为空",
                component="chroma_default_embedding",
            )

        return self._embed([text])[0]

    def _embed(
        self,
        texts: list[str],
    ) -> list[list[float]]:
        try:
            embeddings = self._embedding_function(
                texts
            )

            return [
                [float(value) for value in embedding]
                for embedding in embeddings
            ]
        except Exception as exc:
            raise EmbeddingError(
                (
                    "Chroma默认Embedding执行失败："
                    f"{type(exc).__name__}: {exc}"
                ),
                component="chroma_default_embedding",
            ) from exc 