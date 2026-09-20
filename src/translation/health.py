"""Read-only checks for the installed translation database."""

import sqlite3
from contextlib import closing

from .kaikki import SCHEMA_VERSION


def dictionary_is_healthy(path, *, full=False):
    if not path.is_file():
        return False
    try:
        with closing(sqlite3.connect(path.resolve().as_uri() + '?mode=ro', uri=True, timeout=5)) as db:
            if full and db.execute('PRAGMA quick_check').fetchall() != [('ok',)]:
                return False
            version = db.execute("SELECT value FROM metadata WHERE key='schema_version'").fetchone()
            row = db.execute('SELECT language, word, pos, target, value, priority FROM translations LIMIT 1').fetchone()
            return version == (SCHEMA_VERSION,) and row is not None
    except (OSError, sqlite3.Error):
        return False
