"""Tool that reports the Discord permissions of a guild member.

The lookup itself belongs to the Discord layer: this module only defines the
schema and delegates to a handler registered while a request is running.
"""

from collections.abc import Callable
from contextvars import ContextVar

MemberPermissionsHandler = Callable[[str | None], str]

_member_permissions_handler: ContextVar[MemberPermissionsHandler | None] = ContextVar(
    "nestor_member_permissions_handler", default=None
)


def set_member_permissions_handler(handler: MemberPermissionsHandler | None) -> None:
    """Register the callable used to inspect a member's permissions."""
    _member_permissions_handler.set(handler)


def clear_member_permissions_handler() -> None:
    """Remove the registered permissions handler."""
    set_member_permissions_handler(None)


def _get_member_permissions(member: str | None = None) -> str:
    handler = _member_permissions_handler.get()
    if handler is None:
        return "Permission lookup is not available in this context."
    target = str(member).strip() if member is not None else None
    return handler(target or None)


get_member_permissions = {
    "type": "function",
    "function": {
        "name": "get_member_permissions",
        "description": (
            "Show a member's Discord roles and permissions. Omit 'member' to inspect "
            "the person asking. Use it only when the user asks about someone's roles "
            "or what they are allowed to do. Permission enforcement before actions is "
            "automatic through require_permission in src/agent/tools/access.py, so do "
            "not call this tool to pre-check an action. Looking up another member "
            "requires the Manage Server permission."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "member": {
                    "type": "string",
                    "description": (
                        "Member to inspect: a mention, a user id, or a display name. "
                        "Omit it to inspect the current user."
                    ),
                }
            },
        },
    },
    "call": _get_member_permissions,
}
