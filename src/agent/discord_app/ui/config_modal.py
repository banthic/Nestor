"""Modal opened by /config to pick the chatbot channel."""

import discord
from discord import ui

from ...observability import log_event, log_exception
from ..settings import set_chatbot_channel_id
from .banner import post_banner


class ConfigModal(ui.Modal, title="Nestor configuration"):
    """Pick the channel that serves as the chatbot, then save it."""

    channel = ui.Label(
        text="Chatbot channel",
        description="The channel where Nestor answers as a chatbot.",
        component=ui.ChannelSelect(
            channel_types=[discord.ChannelType.text],
            placeholder="Select a channel",
        ),
    )

    def __init__(self, guild_id: int) -> None:
        super().__init__(timeout=300)
        self.guild_id = guild_id

    async def on_submit(self, interaction: discord.Interaction) -> None:
        try:
            await interaction.response.defer(ephemeral=True, thinking=True)
        except discord.NotFound as error:
            log_exception(
                "discord.config_modal.acknowledgement_failed",
                error,
                guild_id=self.guild_id,
                interaction_id=interaction.id,
            )
            return

        try:
            chosen = self.channel.component.values[0]
            set_chatbot_channel_id(self.guild_id, chosen.id)
            channel = interaction.guild.get_channel(chosen.id) if interaction.guild else None
            banner_posted = channel is not None
            if banner_posted:
                try:
                    await post_banner(channel)
                except discord.HTTPException as error:
                    banner_posted = False
                    log_exception(
                        "discord.config_modal.banner_failed",
                        error,
                        guild_id=self.guild_id,
                        channel_id=chosen.id,
                    )

            embed = discord.Embed(
                title="Configuration saved",
                description=f"Nestor will now act as a chatbot in {chosen.mention}.",
                color=discord.Color.green(),
            )
            if not banner_posted:
                embed.add_field(
                    name="Banner not posted",
                    value="I couldn't access the channel to post the banner. Check my permissions.",
                    inline=False,
                )
            await interaction.followup.send(embed=embed, ephemeral=True)
            log_event(
                "discord.config_modal.saved",
                guild_id=self.guild_id,
                channel_id=chosen.id,
                banner_posted=banner_posted,
                interaction_id=interaction.id,
            )
        except Exception as error:  # noqa: BLE001 - always log and surface modal failures
            log_exception(
                "discord.config_modal.submit_failed",
                error,
                guild_id=self.guild_id,
                interaction_id=interaction.id,
            )
            try:
                await interaction.followup.send(
                    "La configuration a échoué. Consulte les logs internes du bot.",
                    ephemeral=True,
                )
            except discord.HTTPException as followup_error:
                log_exception(
                    "discord.config_modal.error_followup_failed",
                    followup_error,
                    guild_id=self.guild_id,
                    interaction_id=interaction.id,
                )
