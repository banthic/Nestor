"""Reaction-based multi-select checkboxes for ``select_options``.

Presents options as a list with number emojis, lets the targeted member tick
or untick by reacting, and submits with ✅ or cancels with ❌.
"""

import asyncio

import discord

PROMPT_TIMEOUT = 180
EMOJIS = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]
SUBMIT = "✅"
CANCEL = "❌"
CANCELLED_ANSWER = "The user cancelled the selection."
TIMED_OUT_ANSWER = "The user did not answer in time."


def _build_embed(
    question: str,
    options: list[str],
    selected: set[int],
    title: str = "Pick one or more options",
) -> discord.Embed:
    lines = []
    for index, option in enumerate(options):
        mark = "☑️" if index in selected else "⬜"
        lines.append(f"{mark} {EMOJIS[index]} {option}")
    description = f"{question}\n\n" + "\n".join(lines)
    description += f"\n\n{SUBMIT} Confirm • {CANCEL} Cancel"
    return discord.Embed(title=title, description=description[:4000], color=discord.Color.blurple())


class _CheckboxSelector:
    def __init__(
        self,
        channel: discord.abc.Messageable,
        member: discord.Member,
        question: str,
        options: list[str],
        allow_free_text: bool = False,
    ) -> None:
        self.channel = channel
        self.member = member
        self.question = question
        self.options = options[:15]
        self.allow_free_text = allow_free_text
        self.selected: set[int] = set()
        self.message: discord.Message | None = None
        self.result: str | None = None
        self._done = asyncio.Event()
        self._cancelled = False

    async def run(self) -> str:
        embed = _build_embed(self.question, self.options, self.selected)
        self.message = await self.channel.send(content=self.member.mention, embed=embed)

        for index in range(len(self.options)):
            try:
                await self.message.add_reaction(EMOJIS[index])
            except discord.HTTPException:
                pass
        try:
            await self.message.add_reaction(SUBMIT)
        except discord.HTTPException:
            pass
        try:
            await self.message.add_reaction(CANCEL)
        except discord.HTTPException:
            pass

        bot = self.channel.guild.me if hasattr(self.channel, "guild") and self.channel.guild else None
        def check(payload: discord.RawReactionActionEvent) -> bool:
            if self.message is None or payload.message_id != self.message.id:
                return False
            if payload.user_id != self.member.id:
                return False
            if bot and payload.user_id == bot.id:
                return False
            emoji = str(payload.emoji)
            return emoji in EMOJIS[: len(self.options)] or emoji == SUBMIT or emoji == CANCEL

        asyncio.get_running_loop()
        try:
            while True:
                try:
                    payload = await asyncio.wait_for(
                        self.channel._state.client.wait_for(
                            "raw_reaction_add",
                            check=check,
                        ),
                        timeout=PROMPT_TIMEOUT,
                    )
                except TimeoutError:
                    try:
                        await self.message.edit(
                            embed=_build_embed(
                                self.question,
                                self.options,
                                self.selected,
                                title="No answer received",
                            ),
                            view=None,
                        )
                    except discord.HTTPException:
                        pass
                    return TIMED_OUT_ANSWER

                emoji = str(payload.emoji)
                if emoji in EMOJIS[: len(self.options)]:
                    index = EMOJIS.index(emoji)
                    if index in self.selected:
                        self.selected.discard(index)
                    else:
                        self.selected.add(index)
                    try:
                        await self.message.edit(
                            embed=_build_embed(self.question, self.options, self.selected)
                        )
                    except discord.HTTPException:
                        pass
                    continue

                if emoji == CANCEL:
                    try:
                        await self.message.edit(
                            embed=discord.Embed(
                                title="Selection cancelled",
                                description=CANCELLED_ANSWER,
                                color=discord.Color.dark_grey(),
                            ),
                            view=None,
                        )
                    except discord.HTTPException:
                        pass
                    return CANCELLED_ANSWER

                if emoji == SUBMIT:
                    if not self.selected:
                        try:
                            await self.channel.send(
                                "Pick at least one option or react with ❌ to cancel.",
                                delete_after=8,
                            )
                        except discord.HTTPException:
                            pass
                        continue

                    picks = [self.options[index] for index in sorted(self.selected)]
                    summary = ", ".join(picks)
                    if self.allow_free_text and len(picks) == len(self.selected):
                        pass

                    embed = discord.Embed(
                        title="Selection received",
                        description="\n".join([f"• {pick}" for pick in picks]),
                        color=discord.Color.green(),
                    )
                    try:
                        await self.message.edit(embed=embed, view=None)
                    except discord.HTTPException:
                        pass
                    return summary
        finally:
            pass


async def select_options_in_channel(
    channel: discord.abc.Messageable,
    member: discord.Member,
    question: str,
    options: list[str],
    allow_free_text: bool = False,
) -> str:
    selector = _CheckboxSelector(channel, member, question, options, allow_free_text)
    return await selector.run()
