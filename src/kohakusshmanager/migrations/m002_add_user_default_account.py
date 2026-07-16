"""Add User.default_account (preferred Unix account name).

Guarded so it is a no-op on a fresh database where m001's create_tables
already produced the column from the current model.
"""


def migrate(db):
    cols = {row[1] for row in db.execute_sql('PRAGMA table_info("user")').fetchall()}
    if "default_account" not in cols:
        db.execute_sql(
            'ALTER TABLE "user" ADD COLUMN default_account '
            "VARCHAR(255) NOT NULL DEFAULT ''"
        )
