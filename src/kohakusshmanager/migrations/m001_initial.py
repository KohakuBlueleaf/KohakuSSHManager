"""Initial schema: create all tables."""

from kohakusshmanager.models import ALL_MODELS


def migrate(db):
    db.create_tables(ALL_MODELS, safe=True)
