from __future__ import annotations

import time
from unittest.mock import patch

from fastapi.testclient import TestClient

from forgeai.main import app, settings
from forgeai.models import ChangedFile, PullRequestSnapshot, Severity
from forgeai.services.github_client import GitHubClient


def _snapshot() -> PullRequestSnapshot:
    return PullRequestSnapshot(
        repository="octocat/hello-world",
        pull_request=42,
        title="Add authentication service",
        state="open",
        head_sha="abc123",
        filenames=["src/auth/service.py"],
        additions=20,
        deletions=3,
        changed_files=1,
    )


def test_control_plane_job_evidence_approval_and_execution(tmp_path) -> None:
    original_database_url = settings.database_url
    settings.database_url = f"sqlite+aiosqlite:///{tmp_path / 'forgeai.db'}"
    changed_files = [ChangedFile(path="src/auth/service.py", additions=20, deletions=3)]
    try:
        with patch.object(
            GitHubClient,
            "get_pull_request_bundle",
            return_value=(_snapshot(), changed_files),
        ):
            with patch.object(
                GitHubClient,
                "get_file_content",
                return_value="def authenticate(token):\n    return token\n",
            ), patch.object(GitHubClient, "dispatch_workflow", return_value=None):
                with TestClient(app) as client:
                    response = client.post(
                        "/v1/jobs",
                        json={"repository": "octocat/hello-world", "pull_request": 42},
                    )
                    assert response.status_code == 202
                    job_id = response.json()["job_id"]

                    detail = client.get(f"/v1/jobs/{job_id}")
                    for _ in range(40):
                        if detail.json()["status"] == "succeeded":
                            break
                        time.sleep(0.05)
                        detail = client.get(f"/v1/jobs/{job_id}")
                    assert detail.json()["status"] == "succeeded"

                    evidence = client.post(
                        f"/v1/jobs/{job_id}/evidence",
                        json={
                            "findings": [
                                {
                                    "rule_id": "jsql-001",
                                    "severity": Severity.HIGH.value,
                                    "message": "High-severity external analysis finding",
                                    "path": "src/auth/service.py",
                                    "source": "codeql",
                                }
                            ]
                        },
                    )
                    assert evidence.status_code == 200
                    assert evidence.json()["gate"] == "review_required"
                    assert evidence.json()["approval"]["state"] == "pending"

                    approved = client.post(
                        f"/v1/jobs/{job_id}/approval/approve",
                        json={
                            "decided_by": "reviewer",
                            "rationale": "Reviewed evidence and change.",
                        },
                    )
                    assert approved.status_code == 200
                    assert approved.json()["approval"]["state"] == "approved"

                    executed = client.post(
                        f"/v1/jobs/{job_id}/execute",
                        json={
                            "tool_name": "github.workflow_dispatch",
                            "arguments": {"workflow_id": "ci.yml", "ref": "main"},
                        },
                    )
                    assert executed.status_code == 200
                    assert executed.json()["response"]["dispatched"] is True
    finally:
        settings.database_url = original_database_url
