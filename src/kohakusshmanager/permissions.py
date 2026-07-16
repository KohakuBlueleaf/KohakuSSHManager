"""Role checks and the access-approval decision function."""

from kohakusshmanager.auth import Principal
from kohakusshmanager.models import GroupMachine, GroupMember, Machine, User


def leader_machine_ids(user: User) -> set[int]:
    """Machine ids reachable through groups the user belongs to."""
    group_ids = [
        gm.group_id for gm in GroupMember.select().where(GroupMember.user == user)
    ]
    if not group_ids:
        return set()
    query = GroupMachine.select(GroupMachine.machine).where(
        GroupMachine.group.in_(group_ids)
    )
    return {gm.machine_id for gm in query}


def machine_in_leader_scope(user: User, machine: Machine) -> bool:
    return machine.id in leader_machine_ids(user)


def decide_access(principal: Principal, machine: Machine) -> tuple[str, str]:
    """Return (decision, reason) where decision in {"auto", "review", "reject"}."""
    if principal.is_admin:
        return "auto", "admin"
    user = principal.user
    if user is None or not user.enabled:
        return "reject", "user is disabled"
    if principal.role == "leader" and machine_in_leader_scope(user, machine):
        return "auto", "leader within assigned group scope"
    return "review", "member request requires admin approval"
