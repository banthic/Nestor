"""Modal for selecting the private staff channel used by behavior review."""

import discord
from discord import ui

from ...observability import log_event, log_exception
from ..settings import set_review_channel_id


class ReviewChannelModal(ui.Modal, title="Staff review channel"):
    """Choose where Nestor sends human-review alerts."""

    channel = ui.Label(
        text="Private staff channel",
        description="Text messages Nestor can see are checked for potential harm.",
        component=ui.ChannelSelect(
            channel_types=[discord.ChannelType.text],
            placeholder="Select a staff-only channel",
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
                "discord.review_channel_modal.acknowledgement_failed",
                error,
                guild_id=self.guild_id,
                interaction_id=interaction.id,
            )
            return

        try:
            chosen = self.channel.component.values[0]
            channel = interaction.guild.get_channel(chosen.id) if interaction.guild else None
            bot_member = interaction.guild.me if interaction.guild else None
            if channel is None or bot_member is None:
                await interaction.followup.send(
                    "Je ne peux pas vérifier l’accès au salon sélectionné.", ephemeral=True
                )
                return
            everyone_permissions = channel.permissions_for(interaction.guild.default_role)
            if everyone_permissions.view_channel:
                await interaction.followup.send(
                    "Le salon choisi est visible par @everyone. Choisis un salon staff privé pour éviter d’exposer les alertes aux membres.",
                    ephemeral=True,
                )
                return
            permissions = channel.permissions_for(bot_member)
            if not (permissions.view_channel and permissions.send_messages and permissions.embed_links):
                await interaction.followup.send(
                    "Donne à Nestor **Voir le salon**, **Envoyer des messages** et **Intégrer des liens** dans ce salon, puis réessaie.",
                    ephemeral=True,
                )
                return

            set_review_channel_id(self.guild_id, channel.id)
            embed = discord.Embed(
                title="Veille activée",
                description=(
                    f"Nestor analysera les messages textuels des salons qu’il peut voir et enverra "
                    f"les cas préoccupants dans {channel.mention} pour examen humain. "
                    "Aucune sanction n’est automatique."
                ),
                color=discord.Color.green(),
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            log_event(
                "discord.review_channel_modal.saved",
                guild_id=self.guild_id,
                review_channel_id=channel.id,
                interaction_id=interaction.id,
            )
        except Exception as error:  # noqa: BLE001 - make modal failures visible
            log_exception(
                "discord.review_channel_modal.submit_failed",
                error,
                guild_id=self.guild_id,
                interaction_id=interaction.id,
            )
            try:
                await interaction.followup.send(
                    "La configuration de la veille a échoué. Consulte les logs internes du bot.",
                    ephemeral=True,
                )
            except discord.HTTPException as followup_error:
                log_exception(
                    "discord.review_channel_modal.followup_failed",
                    followup_error,
                    guild_id=self.guild_id,
                    interaction_id=interaction.id,
                )
