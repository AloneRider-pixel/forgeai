from __future__ import annotations

import hashlib
import hmac
import json
import time
from unittest.mock import patch

from fastapi.testclient import TestClient

from forgeai.main import app, settings
from forgeai.models import ChangedFile, PullRequestSnapshot
from forgeai.webhook import normalize_pull_request_event, verify_signature

SECRET = "test-webhook-secret"
DELIVERY_ID = "12345678-aaaa-bbbb-cccc-ddddeeeeffff"


def _payload() -> dict[str, object]:
    return {
        "action": "opened",
        "repository": {"full_name": "octocat/hello-world"},
        "pull_request": {"number": 42},
    }


def _signed(body: bytes) -> str:
    digest = hmac.new(SECRET.encode(), body, hashlib.sha256).hexdigest()
    return f"sha256={digest}"


def _snapshot() -> PullRequestSnapshot:
    return PullRequestSnapshot(
        repository="octocat/hello-world",
        pull_request=42,
        title="Add webhook coverage",
        state="open",
        head_sha="abc123",
        filenames=["src/app.py"],
        additions=12,
        deletions=2,
        changed_files=1,
    )


def test_signature_verification() -> None:
    body = b'{"action":"opened"}'
    verify_signature(body, _signed(body), SECRET)


def test_normalize_ignores_unsupported_action() -> None:
    event = normalize_pull_request_event(
        DELIVERY_ID,
        "pull_request",
        {"action": "closed"},
    )
    assert event is None


def test_github_webhook_is_signed_idempotent_and_dispatched(tmp_path) -> None:
    original_database_url = settings.database_url
    original_secret = settings.github_webhook_secret
    settings.database_url = f"sqlite+aiosqlite:///{tmp_path / 'forgeai.db'}"
    settings.github_webhook_secret = SECRET
    body = json.dumps(_payload(), separators=(",", ":")).encode()
    headers = {
        "X-GitHub-Event": "pull_request",
        "X-GitHub-Delivery": DELIVERY_ID,
        "X-Hub-Signature-256": _signed(body),
        "Content-Type": "application/json",
    }
    changed_files = [ChangedFile(path="src/app.py", additions=12, deletions=2)]
    try:
        with patch(
            "forgeai.services.github_client.GitHubClient.get_pull_request_bundle",
            return_value=(_snapshot(), changed_files),
        ), patch(
            "forgeai.services.github_client.GitHubClient.get_file_content",
            return_value="def run():\n    return True\n",
        ):
            with TestClient(app) as client:
                first = client.post("/v1/webhooks/github", content=body, headers=headers)
                assert first.status_code == 202
                assert first.json()["accepted"] is True
                assert first.json()["duplicate"] is False
                job_id = first.json()["job_id"]

                duplicate = client.post(
                    "/v1/webhooks/github", content=body, headers=headers
                )
                assert duplicate.status_code == 202
                assert duplicate.json()["duplicate"] is True
                assert duplicate.json()["job_id"] == job_id

                delivery = client.get(f"/v1/webhooks/github/{DELIVERY_ID}")
                for _ in range(60):
                    if delivery.json()["status"] == "completed":
                        break
                    time.sleep(0.05)
                    delivery = client.get(f"/v1/webhooks/github/{DELIVERY_ID}")
                assert delivery.json()["status"] == "completed"
                job = client.get(f"/v1/jobs/{job_id}")
                assert job.json()["status"] == "succeeded"
                assert job.json()["pull_request"] == 42
    finally:
        settings.database_url = original_database_url
        settings.github_webhook_secret = original_secret


def test_webhook_rejects_bad_signature(tmp_path) -> None:
    original_database_url = settings.database_url
    original_secret = settings.github_webhook_secret
    settings.database_url = f"sqlite+aiosqlite:///{tmp_path / 'forgeai.db'}"
    settings.github_webhook_secret = SECRET
    body = json.dumps(_payload()).encode()
    try:
        with TestClient(app) as client:
            response = client.post(
                "/v1/webhooks/github",
                content=body,
                headers={
                    "X-GitHub-Event": "pull_request",
                    "X-GitHub-Delivery": DELIVERY_ID,
                    "X-Hub-Signature-256": "sha256=" + "0" * 64,
                },
            )
            assert response.status_code == 401
    finally:
        settings.database_url = original_database_url
        settings.github_webhook_secret = original_secret
