"""Tests for the Discord agent bridge and its Discord-scoped tools wiring."""

import asyncio
import unittest
from unittest.mock import patch

from agent.discord_app import agent_bridge
from agent.discord_app.agent_bridge import AgentBridge, split_message
from agent.gateway import Gateway, StreamChunk
from agent.gateway.messages import build_messages
from agent.gateway.prompts import DISCORD_SYSTEM_PROMPT, SYSTEM_PROMPT
from agent.tools import execute_tool


def _fake_stream(self, prompt, history=None, tools=None, max_tool_iterations=10):
    yield StreamChunk("status", "Thinking")
    yield StreamChunk("content", "Hello ")
    yield StreamChunk("content", "world")


class TestAgentBridge(unittest.TestCase):
    @patch.object(Gateway, "stream_text", _fake_stream)
    def test_reply_joins_content(self):
        bridge = AgentBridge()
        reply = asyncio.run(bridge.reply(1, "hi"))
        self.assertEqual(reply.content, "Hello world")

    @patch.object(Gateway, "stream_text", _fake_stream)
    def test_history_accumulates_per_channel(self):
        bridge = AgentBridge()
        asyncio.run(bridge.reply(1, "hi"))
        asyncio.run(bridge.reply(1, "again"))
        asyncio.run(bridge.reply(2, "other channel"))
        self.assertEqual(len(bridge._sessions[1].history), 4)
        self.assertEqual(len(bridge._sessions[2].history), 2)

    def test_reset_clears_session(self):
        bridge = AgentBridge()
        bridge._sessions[5] = agent_bridge._ChannelSession()
        bridge.reset(5)
        self.assertNotIn(5, bridge._sessions)

    @patch.object(Gateway, "stream_text", _fake_stream)
    def test_gateway_exposes_only_discord_tools(self):
        captured = {}

        def _capture(self, prompt, history=None, tools=None, max_tool_iterations=10):
            captured["tools"] = self.tools
            captured["suffix"] = self.system_prompt_suffix
            yield StreamChunk("content", "ok")

        with patch.object(Gateway, "stream_text", _capture):
            bridge = AgentBridge()
            asyncio.run(bridge.reply(1, "hi"))

        self.assertEqual(captured["suffix"], DISCORD_SYSTEM_PROMPT)
        names = [tool["function"]["name"] for tool in captured["tools"]]
        self.assertEqual(names, ["rename_server"])

    def test_rename_handler_registered_during_reply(self):
        from agent.tools import rename_server as rename_tool

        seen = {}
        bridge = AgentBridge()

        def _capture(self, prompt, history=None, tools=None, max_tool_iterations=10):
            seen["output"] = execute_tool(self.tools, "rename_server", {"name": "Hive"})
            yield StreamChunk("content", "done")

        class _Guild:
            async def edit(self, name):
                seen["name"] = name

        with patch.object(Gateway, "stream_text", _capture):
            asyncio.run(bridge.reply(1, "rename the server", guild=_Guild()))

        self.assertEqual(seen.get("name"), "Hive")
        self.assertEqual(rename_tool["function"]["name"], "rename_server")

    def test_rename_handler_cleared_after_reply(self):
        from agent.tools import execute_tool as run_tool
        from agent.tools import rename_server as rename_tool

        bridge = AgentBridge()

        def _capture(self, prompt, history=None, tools=None, max_tool_iterations=10):
            yield StreamChunk("content", "done")

        with patch.object(Gateway, "stream_text", _capture):
            asyncio.run(bridge.reply(1, "hi", guild=None))

        output = run_tool([rename_tool], "rename_server", {"name": "X"})
        self.assertIn("not available", output)


class TestDiscordSystemPrompt(unittest.TestCase):
    def test_addon_disables_filesystem_tools(self):
        self.assertIn("never list files", DISCORD_SYSTEM_PROMPT)
        self.assertIn("rename_server", DISCORD_SYSTEM_PROMPT)

    def test_build_messages_appends_addon(self):
        messages = build_messages("hi", system_prompt=SYSTEM_PROMPT, system_prompt_suffix=DISCORD_SYSTEM_PROMPT)
        content = messages[0]["content"]
        self.assertTrue(content.startswith(SYSTEM_PROMPT))
        self.assertTrue(content.endswith(DISCORD_SYSTEM_PROMPT))

    def test_build_messages_without_addon_unchanged(self):
        messages = build_messages("hi")
        self.assertEqual(messages[0]["content"], SYSTEM_PROMPT)


class TestSplitMessage(unittest.TestCase):
    def test_short_message_kept_whole(self):
        self.assertEqual(split_message("hello"), ["hello"])

    def test_long_message_split(self):
        parts = split_message("a" * 2500)
        self.assertEqual(len(parts), 2)
        self.assertEqual("".join(parts), "a" * 2500)
