"""Deployment PostgreSQL check, run in the target server's container network."""
import argparse
import os
from urllib.parse import quote

import psycopg
from psycopg import sql
from psycopg.conninfo import conninfo_to_dict

TARGET = "aicloset_stylist"


def connection_parameters(dsn):
    if not dsn.startswith(("postgresql://", "postgres://")) or "REPLACE_" in dsn:
        raise ValueError("Configure a PostgreSQL STYLIST_DATABASE in private config/deploy.env")
    parameters = conninfo_to_dict(dsn)
    if parameters.get("dbname") != TARGET:
        raise ValueError("Deployment database must be aicloset_stylist; legacy databases are forbidden")
    parameters["connect_timeout"] = "5"
    return parameters


def check(dsn, create=False):
    parameters = connection_parameters(dsn)
    # libpq connection failures may lose SQLSTATE, including a missing database.
    # Check existence through the maintenance DB before opening the target.
    admin_parameters = {**parameters, "dbname": "postgres"}
    with psycopg.connect(**admin_parameters, autocommit=True) as admin:
        admin.execute("SET statement_timeout = '8s'")
        exists = admin.execute("SELECT 1 FROM pg_database WHERE datname=%s", (TARGET,)).fetchone()
        if not exists:
            if not create:
                raise ValueError("aicloset_stylist does not exist; run with --create-database")
            try:
                admin.execute(sql.SQL("CREATE DATABASE {} TEMPLATE template0 ENCODING 'UTF8'").format(sql.Identifier(TARGET)))
            except psycopg.errors.DuplicateDatabase:
                pass
    conn = psycopg.connect(**parameters, autocommit=True)
    with conn:
        conn.execute("SET statement_timeout = '8s'")
        tables = [r[0] for r in conn.execute("SELECT tablename FROM pg_tables WHERE schemaname='public'")]
        allowed = {"checkpoints", "checkpoint_blobs", "checkpoint_writes", "checkpoint_migrations"}
        if any(not table.startswith("stylist_") and table not in allowed for table in tables):
            raise ValueError("Target database contains unrelated tables; refusing to initialize it")
        can_create = conn.execute("SELECT has_schema_privilege(current_user, 'public', 'CREATE')").fetchone()[0]
        if not can_create:
            raise ValueError("Database account needs CREATE permission on aicloset_stylist.public")
        print("PostgreSQL connection verified: aicloset_stylist; schema initialization permitted.")


def safe_error(exc, dsn):
    message = str(exc)
    secrets = [dsn]
    try:
        parameters = conninfo_to_dict(dsn)
        for key in ("password", "user"):
            value = parameters.get(key)
            if value:
                secrets.extend((value, quote(value, safe="")))
    except psycopg.Error:
        return type(exc).__name__ + ": invalid connection configuration"
    for value in sorted(set(secrets), key=len, reverse=True):
        if value:
            message = message.replace(value, "[redacted]")
    return message[:2000]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--create-database", action="store_true")
    args = parser.parse_args()
    try:
        check(os.getenv("STYLIST_DATABASE", ""), args.create_database)
    except ValueError as exc:
        # Only locally generated errors are printed; libpq errors may contain credentials.
        print(str(exc) if not isinstance(exc, psycopg.Error) else "Invalid database configuration.")
        return 1
    except psycopg.Error as exc:
        print("PostgreSQL preflight failed: " + type(exc).__name__ + "; SQLSTATE=" + (exc.sqlstate or "none"))
        print(safe_error(exc, os.getenv("STYLIST_DATABASE", "")))
        print("Check container DNS, VPC route, outbound TCP 5432, RDS whitelist and database permissions.")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
