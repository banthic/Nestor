"""Bridge between Discord messages and the Nestor Gateway.

The Discord surface only exposes Discord-scoped tools: checking access,
confirming actions, renaming the server, reading a member's permissions, and
asking the user for missing information. Actions declare the permission they
require, and the bridge registers the requesting member's checker for the
duration of the tool loop. Host-file tools are never passed to the gateway, so
a Discord message cannot touch the machine running the bot.
"""

import asyncio
from collections.abc import Callable
from dataclasses import dataclass

import discord

from ..gateway import Gateway
from ..gateway.config import load_config
from ..tools import (
    access,
    ask_user,
    clear_ask_handler,
    clear_confirm_handler,
    clear_member_permissions_handler,
    clear_permission_checker,
    clear_rename_handler,
    confirm,
    get_member_permissions,
    rename_server,
    set_ask_handler,
    set_confirm_handler,
    set_member_permissions_handler,
    set_permission_checker,
    set_rename_handler,
)
from .settings import get_system_prompt

MAX_HISTORY_MESSAGES = 20
DISCORD_MESSAGE_LIMIT = 2000
ASK_TIMEOUT = 200
DISCORD_TOOLS = [
    rename_server,
    access,
    confirm,
    get_member_permissions,
    ask_user,
]

PERMISSION_LABELS = {
    "manage_guild": "Manage Server",
    "kick_members": "Kick Members",
    "ban_members": "Ban Members",
    "manage_channels": "Manage Channels",
    "manage_messages": "Manage Messages",
    "manage_roles": "Manage Roles",
    "manage_webhooks": "Manage Webhooks",
    "moderate_members": "Moderate Members",
}


@dataclass(slots=True)
class DiscordReply:
    """Result from the Discord agent bridge with usage and thinking."""

    content: str
    thinking: str = ""
    usage: dict[str, int] | None = None
    tools_used: list[str] | None = None
    provider: str = ""
    model: str = ""
    error: bool = False


class _ChannelSession:
    """In-memory conversation history for a single channel."""

    def __init__(self) -> None:
        self.history: list[dict[str, str]] = []

    def add_user(self, content: str) -> None:
        self.history.append({"role": "user", "content": content})

    def add_assistant(self, content: str) -> None:
        self.history.append({"role": "assistant", "content": content})

    def trimmed(self) -> list[dict[str, str]]:
        return self.history[-MAX_HISTORY_MESSAGES:]


