"""PowerAgent API健康检查核心测试。"""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.config import (
    AppSettings,
    RuntimeEnvironment,
)
from app.main import create_app
from app.schemas import DependencyCheckStatus
from typing import Any, cast

from app.dependencies import (
    ApplicationServices,
)

def build_stub_services(
    _: AppSettings,
) -> ApplicationServices:
    """构造健康检查使用的空服务容器。"""

    return cast(
        ApplicationServices,
        object(),
    )

# 测试专用配置构造器
def make_test_settings(
    log_dir: Path,
) -> AppSettings:
    """构造不依赖本地.env的测试配置。"""

    return AppSettings(
        service_name="PowerAgent Test",
        service_version="0.1.0-test",
        environment=RuntimeEnvironment.TEST,
        api_prefix="/api/v1",
        host="127.0.0.1",
        port=8000,
        log_level="INFO",
        log_dir=log_dir,
    )


def test_live_health_check_returns_ok(
    tmp_path: Path,
) -> None:
    """存活检查应返回服务基本信息。"""

    application = create_app(
        make_test_settings(
            tmp_path / "logs"
        ),
        service_builder=build_stub_services,
    )  # 独立临时目录

    with TestClient(application) as client:
        response = client.get(
            "/health/live"
        ) # 用with为了让lifespan生命周期真实执行一遍

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "PowerAgent Test",
        "version": "0.1.0-test",
    }

# 验证正常情况下的就绪探针行为
def test_ready_health_check_returns_ready(
    tmp_path: Path,
) -> None:
    """启动完成后全部检查应为ok。"""

    application = create_app(
        make_test_settings(
            tmp_path / "logs"
        ),
        service_builder=build_stub_services,
    )

    with TestClient(application) as client:
        response = client.get(
            "/health/ready"
        )

    payload = response.json()

    assert response.status_code == 200
    assert payload["status"] == "ready"
    assert all(
        value == "ok"
        for value
        in payload["checks"].values()
    )


def test_ready_health_check_returns_503(
    tmp_path: Path,
) -> None:
    """任一关键检查失败时服务应标记未就绪。"""

    application = create_app(
        make_test_settings(
            tmp_path / "logs"
        ),
        service_builder=build_stub_services,
    )

    with TestClient(application) as client:
        application.state.readiness_checks[
            "application"
        ] = DependencyCheckStatus.FAILED

        response = client.get(
            "/health/ready"
        )

    assert response.status_code == 503
    assert (
        response.json()["status"]
        == "not_ready"
    )
    assert (
        response.json()["checks"][
            "application"
        ]
        == "failed"
    )


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
        )