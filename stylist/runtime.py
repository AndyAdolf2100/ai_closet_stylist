"""Keep execution alive when a subscriber disconnects; drain on process shutdown.

Only authenticated, identical requests share an in-process task. No credentials are
written to checkpoints. Another Pod resumes using the caller's fresh Bearer.
"""
import asyncio
import hashlib
import time
from collections import OrderedDict

from .errors import StylistError


class RunManager:
    def __init__(self):
        self.tasks = {}
        self.draining = False
        self.stopped = OrderedDict()

    @staticmethod
    def key(upstream, request, decision=None):
        return hashlib.sha256((upstream.authorization + request.model_dump_json() + str(decision)).encode()).hexdigest()

    def prune_stops(self):
        cutoff = time.monotonic() - 600
        while self.stopped and (next(iter(self.stopped.values())) < cutoff or len(self.stopped) > 2048):
            self.stopped.popitem(last=False)

    async def stop(self, upstream, request):
        await upstream.identity()
        self.prune_stops()
        key = self.key(upstream, request)
        # Tombstone also handles a stop arriving before run() finishes identity validation.
        self.stopped.pop(key, None)
        self.stopped[key] = time.monotonic()
        self.prune_stops()
        task = self.tasks.get(key)
        if task is None or task.done():
            return {"status": "not_running"}
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)
        return {"status": "stop_requested"}

    async def run(self, engine, upstream, request, decision=None):
        await upstream.identity()  # Revalidate even when reattaching to an existing task.
        self.prune_stops()
        key = self.key(upstream, request, decision)
        if key in self.stopped:
            raise StylistError("request_stopped", "这次生成已停止，可以重新发送。", 409)
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
