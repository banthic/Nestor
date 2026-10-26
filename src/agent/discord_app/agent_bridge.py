"""Bridge between Discord messages and the Nestor Gateway.

The Discord surface only exposes Discord-scoped tools: checking access,
confirming actions, renaming the server, reading a member's permissions, and
asking the user for missing information. Actions declare the permission they
require, and the bridge registers the requesting member's checker for the
duration of the tool loop. Host-file tools are never passed to the gateway, so
a Discord message cannot touch the machine running the bot.
"""

import asyncio
import uuid
from collections.abc import Callable
from dataclasses import dataclass

import discord

from ..gateway import Gateway
from ..gateway.config import load_config
from ..observability import log_event, request_context
from ..tools import (
    DISCORD_TOOLS as TOOL_DEFINITIONS,
)
from ..tools import (
    access,
    ask_user,
    clear_ask_handler,
    clear_confirm_handler,
    clear_member_permissions_handler,
    clear_permission_checker,
    clear_rename_handler,
    clear_select_options_handler,
    confirm,
    get_member_permissions,
    rename_server,
    reset_discord_tool_handler,
    select_options,
    set_ask_handler,
    set_confirm_handler,
    set_discord_tool_handler,
    set_member_permissions_handler,
    set_permission_checker,
    set_rename_handler,
    set_select_options_handler,
    web_fetch,
    web_search,
)
from .settings import get_system_prompt

