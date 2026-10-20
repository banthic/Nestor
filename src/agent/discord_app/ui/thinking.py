"""Thinking viewer: button to show reasoning as a text file (ephemeral)."""

import io

import discord
from discord import ui


class ThinkingView(ui.View):
    """Attach a button to a reply that reveals the model's thinking."""

    def __init__(self, thinking: str, timeout: float | None = None):
        super().__init__(timeout=timeout)
        self.thinking = thinking
        if not thinking:
            self.add_item(
                ui.Button(label="No thinking available", disabled=True, style=discord.ButtonStyle.secondary)
            )
            return
        self.add_item(
            ui.Button(
                label="View thinking (.txt)",
                style=discord.ButtonStyle.secondary,
                custom_id="nestor_view_thinking",
            )
        )

    @ui.button(label="View thinking (.txt)", style=discord.ButtonStyle.secondary)
    async def view_thinking(self, interaction: discord.Interaction, button: ui.Button):
        if not self.thinking:
            await interaction.response.send_message(
                "No thinking trace is available for this reply.", ephemeral=True
            )
            return

        bio = io.BytesIO(self.thinking.encode("utf-8"))
        f = discord.File(bio, filename="nestor-thinking.txt")
        embed = discord.Embed(
            title="Nestor · Thinking",
            description=(
                self.thinking[:3800] + "\n\n*...truncated for embed view.*"
                if len(self.thinking) > 3800
                else self.thinking
            ),
            color=discord.Color.dark_grey(),
        )
        embed.set_footer(text="Full reasoning attached as nestor-thinking.txt")
        await interaction.response.send_message(embed=embed, file=f, ephemeral=True)
        button.disabled = True
        await interaction.message.edit(view=self)
