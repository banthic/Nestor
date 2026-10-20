"""Banner message posted in the chatbot channel, inspired by the CLI panel."""

import discord
from discord import ui

from ...gateway.config import load_config
from ..agent_bridge import DISCORD_TOOLS


def _provider_label() -> str:
    config = load_config()
    default_provider = config.get("default_provider", "")
    provider_cfg = config.get("provider", {})
    if default_provider == "external_api_openai_compatible":
        model = provider_cfg.get(default_provider, {}).get("model", "")
        return f"{default_provider} · {model}" if model else default_provider
    if default_provider == "local_ollama":
        model = provider_cfg.get(default_provider, {}).get("model", "")
        return f"{default_provider} · {model}" if model else default_provider
    return default_provider or "unknown"


def _tools_label() -> str:
    if not DISCORD_TOOLS:
        return "none"
    names = [tool["function"]["name"] for tool in DISCORD_TOOLS]
    return ", ".join(names)


def build_banner(status: str = "ready") -> ui.LayoutView:
    """Build the Components V2 banner shown at the top of the chatbot channel."""
    view = ui.LayoutView(timeout=None)
    provider_label = _provider_label()
    tools_label = _tools_label()
    view.add_item(
        ui.Container(
            ui.TextDisplay(
                "# Nestor\n"
                "**Your community assistant.**\n"
                "This channel is set up as the Nestor chatbot."
            ),
            ui.Separator(),
            ui.TextDisplay(
                f"> **Status** · {status}\n"
                f"> **Provider** · {provider_label}\n"
                f"> **Tools** · {tools_label}\n"
                "> **Commands** · `/config` to change the chatbot channel"
            ),
            ui.Separator(),
            ui.TextDisplay("-# Powered by Banthic Labs"),
            accent_colour=discord.Colour.blurple(),
        )
    )
    return view


async def post_banner(channel: discord.abc.Messageable) -> discord.Message:
    """Post the banner message into a channel."""
    return await channel.send(view=build_banner())
