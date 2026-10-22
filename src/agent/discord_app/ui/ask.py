"""Interactive prompt used by the ``ask_user`` tool.

The agent can ask for a missing detail without leaving Discord: a selector is
shown when choices are provided, and a button opens a text input for free-form
answers. The tool call waits until the targeted member answers or the prompt
times out.
"""

import asyncio

import discord
from discord import ui

PROMPT_TIMEOUT = 180
CANCELLED_ANSWER = "The user cancelled the request."


def _answer_embed(question: str, title: str = "Nestor needs more information") -> discord.Embed:
    return discord.Embed(
        title=title,
        description=question[:4000],
        color=discord.Color.blurple(),
    )


class _AnswerModal(ui.Modal, title="Nestor · Your answer"):
    answer = ui.TextInput(
        label="Your answer",
        style=discord.TextStyle.paragraph,
        placeholder="Type the missing information…",
        required=True,
        max_length=1000,
    )

    def __init__(self, view: "_AnswerView") -> None:
        super().__init__(timeout=PROMPT_TIMEOUT)
        self._view = view

    async def on_submit(self, interaction: discord.Interaction) -> None:
        if not await self._view.ensure_author(interaction):
            return
        self._view.finish(str(self.answer.value))
        await interaction.response.send_message("Answer received.", ephemeral=True)
        await self._view.close_message("Your answer", str(self.answer.value))


class _AnswerView(ui.View):
    def __init__(
        self,
        member: discord.Member,
        question: str,
        options: list[str] | None,
        allow_free_text: bool,
    ) -> None:
        super().__init__(timeout=PROMPT_TIMEOUT)
        self.member = member
        self.question = question
        self.options = list(options or [])[:25]
        self.result: str | None = None
        self.message: discord.Message | None = None
        self._answered = asyncio.Event()

        if self.options:
            select = ui.Select(
                placeholder="Choose an answer",
                options=[
                    discord.SelectOption(label=option[:100], value=str(index))
                    for index, option in enumerate(self.options)
                ],
            )
            select.callback = self._on_select
            self.add_item(select)

        if allow_free_text or not self.options:
            button = ui.Button(label="Type an answer", style=discord.ButtonStyle.primary)
            button.callback = self._on_type
            self.add_item(button)

        cancel = ui.Button(label="Cancel", style=discord.ButtonStyle.secondary)
        cancel.callback = self._on_cancel
        self.add_item(cancel)

    async def ensure_author(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id == self.member.id:
            return True
        await interaction.response.send_message(
            "This question was asked to someone else.", ephemeral=True
        )
        return False

    def finish(self, answer: str) -> None:
        self.result = answer
        self.stop()
        self._answered.set()

    async def close_message(self, label: str, answer: str) -> None:
        if self.message is None:
            return
        embed = discord.Embed(
            title=label,
            description=answer[:4000],
            color=discord.Color.green(),
        )
        try:
            await self.message.edit(embed=embed, view=None)
        except discord.HTTPException:
            pass

    async def _on_select(self, interaction: discord.Interaction) -> None:
        if not await self.ensure_author(interaction):
            return
        index = int(interaction.data["values"][0])
        answer = self.options[index]
        self.finish(answer)
        await interaction.response.edit_message(
            embed=discord.Embed(
                title="Answer received",
                description=answer[:4000],
                color=discord.Color.green(),
            ),
            view=None,
        )

    async def _on_type(self, interaction: discord.Interaction) -> None:
        if not await self.ensure_author(interaction):
            return
        await interaction.response.send_modal(_AnswerModal(self))

    async def _on_cancel(self, interaction: discord.Interaction) -> None:
        if not await self.ensure_author(interaction):
            return
        self.finish(CANCELLED_ANSWER)
        await interaction.response.edit_message(
            embed=discord.Embed(
                title="Request cancelled",
                description=CANCELLED_ANSWER,
                color=discord.Color.dark_grey(),
            ),
            view=None,
        )


async def ask_user_in_channel(
    channel: discord.abc.Messageable,
    member: discord.Member,
    question: str,
    options: list[str] | None = None,
    allow_free_text: bool = True,
) -> str:
    """Post an interactive prompt and wait for the member's answer."""
    view = _AnswerView(member, question, options, allow_free_text)
    message = await channel.send(
        content=member.mention,
        embed=_answer_embed(question),
        view=view,
    )
    view.message = message

    try:
        await asyncio.wait_for(view._answered.wait(), timeout=PROMPT_TIMEOUT)
    except TimeoutError:
        view.stop()
        try:
            await message.edit(
                embed=_answer_embed(question, title="No answer received"),
                view=None,
            )
        except discord.HTTPException:
            pass
        return "The user did not answer in time."

    return view.result or "No answer was provided."
