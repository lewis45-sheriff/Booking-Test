"""
Property test conftest — switches the Django DB backend to SQLite so
property tests (which test pure functions) can run without a PostgreSQL
server or the psycopg2 driver.
"""
import django
from django.test.utils import override_settings


def pytest_configure(config):
    """Override the database backend to SQLite before Django is set up."""
    from django.conf import settings as django_settings
    # Only patch if Django is already configured (pytest-django will have
    # applied DJANGO_SETTINGS_MODULE by the time conftest hooks run).
    try:
        if django_settings.configured:
            django_settings.DATABASES["default"] = {
                "ENGINE": "django.db.backends.sqlite3",
                "NAME": ":memory:",
            }
    except Exception:
        pass
