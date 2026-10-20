"""/config: choose the channel that serves as the Nestor chatbot."""

import discord
from discord import app_commands

from ..ui import ConfigModal
from .checks import can_configure


@app_commands.command(
    name="config",
    description="Select the channel where Nestor acts as a chatbot.",
)
@app_commands.guild_only()
async def config_command(interaction: discord.Interaction) -> None:
    if not can_configure(interaction):
        await interaction.response.send_message(
            "You need the **Manage Server** permission to configure Nestor.",
            ephemeral=True,
        )
        return

    await interaction.response.send_modal(ConfigModal(guild_id=interaction.guild_id))
