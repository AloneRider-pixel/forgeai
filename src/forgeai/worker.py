from __future__ import annotations

import asyncio

from forgeai.config import get_settings
from forgeai.db import Database
from forgeai.observability import review_span
from forgeai.queue import InMemoryJobQueue, RedisJobQueue
from forgeai.repository import ControlPlaneRepository
from forgeai.services.github_client import GitHubClient
from forgeai.services.review_service import ReviewService


class ReviewWorker:
    def __init__(
        self,
        service: ReviewService,
        queue: InMemoryJobQueue | RedisJobQueue,
    ) -> None:
        self.service = service
        self.queue = queue
        self.repository = ControlPlaneRepository()

    async def run_forever(self) -> None:
        while True:
            job_id = await self.queue.dequeue(timeout=5)
            if not job_id:
                continue
            async with self.service.database.sessions() as session:
                record = await self.repository.get_job(session, job_id)
            attributes = {}
            if record:
                attributes = {
                    "review.repository": record.repository,
                    "review.pull_request": record.pull_request,
                    "review.trigger_source": str(
                        record.request_json.get("trigger_source", "unknown")
                    ),
                }
            try:
                with review_span(job_id, attributes):
                    await self.service.process(job_id)
            except Exception:
                continue


async def main() -> None:
    settings = get_settings()
    database = Database(
        settings.database_url,
        auto_create_schema=settings.auto_create_schema,
    )
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
