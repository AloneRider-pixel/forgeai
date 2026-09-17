from __future__ import annotations

import asyncio

from forgeai.config import get_settings
from forgeai.db import Database
from forgeai.observability import review_span
from forgeai.queue import InMemoryJobQueue, RedisJobQueue
from forgeai.services.github_client import GitHubClient
from forgeai.services.review_service import ReviewService


class ReviewWorker:
    def __init__(self, service: ReviewService, queue: InMemoryJobQueue | RedisJobQueue) -> None:
        self.service = service
        self.queue = queue

    async def run_forever(self) -> None:
        while True:
            job_id = await self.queue.dequeue(timeout=5)
            if job_id:
                with review_span(job_id):
                    await self.service.process(job_id)


async def main() -> None:
    settings = get_settings()
    database = Database(settings.database_url)
    await database.init()
    github = GitHubClient(token=settings.github_token, timeout=settings.http_timeout_seconds)
    queue = RedisJobQueue(settings.redis_url) if settings.redis_url else InMemoryJobQueue()
    service = ReviewService(database, github, settings)
    try:
        await ReviewWorker(service, queue).run_forever()
    finally:
        github.close()
        if isinstance(queue, RedisJobQueue):
            await queue.close()
        await database.close()


if __name__ == "__main__":
    asyncio.run(main())
