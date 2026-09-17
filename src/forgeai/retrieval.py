from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import PurePosixPath

_TOKEN_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]{1,}")
_DEFAULT_EXTENSIONS = frozenset({".py", ".md", ".yml", ".yaml", ".json", ".toml", ".txt"})


@dataclass(frozen=True)
class RepositoryDocument:
    path: str
    content: str


@dataclass(frozen=True)
class RetrievalHit:
    path: str
    score: float
    snippet: str


class LexicalSemanticIndex:
    """Lightweight dependency-free semantic retrieval using TF-IDF cosine similarity.

    It provides deterministic repository-wide retrieval locally while keeping the
    interface compatible with a future embedding/vector backend.
    """

    def __init__(self, documents: list[RepositoryDocument]) -> None:
        self.documents = documents
        self._vectors: list[dict[str, float]] = []
        document_frequency: Counter[str] = Counter()
        tokenized: list[list[str]] = []
        for document in documents:
            tokens = self._tokens(document.path + " " + document.content)
            tokenized.append(tokens)
            document_frequency.update(set(tokens))
        total = max(len(documents), 1)
        for tokens in tokenized:
            counts = Counter(tokens)
            length = max(len(tokens), 1)
            vector = {}
            for token, count in counts.items():
                idf = math.log((1 + total) / (1 + document_frequency[token])) + 1
                vector[token] = (count / length) * idf
            self._vectors.append(vector)

    @staticmethod
    def _tokens(text: str) -> list[str]:
        return [token.lower() for token in _TOKEN_RE.findall(text) if len(token) > 2]

    def search(self, query: str, limit: int = 5) -> list[RetrievalHit]:
        query_tokens = self._tokens(query)
        if not query_tokens or not self.documents:
            return []
        query_counts = Counter(query_tokens)
        total = max(len(self.documents), 1)
        document_frequency = Counter()
        for vector in self._vectors:
            document_frequency.update(vector.keys())
        query_vector = {
            token: (count / len(query_tokens))
            * (math.log((1 + total) / (1 + document_frequency[token])) + 1)
            for token, count in query_counts.items()
        }
        query_norm = math.sqrt(sum(value * value for value in query_vector.values())) or 1.0
        hits: list[RetrievalHit] = []
        for document, vector in zip(self.documents, self._vectors, strict=True):
            dot = sum(query_vector.get(key, 0.0) * value for key, value in vector.items())
            norm = math.sqrt(sum(value * value for value in vector.values())) or 1.0
            score = dot / (query_norm * norm)
            if score <= 0:
                continue
            hits.append(
                RetrievalHit(
                    path=document.path,
                    score=score,
                    snippet=self._snippet(document.content, query_tokens),
                )
            )
        return sorted(hits, key=lambda hit: hit.score, reverse=True)[:limit]

    @staticmethod
    def _snippet(content: str, query_tokens: list[str], width: int = 280) -> str:
        lowered = content.lower()
        positions = [lowered.find(token) for token in query_tokens if lowered.find(token) >= 0]
        start = max(min(positions) - 80, 0) if positions else 0
        snippet = " ".join(content[start : start + width].split())
        return snippet


def build_index(
    documents: list[RepositoryDocument],
    max_documents: int = 500,
    max_chars_per_document: int = 20_000,
) -> LexicalSemanticIndex:
    selected = []
    for document in documents:
        suffix = PurePosixPath(document.path).suffix.lower()
        if suffix in _DEFAULT_EXTENSIONS:
            selected.append(
                RepositoryDocument(
                    path=document.path,
                    content=document.content[:max_chars_per_document],
                )
            )
        if len(selected) >= max_documents:
            break
    return LexicalSemanticIndex(selected)
