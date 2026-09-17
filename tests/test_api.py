from unittest.mock import patch

from fastapi.testclient import TestClient

from forgeai.main import app
from forgeai.models import PullRequestSnapshot


def test_health() -> None:
    with TestClient(app) as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "forgeai"}


def test_ready() -> None:
    with TestClient(app) as client:
        response = client.get("/ready")

    assert response.status_code == 200
    assert response.json() == {"status": "ready", "service": "forgeai", "queue": True}


def test_create_review() -> None:
    fake_snapshot = PullRequestSnapshot(
        repository="octocat/hello-world",
        pull_request=42,
        title="Add authentication flow",
        state="open",
        filenames=["src/auth/router.py", "tests/test_auth.py"],
        additions=42,
        deletions=8,
        changed_files=2,
    )
    with patch("forgeai.main.GitHubClient.get_pull_request", return_value=fake_snapshot):
        with TestClient(app) as client:
            response = client.post(
                "/v1/reviews",
                json={"repository": "octocat/hello-world", "pull_request": 42},
            )

    assert response.status_code == 200
    payload = response.json()
    assert payload["snapshot"]["pull_request"] == 42
    assert payload["risk_score"] >= 30
    assert payload["gate"] in {"review_required", "eligible_for_auto_pass"}
    assert payload["findings"][0]["rule_id"] == "SEC001"
