"""Discord client and bot entry point."""

import asyncio
import os
import re

import discord
from discord import app_commands
from dotenv import load_dotenv
from rich.console import Console

from ..gateway.config import DOTENV_PATH
from ..observability import configure_logging, log_event, log_exception
from .agent_bridge import AgentBridge, DiscordReply
from .behavior_monitor import BehaviorMonitor
from .commands import register_commands
from .settings import get_chatbot_channel_id
from .ui import ThinkingView, build_reply_embed

console = Console()


def _is_directly_addressed(message: discord.Message, bot_user) -> bool:
    """Whether a guild message pings the bot or uses its name as a whole word."""
    if bot_user is not None and any(user.id == bot_user.id for user in message.mentions):
        return True

    names = {"nestor"}
    if bot_user is not None and getattr(bot_user, "name", None):
        names.add(bot_user.name)
    alternatives = "|".join(re.escape(name) for name in sorted(names, key=len, reverse=True))
    return re.search(rf"(?<!\w)(?:{alternatives})(?!\w)", message.content, re.IGNORECASE) is not None


class LoggingCommandTree(app_commands.CommandTree):
    """Capture slash-command failures in Nestor's internal log."""

    async def on_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError) -> None:
        log_exception(
            "discord.app_command.failed",
            error,
            command=getattr(interaction.command, "qualified_name", None),
            guild_id=interaction.guild_id,
            channel_id=interaction.channel_id,
            user_id=interaction.user.id,
            interaction_id=interaction.id,
        )
        try:
            message = "Une erreur est survenue. Consulte les logs internes du bot."
            if not interaction.response.is_done():
                await interaction.response.send_message(message, ephemeral=True)
            elif not interaction.is_expired():
                await interaction.followup.send(message, ephemeral=True)
        except discord.HTTPException as response_error:
            log_exception(
                "discord.app_command.error_response_failed",
                response_error,
                command=getattr(interaction.command, "qualified_name", None),
                interaction_id=interaction.id,
            )


