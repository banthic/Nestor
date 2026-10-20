"""Embed builders and UI helpers for Discord replies."""

import io

import discord

from ..agent_bridge import DiscordReply


def _footer_text(reply: DiscordReply) -> str:
    parts = []
    provider = reply.provider or "unknown"
    model = reply.model or "unknown"
    parts.append(f"{provider} · {model}")
    usage = reply.usage or {}
    if usage:
        prompt = usage.get("prompt_tokens") or usage.get("prompt") or 0
        completion = usage.get("completion_tokens") or usage.get("completion") or 0
        total = usage.get("total_tokens") or usage.get("total") or (prompt + completion)
        parts.append(f"tokens in {prompt} · out {completion} · total {total}")
    return " · ".join(parts)


def build_reply_embed(reply: DiscordReply, chunk_index: int = 0, chunk_count: int = 1) -> discord.Embed:
    embed = discord.Embed(
        description=reply.content or " ",
        color=discord.Color.blurple() if not reply.error else discord.Color.red(),
    )
    embed.set_author(name="Nestor")
    if reply.tools_used:
        embed.add_field(
            name="🔧 Tools",
            value="\n".join(f"• {tool}" for tool in reply.tools_used),
            inline=False,
        )
    if chunk_count > 1:
        embed.set_footer(text=f"{_footer_text(reply)} · part {chunk_index + 1}/{chunk_count}")
    else:
        embed.set_footer(text=_footer_text(reply))
    return embed


def thinking_file(reply: DiscordReply) -> discord.File | None:
    if not reply.thinking:
        return None
    bio = io.BytesIO(reply.thinking.encode("utf-8"))
    return discord.File(bio, filename="nestor-thinking.txt")
