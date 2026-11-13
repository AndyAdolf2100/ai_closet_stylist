"""Read-only checks for the current operations-managed PostgreSQL baseline."""
from pathlib import Path
import re
import psycopg
from .database_preflight import connection_parameters

DIRECTORY = Path(__file__).with_name("migrations") / "postgresql"
DATABASES = {"dev": "aicloset_stylist", "test": "aicloset_stylist_test", "prod": "aicloset_stylist_prod"}


def verify_connection(connection):
    sql = (DIRECTORY / "001_initial.sql").read_text()
    tables = set(re.findall(r"CREATE TABLE IF NOT EXISTS (\w+)", sql))
    indexes = set(re.findall(r"CREATE INDEX IF NOT EXISTS (\w+)", sql))
    actual_tables = {row[0] for row in connection.execute(
        "SELECT tablename FROM pg_tables WHERE schemaname='public'")}
    actual_indexes = {row[0] for row in connection.execute(
        "SELECT indexname FROM pg_indexes WHERE schemaname='public'")}
    if tables - actual_tables or indexes - actual_indexes:
        raise ValueError("Required tables or indexes missing; execute 001_initial.sql on the selected database")
    return len(tables)


def run(dsn, environment):
    if environment not in DATABASES:
        raise ValueError("Environment must be dev, test or prod")
    parameters = connection_parameters(dsn, target=DATABASES[environment])
    with psycopg.connect(**parameters, autocommit=True) as connection:
        return verify_connection(connection)
