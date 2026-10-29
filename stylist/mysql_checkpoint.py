"""Async LangGraph persistence in the same isolated MySQL database as Store."""
import asyncio
import json
from contextlib import ExitStack, asynccontextmanager

from langgraph.checkpoint.base import (
    WRITES_IDX_MAP,
    BaseCheckpointSaver,
    CheckpointTuple,
    get_checkpoint_id,
    get_checkpoint_metadata,
)

from .mysql import mysql_connection, named_lock


class AsyncMySQLSaver(BaseCheckpointSaver):
    def __init__(self, dsn):
        super().__init__()
        self.dsn = dsn

    async def setup(self):
        from .store import Store

        await asyncio.to_thread(Store, self.dsn)

    @asynccontextmanager
    async def lock_thread(self, thread):
        def acquire():
            with ExitStack() as stack:
                conn = stack.enter_context(mysql_connection(self.dsn))
                stack.enter_context(named_lock(conn, "graph:" + thread, timeout=0))
                return stack.pop_all()

        pending = asyncio.create_task(asyncio.to_thread(acquire))
        try:
            stack = await asyncio.shield(pending)
        except asyncio.CancelledError:
            stack = await pending
            await asyncio.to_thread(stack.close)
            raise
        try:
            yield
        finally:
            await asyncio.to_thread(stack.close)

    def _run(self, operation):
        with mysql_connection(self.dsn) as conn:
            try:
                with conn.cursor() as cur:
                    result = operation(cur)
                conn.commit()
                return result
            except BaseException:
                conn.rollback()
                raise

    @staticmethod
    def _config(thread, namespace, checkpoint):
        return {"configurable": {"thread_id": thread, "checkpoint_ns": namespace, "checkpoint_id": checkpoint}}

    def _tuple(self, cur, row):
        cur.execute(
            "SELECT task_id,channel,type,value FROM stylist_checkpoint_writes "
            "WHERE thread_id=%s AND checkpoint_ns=%s AND checkpoint_id=%s ORDER BY task_id,idx",
            (row["thread_id"], row["checkpoint_ns"], row["checkpoint_id"]),
        )
        return CheckpointTuple(
            self._config(row["thread_id"], row["checkpoint_ns"], row["checkpoint_id"]),
            self.serde.loads_typed((row["type"], row["checkpoint"])),
            json.loads(row["metadata"]),
            self._config(row["thread_id"], row["checkpoint_ns"], row["parent_checkpoint_id"])
            if row["parent_checkpoint_id"] else None,
            [(w["task_id"], w["channel"], self.serde.loads_typed((w["type"], w["value"]))) for w in cur.fetchall()],
        )

    async def aget_tuple(self, config):
        def read(cur):
            values = config["configurable"]
            sql = "SELECT * FROM stylist_checkpoints WHERE thread_id=%s AND checkpoint_ns=%s"
            args = [str(values["thread_id"]), values.get("checkpoint_ns", "")]
            if checkpoint_id := get_checkpoint_id(config):
                sql += " AND checkpoint_id=%s"
                args.append(checkpoint_id)
            cur.execute(sql + " ORDER BY checkpoint_id DESC LIMIT 1", args)
            row = cur.fetchone()
            return self._tuple(cur, row) if row else None

        return await asyncio.to_thread(self._run, read)

    async def alist(self, config, *, filter=None, before=None, limit=None):
        def read(cur):
            clauses, args = [], []
            if config:
                clauses.append("thread_id=%s")
                args.append(str(config["configurable"]["thread_id"]))
                if "checkpoint_ns" in config["configurable"]:
                    clauses.append("checkpoint_ns=%s")
                    args.append(config["configurable"]["checkpoint_ns"])
            if before:
                clauses.append("checkpoint_id<%s")
                args.append(get_checkpoint_id(before))
            sql = "SELECT * FROM stylist_checkpoints"
            if clauses:
                sql += " WHERE " + " AND ".join(clauses)
            cur.execute(sql + " ORDER BY checkpoint_id DESC", args)
            rows = cur.fetchall()
            selected = [r for r in rows if all(json.loads(r["metadata"]).get(k) == v for k, v in (filter or {}).items())]
            return [self._tuple(cur, r) for r in selected[:limit] if limit is None or limit > 0]

        for checkpoint in await asyncio.to_thread(self._run, read):
            yield checkpoint

    async def aput(self, config, checkpoint, metadata, new_versions):
        values = config["configurable"]
        thread, namespace = str(values["thread_id"]), values.get("checkpoint_ns", "")
        kind, blob = self.serde.dumps_typed(checkpoint)
        encoded = json.dumps(get_checkpoint_metadata(config, metadata), ensure_ascii=False)

        def write(cur):
            cur.execute(
                "INSERT INTO stylist_checkpoints "
                "(thread_id,checkpoint_ns,checkpoint_id,parent_checkpoint_id,type,checkpoint,metadata) "
                "VALUES(%s,%s,%s,%s,%s,%s,%s) ON DUPLICATE KEY UPDATE "
                "parent_checkpoint_id=VALUES(parent_checkpoint_id),type=VALUES(type),"
                "checkpoint=VALUES(checkpoint),metadata=VALUES(metadata)",
                (thread, namespace, checkpoint["id"], get_checkpoint_id(config), kind, blob, encoded),
            )

        await asyncio.to_thread(self._run, write)
        return self._config(thread, namespace, checkpoint["id"])

    async def aput_writes(self, config, writes, task_id, task_path=""):
        values = config["configurable"]

        def write(cur):
            for index, (channel, value) in enumerate(writes):
                kind, blob = self.serde.dumps_typed(value)
                update = ("channel=VALUES(channel),type=VALUES(type),value=VALUES(value)"
                          if channel in WRITES_IDX_MAP else "idx=idx")
                cur.execute(
                    "INSERT INTO stylist_checkpoint_writes "
                    "(thread_id,checkpoint_ns,checkpoint_id,task_id,idx,channel,type,value) "
                    "VALUES(%s,%s,%s,%s,%s,%s,%s,%s) ON DUPLICATE KEY UPDATE " + update,
                    (str(values["thread_id"]), values.get("checkpoint_ns", ""), get_checkpoint_id(config),
                     task_id, WRITES_IDX_MAP.get(channel, index), channel, kind, blob),
                )

        await asyncio.to_thread(self._run, write)

    async def adelete_thread(self, thread_id):
        def delete(cur):
            for table in ("stylist_checkpoint_writes", "stylist_checkpoints"):
                cur.execute(f"DELETE FROM {table} WHERE thread_id=%s", (str(thread_id),))

        await asyncio.to_thread(self._run, delete)
