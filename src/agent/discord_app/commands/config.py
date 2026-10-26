"""/config: choose the channel that serves as the Nestor chatbot."""

import discord
from discord import app_commands

from ...observability import log_event
from ..ui import ConfigModal
from .checks import can_configure


@app_commands.command(
    name="config",
    description="Select the channel where Nestor acts as a chatbot.",
)
@app_commands.guild_only()
async def config_command(interaction: discord.Interaction) -> None:
    if not can_configure(interaction):
        log_event(
            "discord.command.config.denied",
            guild_id=interaction.guild_id,
            channel_id=interaction.channel_id,
            user_id=interaction.user.id,
            interaction_id=interaction.id,
        )
        await interaction.response.send_message(
            "You need the **Manage Server** permission to configure Nestor.",
            ephemeral=True,
        )
        return

    log_event(
        "discord.command.config.opened",
        guild_id=interaction.guild_id,
        channel_id=interaction.channel_id,
        user_id=interaction.user.id,
        interaction_id=interaction.id,
    )
    await interaction.response.send_modal(ConfigModal(guild_id=interaction.guild_id))
