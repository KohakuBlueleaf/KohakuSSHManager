"""All peewee models.

Conventions: explicit ``id = AutoField()``, ``created_at`` on every row, JSON
stored via ``JSONField`` (TextField + guarded json), composite uniqueness via
``Meta.indexes``. Owned rows cascade; rows that must survive their parent use
``SET NULL`` with ``null=True``.
"""

import json

from peewee import (
    AutoField,
    BigIntegerField,
    BlobField,
    BooleanField,
    CharField,
    DateTimeField,
    DeferredForeignKey,
    ForeignKeyField,
    IntegerField,
    Model,
    TextField,
)

from kohakusshmanager.db import db, utcnow


class JSONField(TextField):
    """TextField that transparently stores/loads JSON, guarding decode errors."""

    def db_value(self, value):
        if value is None:
            return None
        return json.dumps(value)

    def python_value(self, value):
        if value is None:
            return None
        try:
            return json.loads(value)
        except (TypeError, ValueError):
            return None


class BaseModel(Model):
    id = AutoField()
    created_at = DateTimeField(default=utcnow)

    class Meta:
        database = db


class User(BaseModel):
    username = CharField(unique=True)
    display_name = CharField(default="")
    password_hash = CharField()
    role = CharField(default="member")  # member | leader
    enabled = BooleanField(default=True)


class Session(BaseModel):
    token = CharField(unique=True)
    user = ForeignKeyField(User, backref="sessions", null=True, on_delete="CASCADE")
    is_admin = BooleanField(default=False)
    expires_at = DateTimeField()


class ManagementKey(BaseModel):
    public_key = TextField()
    ciphertext = BlobField()
    nonce = BlobField()
    active = BooleanField(default=True)


class SSHKey(BaseModel):
    user = ForeignKeyField(User, backref="keys", null=True, on_delete="SET NULL")
    public_key = TextField()
    fingerprint = CharField(unique=True)
    comment = CharField(default="")
    state = CharField(default="active")  # active | revoked | no_owner


class Machine(BaseModel):
    name = CharField(unique=True)
    address = CharField()
    port = IntegerField(default=22)
    management_user = CharField()
    host_key_fingerprint = CharField(null=True)
    enrolled = BooleanField(default=False)
    tags = JSONField(default=list)
    notes = TextField(default="")
    facts = JSONField(null=True)
    status = CharField(default="new")  # new | online | offline | error
    last_check_at = DateTimeField(null=True)
    last_error = TextField(null=True)


class LocalAccount(BaseModel):
    machine = ForeignKeyField(Machine, backref="accounts", on_delete="CASCADE")
    username = CharField()
    uid = IntegerField(null=True)
    gid = IntegerField(null=True)
    home = CharField(default="")
    shell = CharField(default="")
    user = ForeignKeyField(User, backref="accounts", null=True, on_delete="SET NULL")
    state = CharField(default="unmanaged")  # managed | adopted | unmanaged
    locked = BooleanField(null=True)
    groups = JSONField(default=list)
    present = BooleanField(default=True)
    key_file_archived = BooleanField(default=False)
    last_seen_at = DateTimeField(null=True)

    class Meta:
        indexes = ((("machine", "username"), True),)


class AccountKey(BaseModel):
    account = ForeignKeyField(LocalAccount, backref="account_keys", on_delete="CASCADE")
    key = ForeignKeyField(SSHKey, backref="account_keys", on_delete="CASCADE")
    observed = BooleanField(default=True)
    managed = BooleanField(default=False)
    origin = CharField(default="discovered")  # kohaku | discovered | archive

    class Meta:
        indexes = ((("account", "key"), True),)


class AccessRequest(BaseModel):
    user = ForeignKeyField(User, backref="requests", null=True, on_delete="SET NULL")
    machine = ForeignKeyField(Machine, backref="requests", on_delete="CASCADE")
    username = CharField()
    account = ForeignKeyField(
        LocalAccount, backref="requests", null=True, on_delete="SET NULL"
    )
    state = CharField(default="pending")
    # pending | approved | active | failed | rejected | revoked
    reason = CharField(default="")
    requested_by = CharField()
    decided_by = CharField(null=True)
    decided_at = DateTimeField(null=True)
    valid_until = DateTimeField(null=True)
    last_error = TextField(null=True)


class RemoteAction(BaseModel):
    action = CharField()
    actor = CharField()
    machine = ForeignKeyField(
        Machine, backref="actions", null=True, on_delete="SET NULL"
    )
    account = ForeignKeyField(
        LocalAccount, backref="actions", null=True, on_delete="SET NULL"
    )
    key = ForeignKeyField(SSHKey, backref="actions", null=True, on_delete="SET NULL")
    request = ForeignKeyField(
        AccessRequest, backref="actions", null=True, on_delete="SET NULL"
    )
    # Deferred FK: StorageMount is defined later in this module. Lets a scan
    # action record its exact mount so retry re-scans the right one.
    mount = DeferredForeignKey(
        "StorageMount", backref="actions", null=True, on_delete="SET NULL"
    )
    state = CharField(default="pending")
    # pending | running | succeeded | failed | interrupted
    input_summary = TextField(default="")
    result = JSONField(null=True)
    error = TextField(null=True)
    started_at = DateTimeField(null=True)
    finished_at = DateTimeField(null=True)


class AuditLog(BaseModel):
    actor = CharField()
    action = CharField()
    target = CharField(default="")
    detail = TextField(default="")


class Group(BaseModel):
    name = CharField(unique=True)
    description = TextField(default="")


class GroupMember(BaseModel):
    group = ForeignKeyField(Group, backref="members", on_delete="CASCADE")
    user = ForeignKeyField(User, backref="group_links", on_delete="CASCADE")

    class Meta:
        indexes = ((("group", "user"), True),)


class GroupMachine(BaseModel):
    group = ForeignKeyField(Group, backref="machines", on_delete="CASCADE")
    machine = ForeignKeyField(Machine, backref="group_links", on_delete="CASCADE")

    class Meta:
        indexes = ((("group", "machine"), True),)


class StorageMount(BaseModel):
    name = CharField()  # logical source name, e.g. "nas1"
    machine = ForeignKeyField(Machine, backref="mounts", on_delete="CASCADE")
    path = CharField()
    subdirs = JSONField(default=list)
    preferred = BooleanField(default=False)
    notes = TextField(default="")
    enabled = BooleanField(default=True)


class UsageRecord(BaseModel):
    mount = ForeignKeyField(StorageMount, backref="usage_records", on_delete="CASCADE")
    scope = CharField()  # total | owner | directory
    uid = IntegerField(null=True)
    owner_name = CharField(null=True)
    path = CharField(null=True)
    bytes = BigIntegerField(default=0)
    file_count = IntegerField(null=True)
    scanned_at = DateTimeField(default=utcnow)
    status = CharField(default="ok")  # ok | failed
    error = TextField(null=True)


ALL_MODELS = [
    User,
    Session,
    ManagementKey,
    SSHKey,
    Machine,
    LocalAccount,
    AccountKey,
    AccessRequest,
    RemoteAction,
    AuditLog,
    Group,
    GroupMember,
    GroupMachine,
    StorageMount,
    UsageRecord,
]
