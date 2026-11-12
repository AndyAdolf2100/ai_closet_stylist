"""Read-only PostgreSQL schema preflight; operations execute SQL manually."""
import argparse
import asyncio
import os

from .config import Settings
from .schema_migrations import DATABASES, run


async def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--environment', choices=sorted(DATABASES))
    args = parser.parse_args()
    settings = Settings.load()
    check_only = args.check or os.getenv('STYLIST_REQUIRE_MIGRATIONS', '').lower() in {'true', '1'}
    if check_only and settings.database.startswith(('postgres://', 'postgresql://')):
        from psycopg.conninfo import conninfo_to_dict
        try:
            name = conninfo_to_dict(settings.database).get('dbname')
            environment = args.environment or next((e for e, db in DATABASES.items() if db == name), None)
            count = run(settings.database, environment)
            if settings.checkpoint_database and settings.checkpoint_database != settings.database:
                run(settings.checkpoint_database, environment)
        except Exception as error:
            # SQL/libpq errors may include DSNs or input text; keep stdout safe.
            print('Migration check failed: ' + type(error).__name__ + '. Verify operations SQL baseline and selected database.')
            return 1
        print(f'PostgreSQL baseline tables verified: {count}; environment={environment}.')
        return 0
    if check_only:
        print('SQL baseline mode requires PostgreSQL.')
        return 1
    # Keep isolated SQLite/MySQL development compatibility.
    from .store import Store
    from .engine import Stylist
    store = Store(settings.database)
    engine = Stylist(settings, store, None)
    async with engine.checkpoints() as saver:
        await saver.setup()
    return 0


if __name__ == '__main__':
    raise SystemExit(asyncio.run(main()))
