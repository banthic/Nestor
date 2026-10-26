"""Configure the private staff channel for continuous behavior review."""

import discord
from discord import app_commands

from ...observability import log_event
from ..ui.review_channel_modal import ReviewChannelModal
from .checks import can_configure


@app_commands.command(
    name="config_review",
    description="Choose a staff-only channel for continuous AI behavior review.",
)
@app_commands.guild_only()
async def config_review_command(interaction: discord.Interaction) -> None:
    if not can_configure(interaction):
        await interaction.response.send_message(
            "Tu dois avoir **Gérer le serveur** pour configurer la veille.", ephemeral=True
        )
        return
    log_event(
        "discord.config_review.opened",
        guild_id=interaction.guild_id,
        user_id=interaction.user.id,
        interaction_id=interaction.id,
    )
    await interaction.response.send_modal(ReviewChannelModal(guild_id=interaction.guild_id))


@app_commands.command(
    name="disable_review_monitor",
    description="Disable continuous AI behavior review for this server.",
)
@app_commands.guild_only()
async def disable_review_monitor_command(interaction: discord.Interaction) -> None:
    if not can_configure(interaction):
        await interaction.response.send_message(
            "Tu dois avoir **Gérer le serveur** pour configurer la veille.", ephemeral=True
        )
        return
    from ..settings import clear_review_channel_id

    clear_review_channel_id(interaction.guild_id)
    log_event(
        "discord.behavior_monitor.disabled",
        guild_id=interaction.guild_id,
        user_id=interaction.user.id,
        interaction_id=interaction.id,
    )
    await interaction.response.send_message(
        "La veille des messages est désactivée pour ce serveur.", ephemeral=True
    )
