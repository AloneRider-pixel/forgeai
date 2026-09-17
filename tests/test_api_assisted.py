from unittest.mock import patch

from fastapi.testclient import TestClient

from forgeai.main import app
from forgeai.models import ChangedFile, PullRequestSnapshot


def test_assisted_review_returns_context_and_plan() -> None:
    snapshot = PullRequestSnapshot(
        repository="octocat/hello-world",
        pull_request=42,
        title="Add authentication flow",
        state="open",
        head_sha="abc123",
        filenames=["src/auth/service.py", "tests/test_auth.py"],
        additions=42,
        deletions=8,
        changed_files=2,
    )
    changed_files = [
        ChangedFile(path="src/auth/service.py", additions=35, deletions=5),
        ChangedFile(path="tests/test_auth.py", additions=7, deletions=3),
    ]
    content = (
        'def authenticate(token):\n'
        '    api_key = "super-secret-value"\n'
        '    return token == api_key\n'
    )

    with patch(
        "forgeai.main.GitHubClient.get_pull_request_bundle",
        return_value=(snapshot, changed_files),
    ), patch(
        "forgeai.main.GitHubClient.get_file_content",
        return_value=content,
    ):
        with TestClient(app) as client:
            response = client.post(
                "/v1/reviews/assisted",
                json={
                    "repository": "octocat/hello-world",
                    "pull_request": 42,
                    "max_context_files": 1,
                    "max_file_chars": 2000,
                },
            )

    assert response.status_code == 200
    payload = response.json()
    assert payload["baseline"]["snapshot"]["pull_request"] == 42
    assert payload["plan"]["provider"] == "deterministic"
    assert len(payload["context"]) == 1
    assert "super-secret-value" not in payload["context"][0]["content"]
    assert payload["context"][0]["redacted"] is True
