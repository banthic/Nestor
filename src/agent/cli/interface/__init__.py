"""CLI interface module for Nestor."""

from .messages import Message, MessageHistory
from .panel import get_panel, render_panel, render_prompt_frame
from .prompt import FileReferenceCompleter, PromptArea, prompt_user
from .thinking import (
    DEFAULT_MAX_LENGTH,
    ThinkingMode,
    ThinkingStreamer,
    render_thinking,
)

__all__ = [
    "DEFAULT_MAX_LENGTH",
    "FileReferenceCompleter",
    "Message",
    "MessageHistory",
    "PromptArea",
    "ThinkingMode",
    "ThinkingStreamer",
    "get_panel",
    "prompt_user",
    "render_panel",
        "render_prompt_frame",
    "render_thinking",
]
