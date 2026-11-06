"""Remove obsolete duplicate nickname/gender settings, never account or history data.

Defaults to counting only. --apply removes only the two JSON keys in this
project's stylist_companion_profiles table, via the selected Stylist database.
"""
import argparse
import json

from stylist.config import Settings
from stylist.store import Store


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    store = Store(Settings.load().database)
    backend = 'PostgreSQL' if store.postgres else 'MySQL' if store.mysql else 'SQLite'
    if args.apply:
        count = store.remove_legacy_account_settings()
        print(f'{backend}: removed duplicate account keys from {count} companion settings records; no account/history data modified')
    else:
        with store.connection() as conn:
            count = sum(any(key in json.loads(row['profile_json']) for key in ('user_name', 'user_gender'))
                        for row in conn.execute('SELECT profile_json FROM stylist_companion_profiles').fetchall())
        print(f'{backend}: {count} companion settings records contain obsolete account keys; not removed (use --apply)')


if __name__ == '__main__':
    main()
