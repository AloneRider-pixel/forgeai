import httpx

from forgeai.models import PullRequestSnapshot
from forgeai.services.github_client import GitHubClient, GitHubAPIError


def test_get_pull_request_parses_metadata_and_files() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/pulls/42"):
            return httpx.Response(
                200,
                json={
                    "title": "Add auth",
                    "state": "open",
                    "draft": True,
                    "additions": 10,
                    "deletions": 2,
                    "changed_files": 2,
                },
            )
        return httpx.Response(200, json=[{"filename": "src/auth.py"}, {"filename": "tests/test_auth.py"}])

    client = GitHubClient()
    client._client = httpx.Client(transport=httpx.MockTransport(handler), base_url="https://api.github.com")

    snapshot = client.get_pull_request("octocat/hello-world", 42)

    assert snapshot == PullRequestSnapshot(
        repository="octocat/hello-world",
        pull_request=42,
        title="Add auth",
        state="open",
        draft=True,
        filenames=["src/auth.py", "tests/test_auth.py"],
        additions=10,
        deletions=2,
        changed_files=2,
    )
    client.close()


def test_changed_files_are_paginated() -> None:
    requests: list[int] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/pulls/42"):
            return httpx.Response(200, json={"title": "Large PR", "state": "open"})
        page = int(request.url.params.get("page", "1"))
        requests.append(page)
        if page == 1:
            return httpx.Response(200, json=[{"filename": f"src/file_{index}.py"} for index in range(100)])
        return httpx.Response(200, json=[{"filename": "src/last.py"}])

    client = GitHubClient()
    client._client = httpx.Client(transport=httpx.MockTransport(handler), base_url="https://api.github.com")

    snapshot = client.get_pull_request("octocat/hello-world", 42)

    assert requests == [1, 2]
    assert len(snapshot.filenames) == 101
    assert snapshot.filenames[-1] == "src/last.py"
    client.close()


def test_malformed_changed_file_raises() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/pulls/42"):
            return httpx.Response(200, json={"title": "Bad", "state": "open"})
        return httpx.Response(200, json=[{"not_filename": "src/bad.py"}])

    client = GitHubClient()
    client._client = httpx.Client(transport=httpx.MockTransport(handler), base_url="https://api.github.com")

    try:
        client.get_pull_request("octocat/hello-world", 42)
    except GitHubAPIError as exc:
        assert "malformed changed-file entry" in str(exc)
    else:
        raise AssertionError("Expected malformed changed-file error")
    finally:
        client.close()
