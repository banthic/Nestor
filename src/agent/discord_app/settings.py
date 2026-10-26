"""Persistence of Discord settings per guild."""

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
    guild = guilds.setdefault(str(guild_id), {})
    guild["chatbot_channel_id"] = channel_id
    _save(config)


def get_review_channel_id(guild_id: int) -> int | None:
    """Return the staff review channel configured for continuous monitoring."""
    entry = _load().get("guilds", {}).get(str(guild_id), {})
    channel_id = entry.get("review_channel_id")
    return int(channel_id) if channel_id is not None else None


def set_review_channel_id(guild_id: int, channel_id: int) -> None:
    """Enable the behavior review monitor by setting its staff channel."""
    config = _load()
    guilds = config.setdefault("guilds", {})
    guild = guilds.setdefault(str(guild_id), {})
    guild["review_channel_id"] = channel_id
    _save(config)


def clear_review_channel_id(guild_id: int) -> None:
    """Disable behavior review monitoring for a guild."""
    config = _load()
    guilds = config.setdefault("guilds", {})
    guild = guilds.setdefault(str(guild_id), {})
    guild.pop("review_channel_id", None)
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
