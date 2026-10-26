"""Request-scoped bridge from Discord tool modules to the active Discord session."""

from contextvars import ContextVar

DiscordToolHandler = object
_handler = ContextVar("nestor_discord_tool_handler", default=None)


def set_discord_tool_handler(handler):
    return _handler.set(handler)


def reset_discord_tool_handler(token):
    _handler.reset(token)


def execute_discord_tool(tool_name, **arguments):
    handler = _handler.get()
    if handler is None:
        return f"{tool_name} is unavailable outside a Discord request."
    return handler(tool_name, arguments)
