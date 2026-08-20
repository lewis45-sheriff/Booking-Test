"""
Minimal test settings that override the PostgreSQL database with SQLite.
Used so that pure-function property tests (which need no DB) can run
without requiring a live PostgreSQL connection or psycopg2.
"""
from config.settings import *  # noqa: F401, F403

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    }
}
