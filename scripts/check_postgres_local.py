"""Run real PostgreSQL regressions only in a disposable local database."""
import os
import subprocess
import sys
import uuid
from urllib.parse import urlsplit, urlunsplit

import psycopg
from psycopg import sql

from stylist.config import Settings


def main():
    url = urlsplit(Settings.load().database)
    if url.scheme != "postgresql" or url.hostname != "127.0.0.1" or url.path != "/aicloset_stylist":
        raise RuntimeError("Run setup_postgres_local.py first; only local PostgreSQL is allowed")
    database = "stylist_tmp_" + uuid.uuid4().hex
    with psycopg.connect(url.geturl(), autocommit=True) as conn:
        conn.execute(sql.SQL("CREATE DATABASE {} TEMPLATE template0 ENCODING 'UTF8'").format(sql.Identifier(database)))
        try:
            env = dict(os.environ, STYLIST_TEST_POSTGRES_DSN=urlunsplit(url._replace(path="/" + database)))
            return subprocess.run([sys.executable, "-m", "pytest", "-q", "tests/test_postgres.py"], env=env).returncode
        finally:
            conn.execute(sql.SQL("DROP DATABASE {} WITH (FORCE)").format(sql.Identifier(database)))


if __name__ == "__main__":
    sys.exit(main())
