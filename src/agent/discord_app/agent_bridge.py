"""Bridge between Discord messages and the Nestor Gateway.

The Discord surface only exposes Discord-scoped tools (currently renaming the
server). The host-file tools are never passed to the gateway, so a Discord
message cannot touch the machine running the bot.
"""

import asyncio
from collections.abc import Callable
from dataclasses import dataclass

import discord

from ..gateway import Gateway
from ..gateway.config import load_config
from ..tools import rename_server, set_rename_handler
from .settings import get_system_prompt

MAX_HISTORY_MESSAGES = 20
DISCORD_MESSAGE_LIMIT = 2000
DISCORD_TOOLS = [rename_server]


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

    def _rename(self, guild: discord.Guild) -> Callable[[str], str]:
        loop = self._loop
        if loop is None:
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                loop = None

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

    async def reply(
        self,
        channel_id: int,
        prompt: str,
        guild: discord.Guild | None = None,
    ) -> DiscordReply:
        """Run the gateway for one user message and return the assistant reply."""
        session = self._session(channel_id)
        session.add_user(prompt)

        if guild is not None:
            set_rename_handler(self._rename(guild))

        gateway = Gateway(tools=DISCORD_TOOLS, system_prompt_suffix=get_system_prompt())
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
            set_rename_handler(None)

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
