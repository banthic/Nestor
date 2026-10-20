"""Persistence of Discord settings (chatbot channel per guild)."""

import json
from pathlib import Path

from ..gateway.prompts import DISCORD_SYSTEM_PROMPT

DISCORD_CONFIG_PATH = Path(__file__).resolve().parents[1] / "config" / "discord.json"


def _load() -> dict:
    try:
        with DISCORD_CONFIG_PATH.open() as config_file:
            config = json.load(config_file)
    except (OSError, json.JSONDecodeError):
        return {"guilds": {}}
    if not isinstance(config, dict):
        return {"guilds": {}}
    return config


def _save(config: dict) -> None:
    DISCORD_CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with DISCORD_CONFIG_PATH.open("w") as config_file:
        json.dump(config, config_file, indent=4)
        config_file.write("\n")


def get_chatbot_channel_id(guild_id: int) -> int | None:
    """Return the chatbot channel id saved for a guild, or None."""
    entry = _load().get("guilds", {}).get(str(guild_id), {})
    channel_id = entry.get("chatbot_channel_id")
    if channel_id is None:
        return None
    return int(channel_id)


def set_chatbot_channel_id(guild_id: int, channel_id: int) -> None:
    """Save the chatbot channel id for a guild."""
    config = _load()
    guilds = config.setdefault("guilds", {})
    guilds[str(guild_id)] = {"chatbot_channel_id": channel_id}
    _save(config)


def get_system_prompt() -> str:
    """Return the Discord system prompt addon (appended to the gateway prompt)."""
    prompt = _load().get("system_prompt")
    if not isinstance(prompt, str) or not prompt.strip():
        return DISCORD_SYSTEM_PROMPT
    return prompt


def set_system_prompt(prompt: str) -> None:
    """Save the Discord system prompt addon."""
    config = _load()
    config["system_prompt"] = prompt
    _save(config)
