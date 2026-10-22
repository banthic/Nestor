from .access import (
    access,
    clear_permission_checker,
    require_permission,
    set_permission_checker,
)
from .ask_user import (
    ask_user,
    clear_ask_handler,
    set_ask_handler,
)
from .confirm import (
    clear_confirm_handler,
    confirm,
    set_confirm_handler,
)
from .member_permissions import (
    clear_member_permissions_handler,
    get_member_permissions,
    set_member_permissions_handler,
)
from .quit import QuitRequested
from .rename_server import (
    clear_rename_handler,
    rename_server,
    set_rename_handler,
)

__all__ = [
    "TOOLS",
    "QuitRequested",
    "access",
    "ask_user",
    "clear_ask_handler",
    "clear_confirm_handler",
    "clear_member_permissions_handler",
    "clear_permission_checker",
    "clear_rename_handler",
    "confirm",
    "execute_tool",
    "get_member_permissions",
    "get_tools",
    "rename_server",
    "require_permission",
    "set_ask_handler",
    "set_confirm_handler",
    "set_member_permissions_handler",
    "set_permission_checker",
    "set_rename_handler",
    "to_schemas",
]

TOOLS = [rename_server]


def get_tools():
    return TOOLS


def to_schemas(tools=None):
    return [
        {key: value for key, value in tool.items() if key not in ("call", "permission")}
        for tool in (tools or TOOLS)
    ]


def execute_tool(tools, name, arguments):
    for tool in tools:
        if tool["function"]["name"] == name:
            permission = tool.get("permission")
            if permission:
                denial = require_permission(permission)
                if denial:
                    return denial
            return str(tool["call"](**arguments))
    raise KeyError(f"Unknown tool: {name}")
