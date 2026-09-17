from forgeai.models import ChangedFile, Finding, PullRequestSnapshot, Severity
from forgeai.services.context import collect_context, redact_secrets


class FakeClient:
    def __init__(self, contents: dict[str, str]) -> None:
        self.contents = contents

    def get_file_content(self, repository: str, path: str, ref: str) -> str | None:
        return self.contents.get(path)


def test_redact_secrets_removes_common_secret_values() -> None:
    text = 'api_key="super-secret"\npassword = hidden-value'

    redacted, changed = redact_secrets(text)

    assert changed is True
    assert "super-secret" not in redacted
    assert "hidden-value" not in redacted
    assert "[REDACTED]" in redacted


def test_collect_context_is_bounded_and_redacted() -> None:
    snapshot = PullRequestSnapshot(
        repository="octocat/hello-world",
        pull_request=42,
        title="Secure login",
        state="open",
        head_sha="abc123",
        filenames=["src/auth.py"],
        additions=8,
        deletions=2,
        changed_files=1,
    )
    findings = [
        Finding(
            rule_id="SEC001",
            severity=Severity.HIGH,
            category="security",
            title="Security-sensitive files changed",
            detail="Authentication code changed.",
            paths=["src/auth.py"],
        )
    ]
    client = FakeClient({"src/auth.py": 'token = "secret-value"\n' + "x" * 100})
    changed_files = [ChangedFile(path="src/auth.py", additions=8, deletions=2)]

    snippets = collect_context(
        client,
        snapshot,
        changed_files,
        findings,
        max_files=1,
        max_chars=40,
    )

    assert len(snippets) == 1
    assert snippets[0].truncated is True
    assert snippets[0].redacted is True
    assert "secret-value" not in snippets[0].content
