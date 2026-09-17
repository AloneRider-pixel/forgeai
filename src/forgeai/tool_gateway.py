from __future__ import annotations

from typing import Any

from forgeai.config import Settings
from forgeai.services.github_client import GitHubClient


class ToolPolicyError(PermissionError):
    pass


class ToolGateway:
    def __init__(self, github: GitHubClient, settings: Settings) -> None:
        self.github = github
        self.settings = settings

    def list_tools(self) -> list[dict[str, object]]:
        return [
            {
                "name": "github.workflow_dispatch",
                "description": "Dispatch an allowlisted GitHub Actions workflow.",
                "requires_approval": True,
            }
        ]

    def call(
        self, tool_name: str, arguments: dict[str, str], *, approved: bool = False
    ) -> dict[str, Any]:
        if tool_name != "github.workflow_dispatch":
            raise ToolPolicyError(f"tool '{tool_name}' is not allowlisted")
        if not approved:
            raise ToolPolicyError("human approval is required before tool execution")

        repository = arguments.get("repository", "")
        workflow_id = arguments.get("workflow_id", "")
        ref = arguments.get("ref", "main")
        if not repository or not workflow_id:
            raise ValueError("repository and workflow_id are required")
        if workflow_id not in self.settings.allowed_github_workflows:
            raise ToolPolicyError(f"workflow '{workflow_id}' is not allowlisted")
        self.github.dispatch_workflow(repository, workflow_id, ref)
        return {
            "repository": repository,
            "workflow_id": workflow_id,
            "ref": ref,
            "dispatched": True,
        }
