from .quit import QuitRequested
from .rename_server import (
    clear_rename_handler,
    rename_server,
    set_rename_handler,
)

__all__ = [
    "TOOLS",
    "QuitRequested",
    "clear_rename_handler",
    "execute_tool",
    "get_tools",
    "rename_server",
    "set_rename_handler",
    "to_schemas",
]

TOOLS = [rename_server]


def get_tools():
    return TOOLS


def to_schemas(tools=None):
    return [
        {key: value for key, value in tool.items() if key != "call"}
        for tool in (tools or TOOLS)
    ]


def execute_tool(tools, name, arguments):
    for tool in tools:
        if tool["function"]["name"] == name:
            return str(tool["call"](**arguments))
    raise KeyError(f"Unknown tool: {name}")
