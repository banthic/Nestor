"""Discord server-rename tool.

The tool is dumb on purpose: it delegates the actual rename to a handler
registered by the Discord layer (which owns the guild object and event loop).
This keeps the tool registry free of Discord imports and testable offline.
"""

from collections.abc import Callable
from contextvars import ContextVar

RenameHandler = Callable[[str], str]

_rename_handler: ContextVar[RenameHandler | None] = ContextVar(
    "nestor_rename_handler", default=None
)


def set_rename_handler(handler: RenameHandler | None) -> None:
    """Register the callable used to rename the Discord server."""
    _rename_handler.set(handler)


def clear_rename_handler() -> None:
    """Remove the registered rename handler."""
    set_rename_handler(None)


def _rename_server(name: str) -> str:
    handler = _rename_handler.get()
    if handler is None:
        return "Renaming the server is not available in this context."
    return handler(name)


rename_server = {
    "type": "function",
    "function": {
        "name": "rename_server",
        "description": (
            "Rename the current Discord server. Use only when the user explicitly asks "
            "to change the server name and has confirmed it through ask_user. The "
            "required permission is enforced automatically by require_permission in "
            "src/agent/tools/access.py. Returns a confirmation with the new name."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "The new name for the Discord server.",
                }
            },
            "required": ["name"],
        },
    },
    "permission": "manage_guild",
    "call": _rename_server,
}
