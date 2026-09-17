from __future__ import annotations

import httpx
from pydantic import BaseModel, Field


class GitHubAPIError(RuntimeError):
    """Raised when GitHub returns an unexpected response."""


class PullRequestSnapshot(BaseModel):
    repository: str
    pull_request: int
    title: str
    state: str
    filenames: list[str] = Field(default_factory=list)
    additions: int = 0
    deletions: int = 0
    changed_files: int = 0


class GitHubClient:
    def __init__(self, token: str | None = None, timeout: float = 15.0) -> None:
        headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        if token:
            headers["Authorization"] = f"Bearer {token}"
        self._client = httpx.Client(
            base_url="https://api.github.com",
            headers=headers,
            timeout=timeout,
            follow_redirects=True,
        )

    def close(self) -> None:
        self._client.close()

    def get_pull_request(self, repository: str, pull_request: int) -> PullRequestSnapshot:
        response = self._client.get(f"/repos/{repository}/pulls/{pull_request}")
        if response.status_code >= 400:
            raise GitHubAPIError(
                f"GitHub pull request request failed with HTTP {response.status_code}: "
                f"{response.text[:200]}"
            )

        payload = response.json()
        if not isinstance(payload, dict):
            raise GitHubAPIError("GitHub returned a malformed pull request payload")

        files_response = self._client.get(
            f"/repos/{repository}/pulls/{pull_request}/files",
            params={"per_page": 100},
        )
        if files_response.status_code >= 400:
            raise GitHubAPIError(
                f"GitHub changed-files request failed with HTTP {files_response.status_code}: "
                f"{files_response.text[:200]}"
            )

        files_payload = files_response.json()
        if not isinstance(files_payload, list):
            raise GitHubAPIError("GitHub returned a malformed changed-files payload")

        filenames: list[str] = []
        for item in files_payload:
            if not isinstance(item, dict) or not isinstance(item.get("filename"), str):
                raise GitHubAPIError("GitHub returned a malformed changed-file entry")
            filenames.append(item["filename"])

        return PullRequestSnapshot(
            repository=repository,
            pull_request=pull_request,
            title=payload.get("title", ""),
            state=payload.get("state", "unknown"),
            filenames=filenames,
            additions=int(payload.get("additions", 0)),
            deletions=int(payload.get("deletions", 0)),
            changed_files=int(payload.get("changed_files", len(filenames))),
        )
