"""MySQL connections for the stylist's own data domain (never legacy tables)."""
import hashlib
from contextlib import contextmanager
from urllib.parse import unquote, urlsplit

import pymysql

from .errors import StylistError


@contextmanager
def mysql_connection(dsn):
    url = urlsplit(dsn)
    database = unquote(url.path.lstrip("/"))
    if url.scheme != "mysql" or not database or url.query or url.fragment:
        raise ValueError("MySQL 连接应为 mysql://用户名:密码@主机:端口/独立数据库，不支持查询参数。")
    if database.lower() in {"aicloset_dev", "aicloset_test", "mysql", "sys", "information_schema", "performance_schema"}:
        raise ValueError("请为 stylist 使用独立数据库，不能使用旧服务或系统数据库。")
    conn = pymysql.connect(
        host=url.hostname or "127.0.0.1", port=url.port or 3306,
        user=unquote(url.username or ""), password=unquote(url.password or ""),
        database=database, charset="utf8mb4", cursorclass=pymysql.cursors.DictCursor,
        autocommit=False, connect_timeout=10, read_timeout=30, write_timeout=30,
        # Match SQLite/PostgreSQL UPDATE rowcount semantics even when values stay equal.
        client_flag=pymysql.constants.CLIENT.FOUND_ROWS,
    )
    try:
        yield conn
    finally:
        conn.close()


@contextmanager
def named_lock(conn, key, timeout=5):
    # MySQL locks are server-wide; include the database to isolate local test databases.
    name = "stylist:" + hashlib.sha256(conn.db + b":" + key.encode()).hexdigest()[:55]
    with conn.cursor() as cur:
        cur.execute("SELECT GET_LOCK(%s,%s) AS locked", (name, timeout))
        if cur.fetchone()["locked"] != 1:
            raise StylistError("request_in_progress", "任务仍在执行，请稍后重试。", 409)
    try:
        yield
    finally:
        with conn.cursor() as cur:
            cur.execute("SELECT RELEASE_LOCK(%s)", (name,))


class MySQLConnection:
    def __init__(self, conn):
        self.conn = conn

    def execute(self, sql, args=()):
        if sql == "BEGIN IMMEDIATE":
            sql = "SELECT 1"  # connection() already holds the cross-process store lock.
        sql = sql.replace(
            "ON CONFLICT(owner_id) DO UPDATE SET profile_json=excluded.profile_json,updated_at=CURRENT_TIMESTAMP",
            "ON DUPLICATE KEY UPDATE profile_json=VALUES(profile_json),updated_at=CURRENT_TIMESTAMP",
        ).replace(
            "ON CONFLICT(owner_id,request_id) DO UPDATE SET status='processing',response_json=NULL",
            "ON DUPLICATE KEY UPDATE status='processing',response_json=NULL",
        )
        cur = self.conn.cursor()
        cur.execute(sql.replace("?", "%s"), args)
        return cur

    def executescript(self, sql):
        for statement in sql.split(";"):
            if statement.strip():
                with self.conn.cursor() as cur:
                    cur.execute(statement)
