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
        self.mysql = path.startswith("mysql://")
        if not self.postgres and not self.mysql:
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        with self.connection() as conn:
            schema = "schema_mysql.sql" if self.mysql else "schema.sql"
            conn.executescript(Path(__file__).with_name(schema).read_text())

    @contextmanager
    def connection(self):
        if self.mysql:
            from .mysql import MySQLConnection, mysql_connection, named_lock

            with mysql_connection(self.path) as conn, named_lock(conn, "store"):
                try:
                    yield MySQLConnection(conn)
                    conn.commit()
                except BaseException:
                    conn.rollback()
                    raise
            return
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

    def memory_book(self, owner):
        from .memory import decode_memory_book
        with self.connection() as conn:
            row = conn.execute("SELECT book_json FROM stylist_memory_books WHERE owner_id=?", (owner,)).fetchone()
        return decode_memory_book(row["book_json"] if row else None)[0]

    def save_memory_book(self, owner, book):
        from .memory import decode_memory_book, encode_memory_book, validate_clothing_book
        validate_clothing_book(book)
        with self.connection() as conn:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute("SELECT revision,book_json FROM stylist_memory_books WHERE owner_id=?", (owner,)).fetchone()
            if book.revision != (row["revision"] if row else 0):
                raise StylistError("memory_conflict", "手记已有新的修改。你的草稿仍在，请先重新读取，再合并想留下的内容。", 409)
            saved = book.model_copy(update={"revision": book.revision + 1}, deep=True)
            retired = decode_memory_book(row["book_json"] if row else None)[1]
            if row:
                conn.execute("UPDATE stylist_memory_books SET revision=?,book_json=? WHERE owner_id=?",
                             (saved.revision, encode_memory_book(saved, retired), owner))
            else:
                conn.execute("INSERT INTO stylist_memory_books(owner_id,revision,book_json) VALUES(?,?,?)",
                             (owner, saved.revision, encode_memory_book(saved, retired)))
        return saved

    def reserve(self, owner, request):
        # Omitted persona preserves the digest of requests created before this field existed.
        excluded = {"assistant_persona"} if request.assistant_persona is None else set()
        if request.companion_profile is None:
            excluded.add("companion_profile")
        if request.upload_action_id is None:
            excluded.add("upload_action_id")
        if not request.regenerate_outfit:
            excluded.add("regenerate_outfit")
        if request.regenerate_from_version is None:
            excluded.add("regenerate_from_version")
        excluded = {key: True for key in excluded}
        if request.companion_profile is not None:
            # Visual preferences neither change the task nor invalidate old request receipts.
            excluded["companion_profile"] = {"color_scheme"}
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

    def finish(self, owner, request, claim, state, reply, memory_save=None):
        with self.connection() as conn:
            conn.execute("BEGIN IMMEDIATE")
            result = conn.execute("UPDATE stylist_sessions SET version=?,state_json=?,active_claim=NULL,"
                                  "lease_until=0,updated_at=CURRENT_TIMESTAMP WHERE id=? AND owner_id=? AND active_claim=?",
                                  (reply.version, state.model_dump_json(), reply.conversation_id, owner, claim))
            if result.rowcount != 1:
                raise StylistError("request_superseded", "这次处理已失效，请刷新查看最新结果。", 409)
            from .memory import (
                MemoryEntry,
                automatic_preference,
                clothing_content,
                decode_memory_book,
                encode_memory_book,
                explicit_memory,
                memory_intent,
                strip_save_claims,
            )
            from .personas import memory_receipt
            content = clothing_content(memory_save.content) if memory_save else explicit_memory(request.message)
            feedback = automatic_preference(request.message) if content is None and any(
                token in request.message for token in ("保存", "手记", "记录")) else None
            if feedback:
                saved = conn.execute("SELECT book_json FROM stylist_memory_books WHERE owner_id=?", (owner,)).fetchone()
                existing, _ = decode_memory_book(saved["book_json"] if saved else None)
                if any(entry.content == feedback.content for entry in existing.entries):
                    content = feedback.content
            original_message = reply.message
            receipt = None
            if content is not None:
                row = conn.execute("SELECT book_json FROM stylist_memory_books WHERE owner_id=?", (owner,)).fetchone()
                book, retired = decode_memory_book(row["book_json"] if row else None)
                exists = any(entry.content == content for entry in book.entries)
                if content and book.enabled and not exists:
                    if len(book.entries) >= 30:
                        raise StylistError("memory_full", "手记已经写满 30 页，先到设置整理一下，再留下这件小事。", 409)
                    entry_id = "chat_" + hashlib.sha256(request.request_id.encode()).hexdigest()[:32]
                    book.entries.append(MemoryEntry(id=entry_id, content=content,
                                                   category="穿衣习惯"))
                    book.revision += 1
                    if row:
                        conn.execute("UPDATE stylist_memory_books SET revision=?,book_json=? WHERE owner_id=?",
                                     (book.revision, encode_memory_book(book, retired), owner))
                    else:
                        conn.execute("INSERT INTO stylist_memory_books(owner_id,revision,book_json) VALUES(?,?,?)",
                                     (owner, book.revision, encode_memory_book(book, retired)))
                    receipt = memory_receipt(request.assistant_persona)
                elif exists and (memory_intent(request.message) or feedback):
                    receipt = "这条穿搭信息已经在手记里了，不重复新增。"
                elif not book.enabled and memory_intent(request.message):
                    receipt = "手记参考已暂停，这次没有新增。想继续记录穿搭信息时，可以到设置打开。"
                if receipt or memory_save:
                    if receipt and clothing_content(request.message) != request.message.strip():
                        receipt += f"\n记下的穿搭部分：{content}"
                    body = "" if explicit_memory(request.message) is not None else strip_save_claims(reply.message)
                    reply.message = "\n\n".join(part for part in [receipt, body] if part)
                    if not reply.message:
                        reply.message = "这条穿搭信息已经在手记里了。" if exists else "这次先按你说的穿搭方向聊。"
            if reply.message != original_message:
                last = json.loads(state.messages[-1]["content"])
                last["message"] = reply.message
                state.messages[-1]["content"] = json.dumps(last, ensure_ascii=False)
                conn.execute("UPDATE stylist_sessions SET state_json=? WHERE id=? AND owner_id=?",
                             (state.model_dump_json(), reply.conversation_id, owner))
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

    def regeneration_source(self, owner, cid, version):
        """Read an owned, immutable result without rolling back the live conversation."""
        with self.connection() as conn:
            row = conn.execute("SELECT reply_json FROM stylist_messages WHERE conversation_id=? AND owner_id=? AND version=?",
                               (cid, owner, version)).fetchone()
            if not row:
                raise StylistError("regenerate_source_missing", "找不到这套搭配的原始记录，请重新打开对话后再试。", 404)
            reply = Reply.model_validate_json(row["reply_json"])
            if not reply.looks:
                # A try-on may reference a later chat turn that retained the prior outfit.
                rows = conn.execute("SELECT reply_json FROM stylist_messages WHERE conversation_id=? AND owner_id=? AND version<? ORDER BY version DESC",
                                    (cid, owner, version)).fetchall()
                for item in rows:
                    previous = Reply.model_validate_json(item["reply_json"])
                    if previous.looks:
                        reply = previous
                        break
            if not reply.looks:
                raise StylistError("regenerate_source_missing", "这条记录没有可重新生成的衣橱搭配。", 409)
            return SessionState(task=reply.task, mode=reply.mode, looks=reply.looks).model_dump(mode="json")

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
