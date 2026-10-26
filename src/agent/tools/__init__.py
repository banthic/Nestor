from .access import (
    access,
    clear_permission_checker,
    require_permission,
    set_permission_checker,
)
from .add_reaction import add_reaction
from .ask_clarification import ask_clarification
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
from .create_announcement_draft import create_announcement_draft
from .create_poll import create_poll
from .create_thread import create_thread
from .discord_runtime import reset_discord_tool_handler, set_discord_tool_handler
from .edit_own_message import edit_own_message
from .finish_task import finish_task
from .get_channel_info import get_channel_info
from .get_current_time import get_current_time
from .get_member_info import get_member_info
from .get_member_roles import get_member_roles
from .get_message_context import get_message_context
from .get_poll_results import get_poll_results
from .get_server_info import get_server_info
from .member_permissions import (
    clear_member_permissions_handler,
    get_member_permissions,
    set_member_permissions_handler,
)
from .publish_poll import publish_poll
from .quit import QuitRequested
from .rename_server import (
    clear_rename_handler,
    rename_server,
    set_rename_handler,
)
from .reply_to_message import reply_to_message
from .select_options import (
    clear_select_options_handler,
    select_options,
    set_select_options_handler,
)
from .send_dm import send_dm
from .send_message import send_message
from .webfetch import web_fetch
from .websearch import web_search

__all__ = [
    "DISCORD_TOOLS",
    "TOOLS",
    "QuitRequested",
    "access",
    "add_reaction",
    "ask_clarification",
    "ask_user",
    "clear_ask_handler",
    "clear_confirm_handler",
    "clear_member_permissions_handler",
    "clear_permission_checker",
    "clear_rename_handler",
    "clear_select_options_handler",
    "confirm",
    "create_announcement_draft",
    "create_poll",
    "create_thread",
    "edit_own_message",
    "execute_tool",
    "finish_task",
    "get_channel_info",
    "get_current_time",
    "get_member_info",
    "get_member_permissions",
    "get_member_roles",
    "get_message_context",
    "get_poll_results",
    "get_server_info",
    "get_tools",
    "publish_poll",
    "rename_server",
    "reply_to_message",
    "require_permission",
    "reset_discord_tool_handler",
    "select_options",
    "send_dm",
    "send_message",
    "set_ask_handler",
    "set_confirm_handler",
    "set_member_permissions_handler",
    "set_discord_tool_handler",
    "set_permission_checker",
    "set_rename_handler",
    "set_select_options_handler",
    "to_schemas",
    "web_fetch",
    "web_search",
]

TOOLS = [rename_server, web_search, web_fetch]
DISCORD_TOOLS = [get_message_context, get_channel_info, get_server_info, get_current_time, send_message, reply_to_message, add_reaction, create_thread, edit_own_message, send_dm, get_member_info, get_member_roles, create_announcement_draft, create_poll, publish_poll, get_poll_results, ask_clarification, finish_task]


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
