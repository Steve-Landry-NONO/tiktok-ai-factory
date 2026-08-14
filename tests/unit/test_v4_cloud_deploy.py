from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_render_blueprint_declares_secrets_without_values() -> None:
    text = (ROOT / "render.yaml").read_text(encoding="utf-8")

    assert "runtime: docker" in text
    assert "healthCheckPath: /healthz" in text
    assert "autoDeployTrigger: checksPass" in text
    assert "region: frankfurt" in text
    assert "FACTORY_DURABLE_STORAGE_REQUIRED" in text
    assert "FACTORY_MEDIA_BUCKET" in text
    assert "value: tiktok-media" in text

    for secret_name in (
        "FACTORY_API_TOKEN",
        "GROQ_API_KEY",
        "RUNWAY_API_KEY",
        "SUPABASE_SECRET_KEY",
    ):
        declaration = f"- key: {secret_name}\n        sync: false"
        assert declaration in text

    assert "sklzxgdfbclghwfoataq.supabase.co" in text


def test_n8n_cloud_workflow_is_authenticated_and_async_at_intake() -> None:
    workflow = json.loads(
        (ROOT / "n8n" / "00_factory_orchestrator_v4_cloud.json").read_text(
            encoding="utf-8"
        )
    )
    nodes = {node["name"]: node for node in workflow["nodes"]}

    webhook = nodes["V4 Cloud Intake Webhook"]
    assert webhook["parameters"]["authentication"] == "headerAuth"
    assert webhook["parameters"]["responseMode"] == "onReceived"

    request = nodes["Run Factory V4 Cloud"]
    params = request["parameters"]
    assert params["authentication"] == "genericCredentialType"
    assert params["genericAuthType"] == "httpBearerAuth"
    assert params["url"].startswith("https://")
    assert params["url"].endswith("/v1/runs")
    assert params["options"]["timeout"] == 3_600_000
    assert request["retryOnFail"] is False

    serialized = json.dumps(workflow)
    assert "$env" not in serialized
    assert "GROQ_API_KEY" not in serialized
    assert "RUNWAY_API_KEY" not in serialized
    assert "SUPABASE_SECRET_KEY" not in serialized
