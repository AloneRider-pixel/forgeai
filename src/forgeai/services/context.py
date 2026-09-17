from __future__ import annotations

import re
from collections.abc import Iterable

from forgeai.models import ChangedFile, ContextSnippet, Finding, PullRequestSnapshot
from forgeai.services.github_client import GitHubAPIError, GitHubClient

SOURCE_EXTENSIONS = (
    ".py",
    ".ts",
    ".tsx",
    ".js",
    ".jsx",
    ".go",
    ".java",
    ".rs",
    ".cs",
    ".rb",
    ".sql",
    ".yaml",
    ".yml",
    ".json",
)
SECRET_VALUE = re.compile(
    r"(?i)(api[_-]?key|secret|password|token|access[_-]?key)"
    r"(\s*[:=]\s*)([\"']?)[^\s,;\"']+\3"
)
PRIVATE_KEY_BLOCK = re.compile(
    r"-----BEGIN [A-Z ]*PRIVATE KEY-----.*?-----END [A-Z ]*PRIVATE KEY-----",
    re.DOTALL,
)


def _tokens(text: str) -> set[str]:
    return {token for token in re.findall(r"[a-zA-Z][a-zA-Z0-9_]{2,}", text.lower())}


def _relevance(query: str, content: str, path: str) -> float:
    query_tokens = _tokens(query)
    if not query_tokens:
        return 0.0
    haystack = _tokens(f"{path} {content[:12000]}")
    overlap = len(query_tokens & haystack)
    return min(1.0, overlap / max(3, len(query_tokens)))


def redact_secrets(text: str) -> tuple[str, bool]:
    redacted = PRIVATE_KEY_BLOCK.sub("[REDACTED PRIVATE KEY]", text)
    redacted = SECRET_VALUE.sub(
        lambda match: f"{match.group(1)}{match.group(2)}[REDACTED]",
        redacted,
    )
    return redacted, redacted != text


def build_context_query(snapshot: PullRequestSnapshot, findings: Iterable[Finding]) -> str:
    finding_terms = " ".join(
        f"{finding.category} {finding.title} {finding.detail}" for finding in findings
    )
    return f"{snapshot.title} {finding_terms}"


def collect_context(
    client: GitHubClient,
    snapshot: PullRequestSnapshot,
    changed_files: list[ChangedFile],
    findings: list[Finding],
    max_files: int = 5,
    max_chars: int = 12000,
) -> list[ContextSnippet]:
    if not snapshot.head_sha:
        return []

    query = build_context_query(snapshot, findings)
    candidates = [
        item
        for item in changed_files
        if item.status != "removed"
        and item.path.lower().endswith(SOURCE_EXTENSIONS)
    ]
    candidates.sort(
        key=lambda item: (
            _relevance(query, item.patch or "", item.path),
            item.additions + item.deletions,
        ),
        reverse=True,
    )

    snippets: list[ContextSnippet] = []
    for item in candidates[:max_files]:
        try:
            content = client.get_file_content(
                snapshot.repository,
                item.path,
                snapshot.head_sha,
            )
        except GitHubAPIError:
            continue
        if content is None:
            continue
        truncated = len(content) > max_chars
        content = content[:max_chars]
        content, redacted = redact_secrets(content)
        snippets.append(
            ContextSnippet(
                path=item.path,
                content=content,
                truncated=truncated,
                redacted=redacted,
                relevance=_relevance(query, content, item.path),
            )
        )
    return snippets