class NestorBot(discord.Client):
    """Discord client: intents, slash command tree, lifecycle, chatbot replies."""

    def __init__(self) -> None:
        super().__init__(intents=build_intents())
        self.tree = LoggingCommandTree(self)
        self.agent = AgentBridge()
        self.behavior_monitor = BehaviorMonitor(self)

    async def setup_hook(self) -> None:
        self.agent.bind_loop(asyncio.get_running_loop())
        await self.behavior_monitor.start()
        register_commands(self.tree)
        guild_id = os.getenv("DISCORD_GUILD_ID")
        if guild_id:
            guild = discord.Object(id=int(guild_id))
            self.tree.copy_global_to(guild=guild)
            await self.tree.sync(guild=guild)
        else:
            await self.tree.sync()

    async def on_ready(self) -> None:
        log_event(
            "discord.bot.ready",
            bot_user_id=self.user.id if self.user else None,
            guild_count=len(self.guilds),
        )
        console.print(
            f"[green]Logged in as {self.user} — {len(self.guilds)} guild(s).[/green]"
        )

    async def on_message(self, message: discord.Message) -> None:
        if message.author.bot or message.guild is None:
            return
        if message.content.startswith("/"):
            return

        # Review runs independently of the chatbot channel, in the background.
        self.behavior_monitor.enqueue(message)

        chatbot_channel_id = get_chatbot_channel_id(message.guild.id)
        is_chatbot_channel = (
            chatbot_channel_id is not None and message.channel.id == chatbot_channel_id
        )
        directly_addressed = _is_directly_addressed(message, self.user)
        if not is_chatbot_channel and not directly_addressed:
            return

        log_event(
            "discord.message.received",
            guild_id=message.guild.id,
            channel_id=message.channel.id,
            message_id=message.id,
            user_id=message.author.id,
            content=message.content,
        )

        # Discord already resolves real user pings to Member objects. Pass that
        # authoritative mapping to the model so it can call member tools with an
        # ID instead of guessing from a rendered @name.
        mentioned_members = list(
            {
                mentioned.id: mentioned
                for mentioned in message.mentions
                if self.user is None or mentioned.id != self.user.id
            }.values()
        )
        mention_context = ""
        if mentioned_members:
            mention_lines = [
                f"- {mentioned.mention}: user_id={mentioned.id}; username={mentioned.name}; "
                f"display_name={mentioned.display_name}"
                for mentioned in mentioned_members
            ]
            mention_context = (
                "\n\n[Discord-resolved user mentions in this message]\n"
                + "\n".join(mention_lines)
                + "\nUse the numeric user_id above as the member argument for tools "
                "that target these mentioned users. These IDs come from Discord."
            )
        if directly_addressed:
            mention_context += (
                "\n\n[Direct address] The user directly pinged you or used your name. "
                "Answer the request in this channel."
            )

        try:
            async with message.channel.typing():
                reply = await self.agent.reply(
                    message.channel.id,
                    message.content + mention_context,
                    guild=message.guild,
                    member=message.author,
                    channel=message.channel,
                    source_message=message,
                    bot_user=self.user,
                )
        except Exception as error:  # noqa: BLE001 - always return a visible Discord error
            log_exception(
                "discord.agent.reply_failed",
                error,
                guild_id=message.guild.id,
                channel_id=message.channel.id,
                message_id=message.id,
                user_id=message.author.id,
            )
            console.print(f"[red]Agent reply failed: {error}[/red]")
            reply = DiscordReply(
                content="Je n’ai pas pu traiter cette demande. Vérifie les logs du bot puis réessaie.",
                provider="Nestor",
                model="Discord runtime",
                error=True,
            )

        if not reply.content or not reply.content.strip():
            reply.content = "Je n’ai pas pu générer de réponse. Réessaie dans un instant."
            reply.error = True

        chunks = [reply.content[i : i + 4000] for i in range(0, len(reply.content), 4000)]
        for idx, chunk in enumerate(chunks):
            embed = build_reply_embed(
                type(reply)(content=chunk, thinking=reply.thinking if idx == 0 else "", usage=reply.usage if idx == 0 else None, tools_used=reply.tools_used if idx == 0 else None, provider=reply.provider, model=reply.model, error=reply.error, request_id=reply.request_id),
                chunk_index=idx,
                chunk_count=len(chunks),
            )
            view = ThinkingView(reply.thinking) if idx == 0 and reply.thinking else None
            await message.channel.send(
                embed=embed,
                view=view,
                reference=message if directly_addressed and idx == 0 else None,
            )
        log_event(
            "discord.message.reply_sent",
            request_id=reply.request_id,
            guild_id=message.guild.id,
            channel_id=message.channel.id,
            source_message_id=message.id,
            response_chars=len(reply.content),
            chunk_count=len(chunks),
            tools_used=reply.tools_used or [],
            failed=reply.error,
            provider=reply.provider,
            model=reply.model,
        )

    async def close(self) -> None:
        await self.behavior_monitor.close()
        await super().close()


def build_intents() -> discord.Intents:
    """Bot intents: guilds plus message content for chatbot replies."""
    intents = discord.Intents.default()
    intents.message_content = True
    intents.polls = True
    return intents


def run_bot() -> None:
    """Load the token from .env then start the bot."""
    load_dotenv(dotenv_path=DOTENV_PATH)
    log_path = configure_logging()
    log_event("discord.bot.starting", log_path=str(log_path))
    token = os.getenv("DISCORD_TOKEN")
    if not token:
        raise SystemExit("DISCORD_TOKEN is missing: add it to the .env file at the repo root.")
    guild_id = os.getenv("DISCORD_GUILD_ID")
    if guild_id and not guild_id.isdigit():
        raise SystemExit("Invalid DISCORD_GUILD_ID: provide a numeric guild id.")
    NestorBot().run(token)
