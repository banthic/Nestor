"""Tool that asks the user to confirm a sensitive action.

Confirmation is deliberately separate from ``ask_user``: ``ask_user`` gathers
missing information and offers choices, while ``confirm`` only asks for a
yes/no decision before an action that changes the server.
"""

from collections.abc import Callable
from contextvars import ContextVar

ConfirmHandler = Callable[..., str]

_confirm_handler: ContextVar[ConfirmHandler | None] = ContextVar(
    "nestor_confirm_handler", default=None
)


def set_confirm_handler(handler: ConfirmHandler | None) -> None:
    """Register the callable used to request a confirmation."""
    _confirm_handler.set(handler)


def clear_confirm_handler() -> None:
    """Remove the registered confirm handler."""
    set_confirm_handler(None)


def _confirm(action: str, details: str = "") -> str:
    handler = _confirm_handler.get()
    if handler is None:
        return "Interactive confirmation is not available in this context."
    return handler(action=str(action), details=str(details or ""))


confirm = {
    "type": "function",
    "function": {
        "name": "confirm",
        "description": (
            "Ask the user to confirm a sensitive or server-modifying action. Shows "
            "an embed with Confirm and Cancel buttons, then waits for a yes/no "
            "decision. Use it after the access tool allows the action. Never use "
            "ask_user for confirmation; ask_user is only for missing information "
            "or choices."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "description": "The exact action to confirm.",
                },
                "details": {
                    "type": "string",
                    "description": "Optional impact or context shown in the embed.",
                },
            },
            "required": ["action"],
        },
    },
    "call": _confirm,
}
