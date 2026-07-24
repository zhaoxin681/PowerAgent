"""PowerAgent API演示客户端核心测试。"""

from __future__ import annotations

import json
from pathlib import Path

import httpx

from examples.api_client_demo import (
    PowerAgentApiClient,
    build_parser,
    execute_command,
)


def build_client(
    handler,
) -> PowerAgentApiClient:
    """创建使用MockTransport的客户端。"""

    return PowerAgentApiClient(
        base_url="http://poweragent.test",
        timeout_seconds=5.0,
        transport=httpx.MockTransport(
            handler
        ),
    )


def test_workflow_command_sends_expected_json(
) -> None:
    """通用工作流命令应发送完整请求体。"""

    def handler(
        request: httpx.Request,
    ) -> httpx.Response:
        assert request.method == "POST"

        assert (
            request.url.path
            == "/api/v1/workflows/analyze"
        )

        payload = json.loads(
            request.read().decode("utf-8")
        )

        assert payload == {
            "raw_input": (
                "分析动力电池单体压差扩大"
            ),
            "trace_id": (
                "trace_client_workflow"
            ),
            "max_retries": 3,
            "skill_inputs": None,
            "include_trace": True,
            "include_intermediate_results": (
                False
            ),
        }

        return httpx.Response(
            status_code=200,
            headers={
                "X-Request-ID": (
                    "request-client-workflow"
                ),
            },
            json={
                "request_id": (
                    "request-client-workflow"
                ),
                "trace_id": (
                    "trace_client_workflow"
                ),
                "status": "success",
                "data": {
                    "route": (
                        "fault_diagnosis"
                    )
                },
                "error": None,
            },
        )

    parser = build_parser()

    args = parser.parse_args(
        [
            "workflow-analyze",
            "--input",
            "分析动力电池单体压差扩大",
            "--trace-id",
            "trace_client_workflow",
            "--max-retries",
            "3",
            "--include-trace",
        ]
    )

    with build_client(handler) as client:
        result = execute_command(
            client,
            args,
        )

    assert result.status_code == 200

    assert (
        result.request_id
        == "request-client-workflow"
    )

    assert (
        result.trace_id
        == "trace_client_workflow"
    )


def test_document_upload_sends_multipart(
    tmp_path: Path,
) -> None:
    """上传命令应发送文件和表单字段。"""

    document_path = (
        tmp_path / "battery_note.txt"
    )

    document_path.write_text(
        "动力电池知识文档",
        encoding="utf-8",
    )

    def handler(
        request: httpx.Request,
    ) -> httpx.Response:
        assert request.method == "POST"

        assert (
            request.url.path
            == "/api/v1/knowledge/documents"
        )

        content_type = (
            request.headers[
                "Content-Type"
            ]
        )

        assert (
            content_type.startswith(
                "multipart/form-data;"
            )
        )

        content = request.read()

        assert (
            b"battery_note.txt"
            in content
        )

        assert (
            "动力电池知识文档"
            .encode("utf-8")
            in content
        )

        assert b"battery" in content
        assert b"true" in content

        return httpx.Response(
            status_code=200,
            headers={
                "X-Request-ID": (
                    "request-document-upload"
                ),
            },
            json={
                "request_id": (
                    "request-document-upload"
                ),
                "trace_id": None,
                "status": "success",
                "data": {
                    "document_id": (
                        "battery_note"
                    )
                },
                "error": None,
            },
        )

    parser = build_parser()

    args = parser.parse_args(
        [
            "document-upload",
            "--file",
            str(document_path),
            "--topic",
            "电池一致性",
            "--subsystem",
            "battery",
            "--overwrite",
        ]
    )

    with build_client(handler) as client:
        result = execute_command(
            client,
            args,
        )

    assert result.status_code == 200

    assert (
        result.request_id
        == "request-document-upload"
    )

    assert result.trace_id is None


def test_rnd_command_loads_json_inputs(
    tmp_path: Path,
) -> None:
    """研发命令应加载运行条件和Skill输入。"""

    operating_conditions_path = (
        tmp_path
        / "operating_conditions.json"
    )

    operating_conditions_path.write_text(
        json.dumps(
            [
                {
                    "name": "SOC",
                    "value": "80以上",
                    "unit": "%",
                }
            ],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    skill_inputs_path = (
        tmp_path / "skill_inputs.json"
    )

    skill_inputs_path.write_text(
        json.dumps(
            {
                "battery_analysis": {
                    "cell_voltages_v": [
                        3.55,
                        3.62,
                    ]
                }
            }
        ),
        encoding="utf-8",
    )

    def handler(
        request: httpx.Request,
    ) -> httpx.Response:
        assert request.method == "POST"

        assert (
            request.url.path
            == "/api/v1/rnd/analyze"
        )

        payload = json.loads(
            request.read().decode("utf-8")
        )

        assert (
            payload["raw_input"]
            == "分析高SOC快充限流"
        )

        assert (
            payload["affected_scope"]
            == [
                "部分车辆",
                "高SOC快充工况",
            ]
        )

        assert (
            payload["available_data"]
            == [
                "充电电流",
                "单体电压",
            ]
        )

        assert (
            payload[
                "operating_conditions"
            ][0]["name"]
            == "SOC"
        )

        assert (
            payload[
                "requested_deliverables"
            ]
            == [
                "候选根因",
                "验证实验",
            ]
        )

        assert (
            payload["skill_inputs"][
                "battery_analysis"
            ]["cell_voltages_v"]
            == [
                3.55,
                3.62,
            ]
        )

        assert payload["max_retries"] == 2

        return httpx.Response(
            status_code=200,
            headers={
                "X-Request-ID": (
                    "request-rnd-client"
                ),
            },
            json={
                "request_id": (
                    "request-rnd-client"
                ),
                "trace_id": (
                    "trace-rnd-client"
                ),
                "status": "success",
                "data": {
                    "trace_id": (
                        "trace-rnd-client"
                    ),
                    "status": "completed",
                },
                "error": None,
            },
        )

    parser = build_parser()

    args = parser.parse_args(
        [
            "rnd-analyze",
            "--input",
            "分析高SOC快充限流",
            "--affected-scope",
            "部分车辆",
            "--affected-scope",
            "高SOC快充工况",
            "--available-data",
            "充电电流",
            "--available-data",
            "单体电压",
            "--operating-conditions-json",
            str(
                operating_conditions_path
            ),
            "--deliverable",
            "候选根因",
            "--deliverable",
            "验证实验",
            "--skill-inputs-json",
            str(skill_inputs_path),
        ]
    )

    with build_client(handler) as client:
        result = execute_command(
            client,
            args,
        )

    assert result.status_code == 200

    assert (
        result.request_id
        == "request-rnd-client"
    )

    assert (
        result.trace_id
        == "trace-rnd-client"
    )