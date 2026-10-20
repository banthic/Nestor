"""Tests for Discord settings persistence and the /config modal."""

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from agent.discord_app import settings
from agent.discord_app.ui import ConfigModal, build_banner


class TestDiscordSettings(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.path = Path(self._tmp.name) / "discord.json"
        patcher = patch.object(settings, "DISCORD_CONFIG_PATH", self.path)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.addCleanup(self._tmp.cleanup)

    def test_missing_file_returns_none(self):
        self.assertIsNone(settings.get_chatbot_channel_id(123))

    def test_set_then_get_roundtrip(self):
        settings.set_chatbot_channel_id(123, 456)
        self.assertEqual(settings.get_chatbot_channel_id(123), 456)

    def test_guilds_are_isolated(self):
        settings.set_chatbot_channel_id(1, 10)
        settings.set_chatbot_channel_id(2, 20)
        self.assertEqual(settings.get_chatbot_channel_id(1), 10)
        self.assertEqual(settings.get_chatbot_channel_id(2), 20)

    def test_save_writes_valid_json(self):
        settings.set_chatbot_channel_id(1, 42)
        data = json.loads(self.path.read_text())
        self.assertEqual(data["guilds"]["1"]["chatbot_channel_id"], 42)

    def test_corrupt_file_returns_none(self):
        self.path.write_text("{not json")
        self.assertIsNone(settings.get_chatbot_channel_id(1))

    def test_default_system_prompt_is_discord_addon(self):
        from agent.gateway import DISCORD_SYSTEM_PROMPT

        self.assertEqual(settings.get_system_prompt(), DISCORD_SYSTEM_PROMPT)

    def test_set_system_prompt_roundtrip(self):
        settings.set_system_prompt("Be brief.")
        self.assertEqual(settings.get_system_prompt(), "Be brief.")

    def test_blank_system_prompt_falls_back_to_default(self):
        from agent.gateway import DISCORD_SYSTEM_PROMPT

        settings.set_system_prompt("   ")
        self.assertEqual(settings.get_system_prompt(), DISCORD_SYSTEM_PROMPT)


class TestConfigModal(unittest.TestCase):
    def test_modal_has_channel_select(self):
        modal = ConfigModal(guild_id=1)
        components = modal.to_components()
        self.assertEqual(len(components), 1)
        self.assertEqual(components[0]["type"], 18)
        self.assertEqual(components[0]["component"]["type"], 8)

    def test_modal_uses_english_title(self):
        modal = ConfigModal(guild_id=1)
        self.assertEqual(modal.title, "Nestor configuration")


class TestBanner(unittest.TestCase):
    def test_banner_renders_container(self):
        view = build_banner()
        components = view.to_components()
        self.assertEqual(len(components), 1)
        self.assertEqual(components[0]["type"], 17)

    def test_banner_has_text_and_separators(self):
        container = build_banner().to_components()[0]
        types = [child["type"] for child in container["components"]]
        self.assertIn(10, types)
        self.assertIn(14, types)

    def test_banner_uses_placeholders(self):
        container = build_banner().to_components()[0]
        text = " ".join(
            child["content"] for child in container["components"] if child["type"] == 10
        )
        self.assertIn("Nestor", text)
        self.assertIn("Provider", text)
        self.assertIn("Tools", text)
