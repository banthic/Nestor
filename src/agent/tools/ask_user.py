"""Tool that asks the user for missing information.

When the model lacks a required detail, it calls this tool instead of guessing.
The Discord layer turns it into an interactive prompt: a selector for
multiple-choice questions, or a text input for free-form answers.
"""

from collections.abc import Callable
from contextvars import ContextVar

AskHandler = Callable[..., str]

_ask_handler: ContextVar[AskHandler | None] = ContextVar(
    "nestor_ask_handler", default=None
)


def set_ask_handler(handler: AskHandler | None) -> None:
    """Register the callable used to ask the user a question."""
    _ask_handler.set(handler)


def clear_ask_handler() -> None:
    """Remove the registered ask handler."""
    set_ask_handler(None)


def _ask_user(
    question: str,
    options: list[str] | None = None,
    allow_free_text: bool = True,
) -> str:
    handler = _ask_handler.get()
    if handler is None:
        return "Interactive questions are not available in this context."
    safe_options = (
        [text for option in options if (text := str(option).strip())]
        if isinstance(options, list)
        else []
    )
    return handler(
        question=str(question),
        options=safe_options,
        allow_free_text=bool(allow_free_text),
    )


ask_user = {
    "type": "function",
    "function": {
        "name": "ask_user",
        "description": (
            "Ask the user for information you are missing and wait for the answer. "
            "Never guess a required detail: call this tool instead. Pass 'options' "
            "to show a multiple-choice selector; omit them to request a free-text "
            "answer. Then use the answer to continue the task."
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
                    "maxItems": 25,
                    "description": (
                        "Choices to display in a selector. Omit for a free-text input."
                    ),
                },
                "allow_free_text": {
                    "type": "boolean",
                    "description": (
                        "When options are provided, also allow a typed answer. "
                        "Defaults to true."
                    ),
                },
            },
            "required": ["question"],
        },
    },
    "call": _ask_user,
}
