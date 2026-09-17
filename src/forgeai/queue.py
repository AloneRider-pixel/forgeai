from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from typing import Protocol

import redis.asyncio as redis


class JobQueue(Protocol):
    async def enqueue(self, job_id: str) -> None: ...

    async def dequeue(self, timeout: int = 5) -> str | None: ...


class InMemoryJobQueue:
    def __init__(self) -> None:
        self._queue: asyncio.Queue[str] = asyncio.Queue()

    async def enqueue(self, job_id: str) -> None:
        await self._queue.put(job_id)

    async def dequeue(self, timeout: int = 5) -> str | None:
        try:
            return await asyncio.wait_for(self._queue.get(), timeout=timeout)
        except TimeoutError:
            return None


class RedisJobQueue:
    def __init__(self, url: str, key: str = "forgeai:review_jobs") -> None:
        self.client = redis.from_url(url, decode_responses=True)
        self.key = key

    async def enqueue(self, job_id: str) -> None:
        await self.client.rpush(self.key, job_id)

    async def dequeue(self, timeout: int = 5) -> str | None:
        item = await self.client.blpop(self.key, timeout=timeout)
        return item[1] if item else None

    async def close(self) -> None:
        await self.client.aclose()


async def queue_health(queue: JobQueue) -> bool:
    if isinstance(queue, RedisJobQueue):
        try:
            await queue.client.ping()
        except redis.RedisError:
            return False
    return True
