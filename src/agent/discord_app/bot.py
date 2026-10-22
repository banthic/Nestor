"""Discord client and bot entry point."""

import asyncio
import os

import discord
from discord import app_commands
from dotenv import load_dotenv
from rich.console import Console

from ..gateway.config import DOTENV_PATH
from .agent_bridge import AgentBridge
from .commands import register_commands
from .settings import get_chatbot_channel_id
from .ui import ThinkingView, build_reply_embed

console = Console()


class NestorBot(discord.Client):
    """Discord client: intents, slash command tree, lifecycle, chatbot replies."""

    def __init__(self) -> None:
        super().__init__(intents=build_intents())
        self.tree = app_commands.CommandTree(self)
        self.agent = AgentBridge()

    async def setup_hook(self) -> None:
        self.agent.bind_loop(asyncio.get_running_loop())
        register_commands(self.tree)
        guild_id = os.getenv("DISCORD_GUILD_ID")
        if guild_id:
            guild = discord.Object(id=int(guild_id))
            self.tree.copy_global_to(guild=guild)
            await self.tree.sync(guild=guild)
        else:
            await self.tree.sync()

    async def on_ready(self) -> None:
        console.print(
            f"[green]Logged in as {self.user} — {len(self.guilds)} guild(s).[/green]"
        )

    async def on_message(self, message: discord.Message) -> None:
        if message.author.bot or message.guild is None:
            return
        if message.content.startswith("/"):
            return

        chatbot_channel_id = get_chatbot_channel_id(message.guild.id)
        if chatbot_channel_id is None or message.channel.id != chatbot_channel_id:
            return

        async with message.channel.typing():
            reply = await self.agent.reply(
                message.channel.id,
                message.content,
                guild=message.guild,
                member=message.author,
                channel=message.channel,
            )

        if not reply.content:
            return

        chunks = [reply.content[i : i + 4000] for i in range(0, len(reply.content), 4000)]
        for idx, chunk in enumerate(chunks):
            embed = build_reply_embed(
                type(reply)(content=chunk, thinking=reply.thinking if idx == 0 else "", usage=reply.usage if idx == 0 else None, tools_used=reply.tools_used if idx == 0 else None, provider=reply.provider, model=reply.model, error=reply.error),
                chunk_index=idx,
                chunk_count=len(chunks),
            )
            view = ThinkingView(reply.thinking) if idx == 0 and reply.thinking else None
            await message.channel.send(embed=embed, view=view)


def build_intents() -> discord.Intents:
    """Bot intents: guilds plus message content for chatbot replies."""
    intents = discord.Intents.default()
    intents.message_content = True
    return intents


def run_bot() -> None:
    """Load the token from .env then start the bot."""
    load_dotenv(dotenv_path=DOTENV_PATH)
    token = os.getenv("DISCORD_TOKEN")
    if not token:
        raise SystemExit("DISCORD_TOKEN is missing: add it to the .env file at the repo root.")
    guild_id = os.getenv("DISCORD_GUILD_ID")
    if guild_id and not guild_id.isdigit():
        raise SystemExit("Invalid DISCORD_GUILD_ID: provide a numeric guild id.")
    NestorBot().run(token)
