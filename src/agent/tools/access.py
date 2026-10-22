"""Permission guard shared by tools that act on Discord.

Tools stay provider-independent: they never import ``discord``. The Discord
layer registers a checker for the duration of a request, and ``execute_tool``
runs it before every action that declares a required permission.

Handlers live in :class:`~contextvars.ContextVar` so concurrent Discord
channels never share another member's permission context.
"""

from collections.abc import Callable
from contextvars import ContextVar

PermissionChecker = Callable[[str], str | None]

_permission_checker: ContextVar[PermissionChecker | None] = ContextVar(
    "nestor_permission_checker", default=None
)


def set_permission_checker(checker: PermissionChecker | None) -> None:
    """Register the callable that verifies the current actor's permissions."""
    _permission_checker.set(checker)


def clear_permission_checker() -> None:
    """Remove the registered permission checker."""
    set_permission_checker(None)


def require_permission(permission: str) -> str | None:
    """Return a denial message when the actor lacks ``permission``.

    ``None`` means the action may proceed. When no checker is registered
    (for example in the CLI) the action is allowed, preserving offline use.
    """
    checker = _permission_checker.get()
    if checker is None:
        return None
    return checker(permission)


def _check_access(permission: str) -> str:
    if _permission_checker.get() is None:
        return "Permission checking is not available in this context."

    denial = require_permission(permission)
    if denial:
        return denial
    return f"The requesting member has the **{permission}** permission."


access = {
    "type": "function",
    "function": {
        "name": "access",
        "description": (
            "Check whether the requesting member has a required Discord permission "
            "before a sensitive or server-modifying action. Backed by require_permission "
            "in src/agent/tools/access.py. Never use ask_user for permission checks; "
            "ask_user is only for missing information or confirmation questions."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "permission": {
                    "type": "string",
                    "description": (
                        "Exact Discord permission name, for example manage_guild "
                        "(Manage Server) or kick_members."
                    ),
                }
            },
            "required": ["permission"],
        },
    },
    "call": _check_access,
}