MAX_HISTORY_MESSAGES = 20
DISCORD_MESSAGE_LIMIT = 2000
ASK_TIMEOUT = 200
_BASE_DISCORD_TOOLS = [
    rename_server,
    access,
    confirm,
    select_options,
    get_member_permissions,
    ask_user,
    web_search,
    web_fetch,
]
DISCORD_TOOLS = [*_BASE_DISCORD_TOOLS, *TOOL_DEFINITIONS]

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
    request_id: str | None = None


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
        normalized = query.strip().removeprefix("@").casefold()
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

        # The model may pass a display form such as "@niceware" instead of a
        # Discord mention (which would contain the user's numeric ID).
        query = query.strip()
        if query.startswith("@"):
            query = query[1:].strip()

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
                log_event(
                    "discord.member_lookup.not_found",
                    guild_id=getattr(guild, "id", None),
                    member_id=member_id,
                    lookup="fetch_member",
                )
                return None
            except (discord.HTTPException, discord.ClientException) as exc:
                log_event(
                    "discord.member_lookup.fetch_failed",
                    level=40,
                    guild_id=getattr(guild, "id", None),
                    member_id=member_id,
                    discord_code=getattr(exc, "code", None),
                    http_status=getattr(exc, "status", None),
                    error=str(exc),
                )
                # A numeric ID is unambiguous. Searching by its digits would
                # require the privileged members intent and cannot improve it.
                return None

        query = query.strip()
        if query.startswith("@"):
            query = query[1:].strip()

        try:
            matches = await guild.query_members(query=query, limit=10)
        except (discord.HTTPException, discord.ClientException, TimeoutError):
            return None

        needle = query.casefold()
        for candidate in matches:
            if needle in {
                candidate.name.casefold(),
                candidate.display_name.casefold(),
                getattr(candidate, "global_name", "").casefold(),
            }:
                return candidate
        # Never DM or moderate an arbitrary first search result.
        return None

    def _lookup_member(
        self,
        guild: discord.Guild,
        query: str,
        loop: asyncio.AbstractEventLoop | None,
        requester: discord.Member | None = None,
        known_members=(),
    ) -> discord.Member | None:
        if requester is not None and self._is_self(query, requester):
            return requester
        member_id = self._member_id(query)
        normalized_query = query.strip().removeprefix("@").casefold()
        for candidate in known_members:
            if member_id is not None and getattr(candidate, "id", None) == member_id:
                return candidate
            if normalized_query in {
                getattr(candidate, "name", "").casefold(),
                getattr(candidate, "display_name", "").casefold(),
                getattr(candidate, "global_name", "").casefold(),
            }:
                return candidate
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
        return f"**{member.display_name}**\nRoles: {roles}\nPermissions: {granted}"

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

    def _multi_selector(
        self,
        channel: discord.abc.Messageable | None,
        member: discord.Member,
    ) -> Callable[..., str]:
        loop = self._event_loop()

        def handler(
            question: str,
            options: list[str] | None = None,
            allow_free_text: bool = False,
        ) -> str:
            if channel is None:
                return "Interactive multi-select is not available in this context."
            if loop is None:
                return "Interactive multi-select is not available right now."
            safe_options = [text for option in (options or []) if (text := str(option).strip())]
            if not safe_options:
                return "At least one option is required."

            from .ui.select_options import select_options_in_channel

            async def _do() -> str:
                return await select_options_in_channel(
                    channel,
                    member,
                    question,
                    safe_options,
                    allow_free_text,
                )

            try:
                future = asyncio.run_coroutine_threadsafe(_do(), loop)
                return future.result(timeout=ASK_TIMEOUT)
            except TimeoutError:
                return "The user did not answer in time."
            except RuntimeError:
                return "Interactive multi-select is not available right now."
            except discord.HTTPException as exc:
                return f"I couldn't ask for selection: {exc}"

        return handler

    def _runtime_handler(self, guild, member, channel, prompt, source_message=None, bot_user=None):
        """Bind Discord community actions to the current request's context."""
        loop = self._event_loop()
        known_members = tuple(getattr(source_message, "mentions", ()) or ())

        def lookup_member(query):
            return self._lookup_member(
                guild, query, loop, requester=member, known_members=known_members
            )

        def handler(name, args):
            if name == "get_message_context": return prompt
            if name == "get_channel_info": return f"Channel {getattr(channel, 'name', 'unknown')} (ID {getattr(channel, 'id', 'unknown')}, {getattr(channel, 'type', 'unknown')})."
            if name == "get_server_info": return f"Server {getattr(guild, 'name', 'unavailable')} (ID {getattr(guild, 'id', 'unavailable')}); members: {getattr(guild, 'member_count', 'unknown')}."
            if name == "ask_clarification": return self._asker(channel, member)(args["question"])
            if guild is None or channel is None: return "This tool requires a server channel."
            async def action():
                async def send_nestor_embed(text, reference=None):
                    chunks = [text[index : index + 4000] for index in range(0, len(text), 4000)] or [" "]
                    sent = None
                    for index, chunk in enumerate(chunks):
                        embed = discord.Embed(description=chunk, color=discord.Color.blurple())
                        embed.set_author(name="Nestor")
                        sent = await channel.send(
                            embed=embed,
                            reference=reference if index == 0 else None,
                        )
                    return sent
                if name == "send_message":
                    sent = await send_nestor_embed(args["content"]); return f"Message sent as an embed (ID {sent.id})."
                if name in {"reply_to_message", "add_reaction", "create_thread"}:
                    message = source_message
                    if message is None: return "Original message context is unavailable."
                    if name == "reply_to_message":
                        sent = await send_nestor_embed(args["content"], reference=message); return f"Reply sent as an embed (ID {sent.id})."
                    if name == "add_reaction": await message.add_reaction(args["emoji"]); return "Reaction added."
                    bot_member = guild.get_member(bot_user.id) if bot_user else None
                    if bot_member is None or not channel.permissions_for(bot_member).create_public_threads:
                        return "Discord action failed: the bot needs Create Public Threads in this channel."
                    thread = await message.create_thread(name=args["name"]); return f"Thread created: {thread.mention}"
                if name == "edit_own_message":
                    msg = await channel.fetch_message(int(args["message_id"]))
                    if bot_user is None or msg.author.id != bot_user.id: return "That message was not sent by this bot."
                    edited_embed = discord.Embed(description=args["content"] or " ", color=discord.Color.blurple())
                    edited_embed.set_author(name="Nestor")
                    await msg.edit(content=None, embed=edited_embed)
                    return "Message edited as an embed."
                if name in {"get_member_info", "get_member_roles", "send_dm"}:
                    target = lookup_member(args["member"])
                    if target is None: return "Member not found."
                    if name == "get_member_info": return f"{target.display_name} (@{target.name}), ID {target.id}, joined {target.joined_at}."
                    if name == "get_member_roles": return ", ".join(r.name for r in target.roles if not r.is_default()) or "No roles."
                    if name == "send_dm":
                        dm_embed = discord.Embed(description=args["content"] or " ", color=discord.Color.blurple())
                        dm_embed.set_author(name="Nestor")
                        await target.send(embed=dm_embed)
                        return "Direct message sent as an embed."
                if name == "create_announcement_draft": return f"**{args['title']}**\n{args['content']}"
                if name in {"create_poll", "publish_poll"}:
                    options = [str(option).strip() for option in args["options"]]
                    if not 2 <= len(options) <= 10: return "Native Discord polls need between 2 and 10 options."
                    if any(not option or len(option) > 55 for option in options): return "Each poll option must contain 1 to 55 characters."
                    question = str(args["question"]).strip()
                    if not question: return "A poll question is required."
                    from datetime import timedelta
                    duration_hours = int(args.get("duration_hours", 24))
                    if duration_hours not in {1, 4, 8, 24, 72, 168}:
                        return "Choose a native Discord poll duration of 1, 4, 8, 24, 72, or 168 hours."
                    poll = discord.Poll(
                        question,
                        duration=timedelta(hours=duration_hours),
                        multiple=bool(args.get("multiple", False)),
                    )
                    for option in options:
                        poll.add_answer(text=option)
                    poll_embed = discord.Embed(description=f"📊 **{question}**", color=discord.Color.blurple())
                    poll_embed.set_author(name="Nestor · sondage Discord")
                    sent = await channel.send(embed=poll_embed, poll=poll)
                    return f"Sondage natif Discord publié (message ID {sent.id}); durée {poll.duration.total_seconds() / 3600:g} h."
                if name == "get_poll_results":
                    msg = await channel.fetch_message(int(args["message_id"]))
                    if msg.poll is None: return "This message does not contain a native Discord poll."
                    return f"{msg.poll.question}\n" + "\n".join(f"{answer.text}: {answer.vote_count} vote(s)" for answer in msg.poll.answers) + f"\nTotal votes: {msg.poll.total_votes}"
                return f"Tool {name} is unavailable."
            if loop is None: return "Discord actions are unavailable in this context."
            try:
                return asyncio.run_coroutine_threadsafe(action(), loop).result(timeout=20)
            except (discord.HTTPException, discord.Forbidden) as exc:
                log_event(
                    "discord.tool.http_failed",
                    level=40,
                    tool=name,
                    guild_id=getattr(guild, "id", None),
                    channel_id=getattr(channel, "id", None),
                    discord_code=getattr(exc, "code", None),
                    http_status=getattr(exc, "status", None),
                    error=str(exc),
                )
                return f"Discord action failed: {exc}"
            except TimeoutError:
                log_event(
                    "discord.tool.timed_out",
                    level=40,
                    tool=name,
                    guild_id=getattr(guild, "id", None),
                    channel_id=getattr(channel, "id", None),
                    timeout_seconds=timeout,
                )
                return "Discord action timed out."
        return handler

    async def reply(
        self,
        channel_id: int,
        prompt: str,
        guild: discord.Guild | None = None,
        member: discord.Member | None = None,
        channel: discord.abc.Messageable | None = None,
        source_message: discord.Message | None = None,
        bot_user: discord.ClientUser | None = None,
    ) -> DiscordReply:
        """Run the gateway for one user message and return the assistant reply."""
        request_id = uuid.uuid4().hex
        session = self._session(channel_id)
        prior_history = session.trimmed()
        session.add_user(prompt)

        log_event(
            "discord.agent.request_received",
            request_id=request_id,
            guild_id=getattr(guild, "id", None),
            channel_id=channel_id,
            user_id=getattr(member, "id", None),
            prompt_chars=len(prompt),
            history_messages=len(prior_history),
        )

        handler_token = set_discord_tool_handler(self._runtime_handler(guild, member, channel, prompt, source_message, bot_user))
        gateway = Gateway(tools=DISCORD_TOOLS, system_prompt_suffix=get_system_prompt())

        if guild is not None:
            set_rename_handler(self._rename(guild))
        if member is not None:
            set_permission_checker(self._permission_checker(member))
            if guild is not None:
                set_member_permissions_handler(self._member_permissions(guild, member))
            set_ask_handler(self._asker(channel, member))
            set_confirm_handler(self._confirmer(channel, member))
            set_select_options_handler(self._multi_selector(channel, member))
        content_parts: list[str] = []
        error_holder: list[str] = []
        thinking_parts: list[str] = []
        usage_holder: list[dict[str, int] | None] = [None]
        tools_used: list[str] = []
        tools_seen: set[str] = set()
        tool_results: list[str] = []

        def _stream() -> None:
            with request_context(request_id):
                for chunk in gateway.stream_text(prompt, prior_history):
                    if chunk.type == "content":
                        content_parts.append(chunk.text)
                    elif chunk.type == "error":
                        content_parts.append(chunk.text)
                        error_holder.append(chunk.text)
                    elif chunk.type == "thinking":
                        thinking_parts.append(chunk.text)
                    elif chunk.type == "usage":
                        usage_holder[0] = chunk.usage or usage_holder[0]
                    elif chunk.type == "tool_result" and chunk.tool:
                        tool_results.append(f"{chunk.tool}: {chunk.text}")
                    elif (chunk.type in ("tool_call", "tool_result") and chunk.tool and chunk.tool not in tools_seen):
                        tools_seen.add(chunk.tool)
                        tools_used.append(chunk.tool)

        try:
            await asyncio.to_thread(_stream)
        finally:
            reset_discord_tool_handler(handler_token)
            clear_rename_handler()
            clear_permission_checker()
            clear_member_permissions_handler()
            clear_ask_handler()
            clear_confirm_handler()
            clear_select_options_handler()

        reply = "".join(content_parts).strip()
        if not reply:
            reply = (error_holder[0] if error_holder else "") or "I couldn't generate a reply."
        stored_reply = reply
        if tool_results:
            verified_results = "\n".join(tool_results)
            if len(verified_results) > 3000:
                verified_results = verified_results[:2997] + "..."
            stored_reply += f"\n\n[Verified tool results from this turn]\n{verified_results}"
        session.add_assistant(stored_reply)

        log_event(
            "discord.agent.request_completed",
            request_id=request_id,
            guild_id=getattr(guild, "id", None),
            channel_id=channel_id,
            user_id=getattr(member, "id", None),
            tools_used=tools_used,
            tool_result_count=len(tool_results),
            response_chars=len(reply),
            failed=bool(error_holder),
            error=error_holder[0] if error_holder else None,
        )

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
            request_id=request_id,
        )


__all__ = ["DISCORD_TOOLS", "AgentBridge", "DiscordReply", "split_message"]


def split_message(text: str, limit: int = DISCORD_MESSAGE_LIMIT) -> list[str]:
    """Split a reply into chunks that fit Discord's message length limit."""
    if len(text) <= limit:
        return [text]
    return [text[i : i + limit] for i in range(0, len(text), limit)]