class AgentBridge:
    """Per-channel gateway sessions exposing Discord-scoped tools only."""

    def __init__(self) -> None:
        self._sessions: dict[int, _ChannelSession] = {}
        self._loop: asyncio.AbstractEventLoop | None = None

    def bind_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        """Remember the bot's event loop so sync tools can schedule coroutines."""
        self._loop = loop

    def _session(self, channel_id: int) -> _ChannelSession:
        return self._sessions.setdefault(channel_id, _ChannelSession())

    def reset(self, channel_id: int) -> None:
        self._sessions.pop(channel_id, None)

    def _event_loop(self) -> asyncio.AbstractEventLoop | None:
        if self._loop is not None:
            return self._loop
        try:
            return asyncio.get_running_loop()
        except RuntimeError:
            return None

    def _rename(self, guild: discord.Guild) -> Callable[[str], str]:
        loop = self._event_loop()

        def handler(name: str) -> str:
            new_name = name.strip()
            if not new_name:
                return "No name was provided, so the server was not renamed."
            if loop is None:
                return "The server could not be renamed right now."

            async def _do() -> str:
                await guild.edit(name=new_name)
                return f"The server has been renamed to \"{new_name}\"."

            try:
                return asyncio.run_coroutine_threadsafe(_do(), loop).result(timeout=15)
            except (discord.Forbidden, discord.HTTPException) as exc:
                return f"The server could not be renamed: {exc}"

        return handler

    @staticmethod
    def _check_permission(member: discord.Member, permission: str) -> str | None:
        permissions = member.guild_permissions
        if permissions.administrator or getattr(permissions, permission, False):
            return None
        label = PERMISSION_LABELS.get(permission, permission.replace("_", " ").title())
        return f"You need the **{label}** permission to do that."

    def _permission_checker(self, member: discord.Member) -> Callable[[str], str | None]:
        def checker(permission: str) -> str | None:
            return self._check_permission(member, permission)

        return checker

    @staticmethod
    def _is_self(query: str, member: discord.Member) -> bool:
        normalized = query.casefold()
        if normalized in {"me", "self", "my", "moi"}:
            return True
        if query in {str(member.id), member.mention, f"<@{member.id}>", f"<@!{member.id}>"}:
            return True
        return normalized in {member.name.casefold(), member.display_name.casefold()}

    @staticmethod
    def _member_id(query: str) -> int | None:
        if query.startswith("<@") and query.endswith(">"):
            digits = query.strip("<@!>")
        elif query.isdigit():
            digits = query
        else:
            return None
        return int(digits) if digits.isdigit() else None

    @classmethod
    def _cached_member(cls, guild: discord.Guild, query: str) -> discord.Member | None:
        member_id = cls._member_id(query)
        if member_id is not None:
            found = guild.get_member(member_id)
            if found is not None:
                return found

        by_name = getattr(guild, "get_member_named", None)
        if by_name is not None:
            found = by_name(query)
            if found is not None:
                return found

        needle = query.casefold()
        for candidate in getattr(guild, "members", []):
            if needle in candidate.name.casefold() or needle in candidate.display_name.casefold():
                return candidate
        return None

    @classmethod
    async def _fetch_member(
        cls, guild: discord.Guild, query: str
    ) -> discord.Member | None:
        member_id = cls._member_id(query)
        if member_id is not None:
            try:
                return await guild.fetch_member(member_id)
            except discord.NotFound:
                return None
            except (discord.HTTPException, discord.ClientException):
                pass

        try:
            matches = await guild.query_members(query=query, limit=10)
        except (discord.HTTPException, discord.ClientException, TimeoutError):
            return None

        needle = query.casefold()
        for candidate in matches:
            if needle in {candidate.name.casefold(), candidate.display_name.casefold()}:
                return candidate
        return matches[0] if matches else None

    def _lookup_member(
        self,
        guild: discord.Guild,
        query: str,
        loop: asyncio.AbstractEventLoop | None,
    ) -> discord.Member | None:
        cached = self._cached_member(guild, query)
        if cached is not None:
            return cached

        if loop is None:
            return None
        try:
            future = asyncio.run_coroutine_threadsafe(
                self._fetch_member(guild, query), loop
            )
            return future.result(timeout=15)
        except (TimeoutError, RuntimeError):
            return None

    @classmethod
    def _format_permissions(cls, member: discord.Member) -> str:
        role_names = [
            role.name for role in getattr(member, "roles", []) if not role.is_default()
        ]
        roles = ", ".join(role_names) if role_names else "no roles"

        permissions = member.guild_permissions
        if permissions.administrator:
            granted = "administrator (all permissions)"
        else:
            granted = ", ".join(
                sorted(
                    PERMISSION_LABELS.get(name, name.replace("_", " ").title())
                    for name, value in permissions
                    if value
                )
            ) or "none"

        return (
            f"**{member.display_name}**\n"
            f"Roles: {roles}\n"
            f"Permissions: {granted}"
        )

    def _member_permissions(
        self, guild: discord.Guild, member: discord.Member
    ) -> Callable[[str | None], str]:
        loop = self._event_loop()

        def handler(target: str | None) -> str:
            query = (target or "").strip()
            if not query or self._is_self(query, member):
                return self._format_permissions(member)

            denial = self._check_permission(member, "manage_guild")
            if denial:
                return denial

            found = self._lookup_member(guild, query, loop)
            if found is None:
                return (
                    f"I couldn't find a member matching \"{query}\" on this server. "
                    "Try a mention or the member's numeric ID."
                )
            return self._format_permissions(found)

        return handler

    def _asker(
        self,
        channel: discord.abc.Messageable | None,
        member: discord.Member,
    ) -> Callable[..., str]:
        loop = self._event_loop()

        def handler(
            question: str,
            options: list[str] | None = None,
            allow_free_text: bool = True,
        ) -> str:
            if channel is None:
                return "Interactive questions are not available in this context."
            if loop is None:
                return "Interactive questions are not available right now."

            from .ui.ask import ask_user_in_channel

            async def _do() -> str:
                return await ask_user_in_channel(
                    channel,
                    member,
                    question,
                    options or [],
                    allow_free_text,
                )

            try:
                future = asyncio.run_coroutine_threadsafe(_do(), loop)
                return future.result(timeout=ASK_TIMEOUT)
            except TimeoutError:
                return "The user did not answer in time."
            except RuntimeError:
                return "Interactive questions are not available right now."
            except discord.HTTPException as exc:
                return f"I couldn't ask the user: {exc}"

        return handler

    def _confirmer(
        self,
        channel: discord.abc.Messageable | None,
        member: discord.Member,
    ) -> Callable[..., str]:
        loop = self._event_loop()

        def handler(action: str, details: str = "") -> str:
            if channel is None:
                return "Interactive confirmation is not available in this context."
            if loop is None:
                return "Interactive confirmation is not available right now."

            from .ui.confirm import confirm_in_channel

            async def _do() -> str:
                return await confirm_in_channel(
                    channel,
                    member,
                    action,
                    details,
                )

            try:
                future = asyncio.run_coroutine_threadsafe(_do(), loop)
                return future.result(timeout=ASK_TIMEOUT)
            except TimeoutError:
                return "The user did not confirm in time."
            except RuntimeError:
                return "Interactive confirmation is not available right now."
            except discord.HTTPException as exc:
                return f"I couldn't ask for confirmation: {exc}"

        return handler

    async def reply(
        self,
        channel_id: int,
        prompt: str,
        guild: discord.Guild | None = None,
        member: discord.Member | None = None,
        channel: discord.abc.Messageable | None = None,
    ) -> DiscordReply:
        """Run the gateway for one user message and return the assistant reply."""
        session = self._session(channel_id)
        session.add_user(prompt)

        gateway = Gateway(tools=DISCORD_TOOLS, system_prompt_suffix=get_system_prompt())

        if guild is not None:
            set_rename_handler(self._rename(guild))
        if member is not None:
            set_permission_checker(self._permission_checker(member))
            if guild is not None:
                set_member_permissions_handler(self._member_permissions(guild, member))
            set_ask_handler(self._asker(channel, member))
            set_confirm_handler(self._confirmer(channel, member))
        content_parts: list[str] = []
        error_holder: list[str] = []
        thinking_parts: list[str] = []
        usage_holder: list[dict[str, int] | None] = [None]
        tools_used: list[str] = []
        tools_seen: set[str] = set()

        def _stream() -> None:
            for chunk in gateway.stream_text(prompt, session.trimmed()):
                if chunk.type == "content":
                    content_parts.append(chunk.text)
                elif chunk.type == "error":
                    content_parts.append(chunk.text)
                    error_holder.append(chunk.text)
                elif chunk.type == "thinking":
                    thinking_parts.append(chunk.text)
                elif chunk.type == "usage":
                    usage_holder[0] = chunk.usage or usage_holder[0]
                elif (chunk.type in ("tool_call", "tool_result") and chunk.tool and chunk.tool not in tools_seen):
                    tools_seen.add(chunk.tool)
                    tools_used.append(chunk.tool)

        try:
            await asyncio.to_thread(_stream)
        finally:
            clear_rename_handler()
            clear_permission_checker()
            clear_member_permissions_handler()
            clear_ask_handler()
            clear_confirm_handler()

        reply = "".join(content_parts).strip()
        if not reply:
            reply = (error_holder[0] if error_holder else "") or "I couldn't generate a reply."
        session.add_assistant(reply)

        config = load_config()
        default_provider = config.get("default_provider", "")
        provider_cfg = config.get("provider", {})
        model = ""
        if default_provider == "external_api_openai_compatible":
            model = provider_cfg.get(default_provider, {}).get("model", gateway.openai_model or "")
        elif default_provider == "local_ollama":
            model = provider_cfg.get(default_provider, {}).get("model", gateway.ollama_model or "")

        return DiscordReply(
            content=reply,
            thinking="".join(thinking_parts).strip(),
            usage=usage_holder[0],
            tools_used=tools_used or None,
            provider=default_provider,
            model=model,
            error=bool(error_holder),
        )


__all__ = ["DISCORD_TOOLS", "AgentBridge", "DiscordReply", "split_message"]


def split_message(text: str, limit: int = DISCORD_MESSAGE_LIMIT) -> list[str]:
    """Split a reply into chunks that fit Discord's message length limit."""
    if len(text) <= limit:
        return [text]
    return [text[i : i + limit] for i in range(0, len(text), limit)]
