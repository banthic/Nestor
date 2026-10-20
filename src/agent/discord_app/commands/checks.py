"""Checks shared by the slash commands."""

import discord


def can_configure(interaction: discord.Interaction) -> bool:
    """Whether the member is allowed to configure Nestor on this guild."""
    member = interaction.user
    return isinstance(member, discord.Member) and member.guild_permissions.manage_guild
