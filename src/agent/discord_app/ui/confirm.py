"""Confirmation prompt used by the ``confirm`` tool.

Sensitive actions get their own layout: an embed describing the action, with
only a Confirm and a Cancel button. Choices stay in ``ask_user``; this view
never shows a selector.
"""

import asyncio

import discord
from discord import ui

PROMPT_TIMEOUT = 180
CONFIRMED = "The user confirmed the action."
CANCELLED = "The user cancelled the action."
TIMED_OUT = "The user did not confirm in time."


def _confirm_embed(
    action: str,
    details: str = "",
    title: str = "Nestor needs your confirmation",
) -> discord.Embed:
    description = action[:4000]
    if details:
        description = f"{description}\n\n{details}"[:4000]
    return discord.Embed(
        title=title,
        description=description,
        color=discord.Color.orange(),
    )


class _ConfirmView(ui.View):
    def __init__(self, member: discord.Member, action: str, details: str = "") -> None:
        super().__init__(timeout=PROMPT_TIMEOUT)
        self.member = member
        self.action = action
        self.details = details
        self.result: str | None = None
        self.message: discord.Message | None = None
        self._answered = asyncio.Event()

        confirm = ui.Button(label="Confirm", style=discord.ButtonStyle.success)
        confirm.callback = self._on_confirm
        self.add_item(confirm)

        cancel = ui.Button(label="Cancel", style=discord.ButtonStyle.secondary)
        cancel.callback = self._on_cancel
        self.add_item(cancel)

    async def ensure_author(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id == self.member.id:
            return True
        await interaction.response.send_message(
            "This confirmation was asked to someone else.", ephemeral=True
        )
        return False

    def finish(self, answer: str) -> None:
        self.result = answer
        self.stop()
        self._answered.set()

    async def _on_confirm(self, interaction: discord.Interaction) -> None:
        if not await self.ensure_author(interaction):
            return
        self.finish(CONFIRMED)
        await interaction.response.edit_message(
            embed=_confirm_embed(
                self.action,
                self.details,
                title="Action confirmed",
            ),
            view=None,
        )

    async def _on_cancel(self, interaction: discord.Interaction) -> None:
        if not await self.ensure_author(interaction):
            return
        self.finish(CANCELLED)
        await interaction.response.edit_message(
            embed=discord.Embed(
                title="Action cancelled",
                description=CANCELLED,
                color=discord.Color.dark_grey(),
            ),
            view=None,
        )


async def confirm_in_channel(
    channel: discord.abc.Messageable,
    member: discord.Member,
    action: str,
    details: str = "",
) -> str:
    """Post a confirmation embed with Confirm/Cancel buttons and wait."""
    view = _ConfirmView(member, action, details)
    message = await channel.send(
        content=member.mention,
        embed=_confirm_embed(action, details),
        view=view,
    )
    view.message = message

    try:
        await asyncio.wait_for(view._answered.wait(), timeout=PROMPT_TIMEOUT)
    except TimeoutError:
        view.stop()
        try:
            await message.edit(
                embed=discord.Embed(
                    title="Confirmation timed out",
                    description=TIMED_OUT,
                    color=discord.Color.dark_grey(),
                ),
                view=None,
            )
        except discord.HTTPException:
            pass
        return TIMED_OUT

    return view.result or TIMED_OUT
