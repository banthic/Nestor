"""Discord server-rename tool.

The tool is dumb on purpose: it delegates the actual rename to a handler
registered by the Discord layer (which owns the guild object and event loop).
This keeps the tool registry free of Discord imports and testable offline.
"""

from collections.abc import Callable

RenameHandler = Callable[[str], str]

_rename_handler: RenameHandler | None = None


def set_rename_handler(handler: RenameHandler | None) -> None:
    """Register the callable used to rename the Discord server."""
    global _rename_handler
    _rename_handler = handler


def clear_rename_handler() -> None:
    """Remove the registered rename handler."""
    set_rename_handler(None)


def _rename_server(name: str) -> str:
    if _rename_handler is None:
        return "Renaming the server is not available in this context."
    return _rename_handler(name)


rename_server = {
    "type": "function",
    "function": {
        "name": "rename_server",
        "description": (
            "Rename the current Discord server. Use only when the user explicitly asks "
            "to change the server name. Returns a confirmation with the new name."
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
    "call": _rename_server,
}
