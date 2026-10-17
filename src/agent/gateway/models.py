from dataclasses import dataclass


@dataclass
class ModelResponse:
    """Final answer returned by the blocking generation path."""

    content: str
    thinking: str = ""


@dataclass
class StreamChunk:
    """A single unit of the streamed generation path.

    ``type`` is one of: ``status``, ``content``, ``thinking``, ``tool_call``,
    ``tool_result``, ``usage`` or ``error``.
    """

    type: str
    text: str
    usage: dict[str, int] | None = None
    tool: str | None = None
