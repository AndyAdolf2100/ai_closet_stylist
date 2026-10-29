import hashlib
import json
import sqlite3
import time
import uuid
from contextlib import contextmanager
from pathlib import Path

from .errors import StylistError
from .models import CompanionProfile, Reply, SessionState


class PostgresConnection:
    """Keep existing bound SQL statements portable; never interpolate values."""
    def __init__(self, conn):
        self.conn = conn

    def execute(self, sql, args=()):
        if sql == "BEGIN IMMEDIATE":
            return self.conn.execute("SELECT 1")
        return self.conn.execute(sql.replace("?", "%s"), args)

    def executescript(self, sql):
        for statement in sql.split(";"):
            if statement.strip() and not statement.strip().startswith("PRAGMA"):
                self.conn.execute(statement.replace("INTEGER PRIMARY KEY AUTOINCREMENT", "BIGSERIAL PRIMARY KEY")
                                  .replace(" REAL", " DOUBLE PRECISION"))


class Store:
    def __init__(self, path):
        self.path = path
        self.postgres = path.startswith(("postgres://", "postgresql://"))
        if not self.postgres:
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        with self.connection() as conn:
            conn.executescript(Path(__file__).with_name("schema.sql").read_text())

    @contextmanager
    def connection(self):
        if self.postgres:
            import psycopg
            from psycopg.rows import dict_row
            with psycopg.connect(self.path, row_factory=dict_row) as conn:
                # Short DB-only transactions. Shared across Pods, including image claims.
                conn.execute("SELECT pg_advisory_xact_lock(81294731)")
                yield PostgresConnection(conn)
            return
        conn = sqlite3.connect(self.path, timeout=5)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def companion_profile(self, owner):
        with self.connection() as conn:
            row = conn.execute("SELECT profile_json FROM stylist_companion_profiles WHERE owner_id=?", (owner,)).fetchone()
        return CompanionProfile.model_validate_json(row["profile_json"]) if row else None

    def save_companion_profile(self, owner, profile):
        with self.connection() as conn:
            conn.execute("INSERT INTO stylist_companion_profiles(owner_id,profile_json) VALUES(?,?) "
                         "ON CONFLICT(owner_id) DO UPDATE SET profile_json=excluded.profile_json,updated_at=CURRENT_TIMESTAMP",
                         (owner, profile.model_dump_json()))
        return profile

    def reserve(self, owner, request):
        # Omitted persona preserves the digest of requests created before this field existed.
        excluded = {"assistant_persona"} if request.assistant_persona is None else set()
        if request.companion_profile is None:
            excluded.add("companion_profile")
        digest = hashlib.sha256(request.model_dump_json(exclude=excluded).encode()).hexdigest()
        with self.connection() as conn:
            conn.execute("BEGIN IMMEDIATE")
            old = conn.execute("SELECT * FROM stylist_requests WHERE owner_id=? AND request_id=?",
                               (owner, request.request_id)).fetchone()
            if old:
                if old["digest"] != digest:
                    raise StylistError("idempotency_conflict", "同一请求编号不能用于不同内容。", 409)
                if old["status"] == "completed":
                    return None, None, None, Reply.model_validate_json(old["response_json"])
            cid = old["conversation_id"] if old else request.conversation_id
            if not cid:
                cid = "sty_" + uuid.uuid4().hex
                conn.execute("INSERT INTO stylist_sessions(id,owner_id,state_json) VALUES(?,?,?)",
                             (cid, owner, SessionState().model_dump_json()))
            row = conn.execute("SELECT * FROM stylist_sessions WHERE id=? AND owner_id=?", (cid, owner)).fetchone()
            if not row:
                raise StylistError("conversation_not_found", "找不到当前账号的这条对话。", 404)
            if row["version"] != request.expected_version:
                raise StylistError("stale_version", "对话已有更新，请刷新后继续。", 409)
            if row["active_claim"] and row["lease_until"] > time.time():
                raise StylistError("request_in_progress", "正在处理这条对话，请等待当前结果。", 409)
            claim = uuid.uuid4().hex
            conn.execute("UPDATE stylist_sessions SET active_claim=?, lease_until=? WHERE id=?",
                         (claim, time.time() + 45, cid))
            conn.execute("INSERT INTO stylist_requests VALUES(?,?,?,?,?,NULL) "
                         "ON CONFLICT(owner_id,request_id) DO UPDATE SET status='processing',response_json=NULL",
                         (owner, request.request_id, cid, digest, "processing"))
            return cid, claim, SessionState.model_validate_json(row["state_json"]), None

    def finish(self, owner, request, claim, state, reply):
        with self.connection() as conn:
            conn.execute("BEGIN IMMEDIATE")
            result = conn.execute("UPDATE stylist_sessions SET version=?,state_json=?,active_claim=NULL,"
                                  "lease_until=0,updated_at=CURRENT_TIMESTAMP WHERE id=? AND owner_id=? AND active_claim=?",
                                  (reply.version, state.model_dump_json(), reply.conversation_id, owner, claim))
            if result.rowcount != 1:
                raise StylistError("request_superseded", "这次处理已失效，请刷新查看最新结果。", 409)
            conn.execute("UPDATE stylist_requests SET status='completed',response_json=? WHERE owner_id=? AND request_id=?",
                         (reply.model_dump_json(), owner, request.request_id))
            conn.execute("INSERT INTO stylist_messages(conversation_id,owner_id,version,user_message,reply_json) VALUES(?,?,?,?,?)",
                         (reply.conversation_id, owner, reply.version, request.message, reply.model_dump_json()))

    def release(self, owner, cid, claim):
        with self.connection() as conn:
            conn.execute("UPDATE stylist_sessions SET active_claim=NULL,lease_until=0 WHERE id=? AND owner_id=? AND active_claim=?",
                         (cid, owner, claim))

    def renew(self, owner, cid, claim):
        with self.connection() as conn:
            changed = conn.execute("UPDATE stylist_sessions SET lease_until=? WHERE id=? AND owner_id=? AND active_claim=?",
                                   (time.time() + 45, cid, owner, claim))
            if changed.rowcount != 1:
                raise StylistError("request_superseded", "本次任务执行权已变化。", 409)

    def history(self, owner, cid):
        with self.connection() as conn:
            session = conn.execute("SELECT version FROM stylist_sessions WHERE id=? AND owner_id=?", (cid, owner)).fetchone()
            if not session:
                raise StylistError("conversation_not_found", "找不到当前账号的这条对话。", 404)
            rows = conn.execute("SELECT user_message,reply_json FROM stylist_messages WHERE conversation_id=? AND owner_id=? ORDER BY version",
                                (cid, owner)).fetchall()
            return {"conversation_id": cid, "version": session["version"], "messages": [
                {"user": r["user_message"], "reply": json.loads(r["reply_json"])} for r in rows]}

    def conversations(self, owner):
        with self.connection() as conn:
            rows = conn.execute(
                "SELECT s.id,s.version,s.updated_at,"
                "(SELECT m.user_message FROM stylist_messages m "
                "WHERE m.conversation_id=s.id AND m.owner_id=s.owner_id "
                "ORDER BY m.version ASC LIMIT 1) AS title "
                "FROM stylist_sessions s WHERE s.owner_id=? AND s.version>0 "
                "ORDER BY s.updated_at DESC LIMIT 50", (owner,)).fetchall()
            return [dict(r) for r in rows]
