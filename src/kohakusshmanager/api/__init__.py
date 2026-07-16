"""API router assembly (included under /api by app.py)."""

from fastapi import APIRouter

from kohakusshmanager.api import (
    access,
    actions,
    admin,
    auth,
    groups,
    keys,
    machines,
    storage,
    users,
)

api_router = APIRouter()
for _module in (auth, users, keys, machines, access, actions, groups, storage, admin):
    api_router.include_router(_module.router)
