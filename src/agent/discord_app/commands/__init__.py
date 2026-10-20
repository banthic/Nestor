"""Slash commands registry: one module per command, listed in ``COMMANDS``."""

from discord import app_commands

from .config import config_command

COMMANDS = [
    config_command,
]


def register_commands(tree: app_commands.CommandTree) -> None:
    """Register every command of the registry on the application command tree."""
    for command in COMMANDS:
        tree.add_command(command)


__all__ = ["COMMANDS", "register_commands"]
