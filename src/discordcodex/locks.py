from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from dataclasses import dataclass


@dataclass
class ChannelJob:
    task: asyncio.Task | None
    project_name: str
    started_at: float


class JobRegistry:
    def __init__(self, max_global: int):
        self._global = asyncio.Semaphore(max_global)
        self._jobs: dict[str, ChannelJob] = {}
        self._lock = asyncio.Lock()

    def get(self, channel_id: str) -> ChannelJob | None:
        return self._jobs.get(channel_id)

    @asynccontextmanager
    async def reserve(self, channel_id: str, project_name: str):
        await self._global.acquire()
        async with self._lock:
            if channel_id in self._jobs:
                self._global.release()
                raise RuntimeError("channel already has an active job")
            self._jobs[channel_id] = ChannelJob(
                task=None,
                project_name=project_name,
                started_at=asyncio.get_running_loop().time(),
            )
        try:
            yield
        finally:
            async with self._lock:
                self._jobs.pop(channel_id, None)
                self._global.release()

    async def set_task(self, channel_id: str, task: asyncio.Task) -> None:
        async with self._lock:
            job = self._jobs.get(channel_id)
            if job:
                job.task = task

    async def cancel(self, channel_id: str) -> bool:
        job = self._jobs.get(channel_id)
        if not job or not job.task:
            return False
        job.task.cancel()
        return True
