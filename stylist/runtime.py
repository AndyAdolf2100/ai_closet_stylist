"""Keep execution alive when a subscriber disconnects; drain on process shutdown.

Only authenticated, identical requests share an in-process task. No credentials are
written to checkpoints. Another Pod resumes using the caller's fresh Bearer.
"""
import asyncio
import hashlib

from .errors import StylistError


class RunManager:
    def __init__(self):
        self.tasks = {}
        self.draining = False

    async def run(self, engine, upstream, request, decision=None):
        await upstream.identity()  # Revalidate even when reattaching to an existing task.
        key = hashlib.sha256((upstream.authorization + request.model_dump_json() + str(decision)).encode()).hexdigest()
        task = self.tasks.get(key)
        if task is None:
            if self.draining:
                raise StylistError("server_draining", "服务正在更新，正在为你重新连接。")
            task = asyncio.create_task(engine.chat(upstream, request) if decision is None else
                                       engine.chat(upstream, request, decision=decision))
            self.tasks[key] = task
            def done(finished):
                self.tasks.pop(key, None)
                if not finished.cancelled():
                    finished.exception()  # Observe exceptions after the subscriber has gone.
            task.add_done_callback(done)
        return await asyncio.shield(task)

    async def close(self):
        self.draining = True
        if self.tasks:
            await asyncio.wait(list(self.tasks.values()), timeout=30)
