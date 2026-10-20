"""Modal opened by /config to pick the chatbot channel."""

import discord
from discord import ui

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
        chosen = self.channel.component.values[0]
        set_chatbot_channel_id(self.guild_id, chosen.id)

        channel = interaction.guild.get_channel(chosen.id)
        banner_posted = channel is not None
        if banner_posted:
            await post_banner(channel)

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
        await interaction.response.send_message(embed=embed, ephemeral=True)
