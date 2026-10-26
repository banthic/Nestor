"""Tests for the Discord agent bridge and its Discord-scoped tools wiring."""

import asyncio
import unittest
from types import SimpleNamespace
from unittest.mock import patch

import discord

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


class _FakePermissions:
    def __init__(self, **granted):
        self._values = {"administrator": False, "manage_guild": False, "kick_members": False}
        self._values.update(granted)

    def __getattr__(self, name):
        return self._values.get(name, False)

    def __iter__(self):
        return iter(self._values.items())


class _FakeRole:
    def __init__(self, name, default=False):
        self.name = name
        self._default = default

    def is_default(self):
        return self._default


class _FakeMember:
    def __init__(self, member_id=7, name="alice", display_name="Alice", roles=None, **permissions):
        self.id = member_id
        self.name = name
        self.display_name = display_name
        self.mention = f"<@{member_id}>"
        self.roles = list(roles or [])
        self.guild_permissions = _FakePermissions(**permissions)


class _FakeGuild:
    def __init__(self, members=None):
        self.members = list(members or [])
        self.renamed = None

    async def edit(self, name):
        self.renamed = name

    def get_member(self, member_id):
        return next((member for member in self.members if member.id == member_id), None)

    def get_member_named(self, name):
        lowered = name.casefold()
        return next(
            (
                member
                for member in self.members
                if member.name.casefold() == lowered or member.display_name.casefold() == lowered
            ),
            None,
        )

    async def fetch_member(self, member_id):
        found = self.get_member(member_id)
        if found is not None:
            return found
        raise discord.NotFound(
            SimpleNamespace(status=404, reason="Not Found"),
            "Unknown Member",
        )

    async def query_members(self, query, limit=5):
        needle = query.casefold()
        return [
            member
            for member in self.members
            if needle in {member.name.casefold(), member.display_name.casefold()}
        ][:limit]


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
        self.assertEqual(
            names,
            [
                "rename_server",
                "access",
                "confirm",
                "select_options",
                "get_member_permissions",
                "ask_user",
                "web_search",
                "web_fetch",
            ],
        )

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

    def test_action_is_denied_without_permission(self):
        seen = {}
        bridge = AgentBridge()
        guild = _FakeGuild()
        member = _FakeMember(manage_guild=False)

        def _capture(self, prompt, history=None, tools=None, max_tool_iterations=10):
            seen["rename"] = execute_tool(self.tools, "rename_server", {"name": "Hive"})
            yield StreamChunk("content", "done")

        with patch.object(Gateway, "stream_text", _capture):
            asyncio.run(bridge.reply(1, "rename", guild=guild, member=member))

        self.assertIn("Manage Server", seen["rename"])
        self.assertIsNone(guild.renamed)

    def test_action_is_allowed_with_permission(self):
        bridge = AgentBridge()
        guild = _FakeGuild()
        member = _FakeMember(manage_guild=True)

        def _capture(self, prompt, history=None, tools=None, max_tool_iterations=10):
            execute_tool(self.tools, "rename_server", {"name": "Hive"})
            yield StreamChunk("content", "done")

        with patch.object(Gateway, "stream_text", _capture):
            asyncio.run(bridge.reply(1, "rename", guild=guild, member=member))

        self.assertEqual(guild.renamed, "Hive")

    def test_member_permissions_tool_reads_self(self):
        seen = {}
        bridge = AgentBridge()
        member = _FakeMember(kick_members=True, roles=[_FakeRole("V8")])
        guild = _FakeGuild([member])

        def _capture(self, prompt, history=None, tools=None, max_tool_iterations=10):
            seen["permissions"] = execute_tool(self.tools, "get_member_permissions", {})
            yield StreamChunk("content", "done")

        with patch.object(Gateway, "stream_text", _capture):
            asyncio.run(bridge.reply(1, "my permissions", guild=guild, member=member))

        self.assertIn("Kick Members", seen["permissions"])
        self.assertIn("Roles: V8", seen["permissions"])

    def test_member_lookup_fetches_uncached_member_by_id(self):
        seen = {}
        bridge = AgentBridge()
        requester = _FakeMember(manage_guild=True)
        target = _FakeMember(
            member_id=1230242431413391463,
            name="lecanard",
            display_name="Le canard sous V8",
            roles=[_FakeRole("@everyone", default=True), _FakeRole("V8")],
        )

        class _UncachedGuild(_FakeGuild):
            async def fetch_member(self, member_id):
                if member_id == target.id:
                    return target
                return await super().fetch_member(member_id)

        def _capture(self, prompt, history=None, tools=None, max_tool_iterations=10):
            seen["permissions"] = execute_tool(
                self.tools, "get_member_permissions", {"member": str(target.id)}
            )
            yield StreamChunk("content", "done")

        with patch.object(Gateway, "stream_text", _capture):
            asyncio.run(bridge.reply(1, "roles?", guild=_UncachedGuild(), member=requester))

        self.assertIn("Le canard sous V8", seen["permissions"])
        self.assertIn("Roles: V8", seen["permissions"])

    def test_member_lookup_queries_uncached_member_by_name(self):
        seen = {}
        bridge = AgentBridge()
        requester = _FakeMember(manage_guild=True)
        target = _FakeMember(
            member_id=42,
            name="lecanard",
            display_name="Le canard sous V8",
            roles=[_FakeRole("V8")],
        )

        class _SearchGuild(_FakeGuild):
            async def query_members(self, query, limit=5):
                needle = query.casefold()
                if needle in {target.name.casefold(), target.display_name.casefold()}:
                    return [target]
                return []

        def _capture(self, prompt, history=None, tools=None, max_tool_iterations=10):
            seen["permissions"] = execute_tool(
                self.tools, "get_member_permissions", {"member": "Le canard sous V8"}
            )
            yield StreamChunk("content", "done")

        with patch.object(Gateway, "stream_text", _capture):
            asyncio.run(bridge.reply(1, "roles?", guild=_SearchGuild(), member=requester))

        self.assertIn("Le canard sous V8", seen["permissions"])
        self.assertIn("Roles: V8", seen["permissions"])

    def test_member_permissions_require_manage_server_for_others(self):
        seen = {}
        bridge = AgentBridge()
        member = _FakeMember(manage_guild=False)
        guild = _FakeGuild([member, _FakeMember(member_id=8, name="bob", display_name="Bob")])

        def _capture(self, prompt, history=None, tools=None, max_tool_iterations=10):
            seen["permissions"] = execute_tool(
                self.tools, "get_member_permissions", {"member": "bob"}
            )
            yield StreamChunk("content", "done")

        with patch.object(Gateway, "stream_text", _capture):
            asyncio.run(bridge.reply(1, "bob's permissions", guild=guild, member=member))

        self.assertIn("Manage Server", seen["permissions"])


class TestDiscordSystemPrompt(unittest.TestCase):
    def test_addon_disables_filesystem_tools(self):
        self.assertIn("never list files", DISCORD_SYSTEM_PROMPT)
        self.assertIn("rename_server", DISCORD_SYSTEM_PROMPT)

    def test_addon_uses_access_confirm_and_select_options(self):
        prompt = DISCORD_SYSTEM_PROMPT.casefold()
        self.assertIn("src/agent/tools/access.py", prompt)
        self.assertIn("require_permission", prompt)
        self.assertIn("permission checks use access", prompt)
        self.assertIn("confirm", prompt)
        self.assertIn("select_options", prompt)
        self.assertIn("reaction-based checkboxes", prompt)
        self.assertIn("never use ask_user for confirmation", prompt)
        self.assertIn("member's roles", prompt)

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
