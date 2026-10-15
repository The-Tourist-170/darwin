"""Background task queue: Redis/Valkey + RQ for non-blocking offloaded jobs."""

from redis import Redis
from rq import Queue

from darwin.core.config import config


class TaskQueue:
    def __init__(self) -> None:
        self.redis = Redis.from_url(config.REDIS_URL)
        self.queue = Queue("darwin", connection=self.redis)

    def enqueue(self, fn, *args, **kwargs):
        return self.queue.enqueue(fn, *args, **kwargs)
