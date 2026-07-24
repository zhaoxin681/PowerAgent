"""PowerAgent API配置模型核心测试。"""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from app.config import AppSettings


def test_settings_reject_invalid_api_prefix(
    tmp_path: Path,
) -> None:
    """API前缀必须以斜杠开头。"""

    with pytest.raises(
        ValidationError,
        match="api_prefix必须以/开头",
    ):
        AppSettings(
            api_prefix="api/v1",
            log_dir=tmp_path / "logs",
            chroma_path=tmp_path / "chroma",
            upload_temp_dir=(
                tmp_path / "uploads" / "tmp"
            ),
        )