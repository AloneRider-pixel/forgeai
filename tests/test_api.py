from fastapi.testclient import TestClient

from forgeai.main import app
from forgeai.services.github_client import GitHubClient, PullRequestSnapshot


class FakeGitHubClient:
    def get_pull_request(self, repository: str, pull_request: int) -> PullRequestSnapshot:
        return PullRequestSnapshot(
            repository=repository,
            pull_request=pull_request,
            title="Add authentication flow",
            state="open",
            filenames=["src/auth/router.py", "tests/test_auth.py"],
            additions=42,
            deletions=8,
            changed_files=2,
        )

    def close(self) -> None:
        pass


def test_health() -> None:
    with TestClient(app) as client:
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok", "service": "forgeai"}


def test_create_review(monkeypatch) -> None:
    def fake_client(self) -> PullRequestSnapshot:
        return FakeGitHubClient().get_pull_request("octocat/hello-world", 42)

    monkeypatch.setattr(GitHubClient, "get_pull_request", fake_client)

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
