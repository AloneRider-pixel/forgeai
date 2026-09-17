from __future__ import annotations

import time
from typing import Any

import httpx

from forgeai.models import PullRequestSnapshot


class GitHubAPIError(RuntimeError):
    """Raised when GitHub returns an unexpected response."""


class GitHubClient:
    def __init__(self, token: str | None = None, timeout: float = 15.0, max_retries: int = 3) -> None:
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
        self._max_retries = max_retries

    def close(self) -> None:
        self._client.close()

    def _request(self, method: str, path: str, **kwargs: Any) -> httpx.Response:
        last_error: Exception | None = None
        for attempt in range(self._max_retries + 1):
            try:
                response = self._client.request(method, path, **kwargs)
            except httpx.HTTPError as exc:
                last_error = exc
                if attempt == self._max_retries:
                    raise GitHubAPIError(f"GitHub request failed: {exc}") from exc
                time.sleep(0.25 * (2**attempt))
                continue

            if response.status_code not in {429, 500, 502, 503, 504}:
                return response
            if attempt == self._max_retries:
                return response
            retry_after = response.headers.get("Retry-After")
            delay = float(retry_after) if retry_after and retry_after.isdigit() else 0.25 * (2**attempt)
            time.sleep(min(delay, 5.0))

        raise GitHubAPIError(f"GitHub request failed: {last_error or 'unknown error'}")

    @staticmethod
    def _raise_for_payload(response: httpx.Response, endpoint: str) -> Any:
        if response.status_code >= 400:
            raise GitHubAPIError(
                f"GitHub {endpoint} request failed with HTTP {response.status_code}: "
                f"{response.text[:200]}"
            )
        try:
            return response.json()
        except ValueError as exc:
            raise GitHubAPIError(f"GitHub returned invalid JSON for {endpoint}") from exc

    def get_pull_request(self, repository: str, pull_request: int) -> PullRequestSnapshot:
        payload = self._raise_for_payload(
            self._request("GET", f"/repos/{repository}/pulls/{pull_request}"),
            "pull request",
        )
        if not isinstance(payload, dict):
            raise GitHubAPIError("GitHub returned a malformed pull request payload")

        filenames: list[str] = []
        page = 1
        while page <= 5:
            files_response = self._request(
                "GET",
                f"/repos/{repository}/pulls/{pull_request}/files",
                params={"per_page": 100, "page": page},
            )
            files_payload = self._raise_for_payload(files_response, "changed-files")
            if not isinstance(files_payload, list):
                raise GitHubAPIError("GitHub returned a malformed changed-files payload")
            for item in files_payload:
                if not isinstance(item, dict) or not isinstance(item.get("filename"), str):
                    raise GitHubAPIError("GitHub returned a malformed changed-file entry")
                filenames.append(item["filename"])
            if len(files_payload) < 100:
                break
            page += 1

        return PullRequestSnapshot(
            repository=repository,
            pull_request=pull_request,
            title=payload.get("title", ""),
            state=payload.get("state", "unknown"),
            draft=bool(payload.get("draft", False)),
            filenames=filenames,
            additions=int(payload.get("additions", 0)),
            deletions=int(payload.get("deletions", 0)),
            changed_files=int(payload.get("changed_files", len(filenames))),
        )
