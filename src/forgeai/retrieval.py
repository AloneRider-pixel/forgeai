from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

import httpx

from forgeai.config import Settings
from forgeai.services.github_client import GitHubClient


@dataclass(frozen=True)
class RetrievedDocument:
    path: str
    content: str
    score: float
    mode: str


def _cosine(left: list[float], right: list[float]) -> float:
    if not left or not right or len(left) != len(right):
        return 0.0
    numerator = sum(a * b for a, b in zip(left, right, strict=True))
    left_norm = math.sqrt(sum(a * a for a in left))
    right_norm = math.sqrt(sum(b * b for b in right))
    if left_norm == 0 or right_norm == 0:
        return 0.0
    return numerator / (left_norm * right_norm)


def _tokens(text: str) -> set[str]:
    current = []
    output: set[str] = set()
    for char in text.lower():
        if char.isalnum() or char == "_":
            current.append(char)
        elif current:
            output.add("".join(current))
            current.clear()
    if current:
        output.add("".join(current))
    return {item for item in output if len(item) > 2}


class EmbeddingProvider:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    @property
    def enabled(self) -> bool:
        return bool(self.settings.embedding_base_url and self.settings.embedding_api_key)

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not self.enabled:
            return []
        response = httpx.post(
            self.settings.embedding_base_url.rstrip("/") + "/embeddings",
            headers={"Authorization": f"Bearer {self.settings.embedding_api_key}"},
            json={"model": self.settings.embedding_model, "input": texts},
            timeout=self.settings.llm_timeout_seconds,
        )
        response.raise_for_status()
        payload: Any = response.json()
        data = payload.get("data", []) if isinstance(payload, dict) else []
        return [
            item["embedding"]
            for item in data
            if isinstance(item, dict) and isinstance(item.get("embedding"), list)
        ]


class RepositoryRetriever:
    """Repository-wide retrieval with remote embeddings and a deterministic fallback."""

    def __init__(self, github: GitHubClient, settings: Settings) -> None:
        self.github = github
        self.settings = settings
        self.embeddings = EmbeddingProvider(settings)

    def index_repository(self, repository: str, ref: str = "main") -> list[dict[str, Any]]:
        tree = self.github.get_repository_tree(repository, ref)
        documents: list[dict[str, Any]] = []
        for item in tree[: self.settings.retrieval_max_files]:
            path = item.get("path")
            excluded_prefixes = (".git/", "node_modules/", "dist/", "build/")
            if not isinstance(path, str) or path.startswith(excluded_prefixes):
                continue
            size = int(item.get("size", 0))
            if size > 100_000:
                continue
            content = self.github.get_file_content(repository, path, ref)
            if not content:
                continue
            documents.append(
                {"path": path, "content": content, "sha": item.get("sha", "")}
            )
        if self.embeddings.enabled and documents:
            vectors = self.embeddings.embed(
                [
                    item["path"] + "\n" + item["content"][:12000]
                    for item in documents
                ]
            )
            for item, vector in zip(documents, vectors, strict=True):
                item["embedding"] = vector
        else:
            for item in documents:
                item["embedding"] = []
        return documents

    def search(
        self,
        query: str,
        documents: list[dict[str, Any]],
        top_k: int,
    ) -> list[RetrievedDocument]:
        query_vector: list[float] = []
        if self.embeddings.enabled:
            vectors = self.embeddings.embed([query])
            query_vector = vectors[0] if vectors else []

        query_tokens = _tokens(query)
        scored: list[RetrievedDocument] = []
        for item in documents:
            content = str(item.get("content", ""))
            path = str(item.get("path", ""))
            vector = item.get("embedding", [])
            if query_vector and isinstance(vector, list):
                score = _cosine(query_vector, vector)
                mode = "embedding"
            else:
                tokens = _tokens(path + "\n" + content[:12000])
                score = len(query_tokens & tokens) / max(len(query_tokens), 1)
                mode = "lexical-fallback"
            scored.append(
                RetrievedDocument(
                    path=path,
                    content=content[:12000],
                    score=score,
                    mode=mode,
                )
            )
        scored.sort(key=lambda item: item.score, reverse=True)
        return scored[:top_k]
