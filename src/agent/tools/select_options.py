"""Tool for multi-select questions using reactions as checkboxes."""

from collections.abc import Callable
from contextvars import ContextVar

SelectOptionsHandler = Callable[..., str]

_select_options_handler: ContextVar[SelectOptionsHandler | None] = ContextVar(
    "nestor_select_options_handler", default=None
)


def set_select_options_handler(handler: SelectOptionsHandler | None) -> None:
    """Register the callable used for multi-select prompts."""
    _select_options_handler.set(handler)


def clear_select_options_handler() -> None:
    """Remove the registered select options handler."""
    set_select_options_handler(None)


def _select_options(
    question: str,
    options: list[str],
    allow_free_text: bool = False,
) -> str:
    handler = _select_options_handler.get()
    if handler is None:
        return "Interactive multi-select is not available in this context."
    safe_options = [text for option in options if (text := str(option).strip())]
    if not safe_options:
        return "At least one option is required."
    return handler(
        question=str(question),
        options=safe_options,
        allow_free_text=bool(allow_free_text),
    )


select_options = {
    "type": "function",
    "function": {
        "name": "select_options",
        "description": (
            "Ask the user to pick one or more options using reaction-based checkboxes. "
            "Shows an embed with reactions per option, plus ✅ to confirm and ❌ to "
            "cancel. Use when the user wants to choose multiple features/choices. "
            "Never guess; call this instead when multiple selections are needed."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "question": {
                    "type": "string",
                    "description": "The question to display to the user.",
                },
                "options": {
                    "type": "array",
                    "items": {"type": "string"},
                    "minItems": 1,
                    "maxItems": 15,
                    "description": "Options to choose from (max 15).",
                },
                "allow_free_text": {
                    "type": "boolean",
                    "description": "Also allow adding a custom entry via text after selection.",
                    "default": False,
                },
            },
            "required": ["question", "options"],
        },
    },
    "call": _select_options,
}
