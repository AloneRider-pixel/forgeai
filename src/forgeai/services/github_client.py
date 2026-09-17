from __future__ import annotations

import base64
import time
from typing import Any

import httpx

from forgeai.models import ChangedFile, PullRequestSnapshot


class GitHubAPIError(RuntimeError):
    """Raised when GitHub returns an unexpected response."""


class GitHubClient:
    def __init__(
        self,
        token: str | None = None,
        timeout: float = 15.0,
        max_retries: int = 3,
    ) -> None:
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
            if retry_after and retry_after.isdigit():
                delay = float(retry_after)
            else:
                delay = 0.25 * (2**attempt)
            time.sleep(min(delay, 5.0))

        raise GitHubAPIError(f"GitHub request failed: {last_error or 'unknown error'}")

    @staticmethod
    def _raise_for_payload(response: httpx.Response, endpoint: str) -> Any:
        if response.status_code >= 400:
            raise GitHubAPIError(
                f"GitHub {endpoint} request failed with HTTP {response.status_code}: "
                f"{response.text[:200]}"
            )
        if response.status_code == 204:
            return None
        try:
            return response.json()
        except ValueError as exc:
            raise GitHubAPIError(f"GitHub returned invalid JSON for {endpoint}") from exc

    def _get_pull_request_payload(self, repository: str, pull_request: int) -> dict[str, Any]:
        payload = self._raise_for_payload(
            self._request("GET", f"/repos/{repository}/pulls/{pull_request}"),
            "pull request",
        )
        if not isinstance(payload, dict):
            raise GitHubAPIError("GitHub returned a malformed pull request payload")
        return payload

    def get_pull_request_files(
        self, repository: str, pull_request: int, max_pages: int = 5
    ) -> list[ChangedFile]:
        changed_files: list[ChangedFile] = []
        page = 1
        while page <= max_pages:
            response = self._request(
                "GET",
                f"/repos/{repository}/pulls/{pull_request}/files",
                params={"per_page": 100, "page": page},
            )
            payload = self._raise_for_payload(response, "changed-files")
            if not isinstance(payload, list):
                raise GitHubAPIError("GitHub returned a malformed changed-files payload")
            for item in payload:
                if not isinstance(item, dict) or not isinstance(item.get("filename"), str):
                    raise GitHubAPIError("GitHub returned a malformed changed-file entry")
                changed_files.append(
                    ChangedFile(
                        path=item["filename"],
                        status=str(item.get("status", "modified")),
                        additions=int(item.get("additions", 0)),
                        deletions=int(item.get("deletions", 0)),
                        patch=item.get("patch") if isinstance(item.get("patch"), str) else None,
                    )
                )
            if len(payload) < 100:
                break
            page += 1
        return changed_files

    def get_pull_request_bundle(
        self, repository: str, pull_request: int
    ) -> tuple[PullRequestSnapshot, list[ChangedFile]]:
        payload = self._get_pull_request_payload(repository, pull_request)
        changed_files = self.get_pull_request_files(repository, pull_request)
        head = payload.get("head")
        base = payload.get("base")
        head_sha = head.get("sha", "") if isinstance(head, dict) else ""
        head_ref = head.get("ref", "") if isinstance(head, dict) else ""
        base_ref = base.get("ref", "") if isinstance(base, dict) else ""
        snapshot = PullRequestSnapshot(
            repository=repository,
            pull_request=pull_request,
            title=str(payload.get("title", "")),
            state=str(payload.get("state", "unknown")),
            draft=bool(payload.get("draft", False)),
            head_sha=head_sha,
            head_ref=head_ref,
            base_ref=base_ref,
            filenames=[item.path for item in changed_files],
            additions=int(payload.get("additions", 0)),
            deletions=int(payload.get("deletions", 0)),
            changed_files=int(payload.get("changed_files", len(changed_files))),
        )
        return snapshot, changed_files

    def get_pull_request(self, repository: str, pull_request: int) -> PullRequestSnapshot:
        snapshot, _ = self.get_pull_request_bundle(repository, pull_request)
        return snapshot

    def get_repository_tree(self, repository: str, ref: str = "main") -> list[dict[str, Any]]:
        response = self._request(
            "GET", f"/repos/{repository}/git/trees/{ref}", params={"recursive": "1"}
        )
        payload = self._raise_for_payload(response, "repository-tree")
        if not isinstance(payload, dict) or not isinstance(payload.get("tree"), list):
            raise GitHubAPIError("GitHub returned a malformed repository tree")
        return [
            item
            for item in payload["tree"]
            if isinstance(item, dict) and item.get("type") == "blob"
        ]

    def get_file_content(self, repository: str, path: str, ref: str) -> str | None:
        response = self._request(
            "GET", f"/repos/{repository}/contents/{path}", params={"ref": ref}
        )
        payload = self._raise_for_payload(response, "file-content")
        if not isinstance(payload, dict):
            return None
        if payload.get("encoding") != "base64" or not isinstance(payload.get("content"), str):
            return None
        try:
            return base64.b64decode(payload["content"]).decode("utf-8", errors="replace")
        except (ValueError, UnicodeError) as exc:
            raise GitHubAPIError(f"GitHub returned undecodable content for {path}") from exc

    def dispatch_workflow(self, repository: str, workflow_id: str, ref: str = "main") -> None:
        response = self._request(
            "POST",
            f"/repos/{repository}/actions/workflows/{workflow_id}/dispatches",
            json={"ref": ref},
        )
        self._raise_for_payload(response, "workflow-dispatch")
