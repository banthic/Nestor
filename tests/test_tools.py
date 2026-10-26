"""Tests for the Nestor tools registry and the server-rename tool."""

import unittest

from agent.tools import (
    TOOLS,
    access,
    ask_user,
    clear_ask_handler,
    clear_member_permissions_handler,
    clear_permission_checker,
    clear_rename_handler,
    execute_tool,
    get_member_permissions,
    get_tools,
    rename_server,
    set_ask_handler,
    set_member_permissions_handler,
    set_permission_checker,
    set_rename_handler,
    to_schemas,
)


class TestTools(unittest.TestCase):
    def tearDown(self):
        clear_rename_handler()
        clear_permission_checker()
        clear_member_permissions_handler()
        clear_ask_handler()

    def test_registry_contains_cli_tools(self):
        names = [tool["function"]["name"] for tool in get_tools()]
        self.assertEqual(names, ["rename_server", "web_search", "web_fetch"])

    def test_get_tools_returns_registry(self):
        self.assertEqual(get_tools(), TOOLS)

    def test_to_schemas_strips_call_key(self):
        schemas = to_schemas(get_tools())
        for schema in schemas:
            self.assertNotIn("call", schema)
            self.assertEqual(schema["type"], "function")
            self.assertIn("function", schema)
        self.assertEqual(schemas[0]["function"]["name"], "rename_server")

    def test_rename_server_requires_name(self):
        self.assertEqual(rename_server["function"]["parameters"]["required"], ["name"])

    def test_execute_rename_without_handler_is_safe(self):
        output = execute_tool(get_tools(), "rename_server", {"name": "Hive"})
        self.assertIn("not available", output)

    def test_execute_rename_calls_handler(self):
        calls = []
        set_rename_handler(lambda name: calls.append(name) or f"renamed to {name}")
        output = execute_tool(get_tools(), "rename_server", {"name": "Hive"})
        self.assertEqual(calls, ["Hive"])
        self.assertEqual(output, "renamed to Hive")

    def test_access_tool_reports_missing_permission(self):
        set_permission_checker(lambda permission: f"missing {permission}")

        output = execute_tool([access], "access", {"permission": "manage_guild"})

        self.assertEqual(output, "missing manage_guild")

    def test_access_tool_reports_granted_permission(self):
        set_permission_checker(lambda permission: None)

        output = execute_tool([access], "access", {"permission": "manage_guild"})

        self.assertIn("has the **manage_guild** permission", output)

    def test_access_tool_without_checker_is_safe(self):
        output = execute_tool([access], "access", {"permission": "manage_guild"})

        self.assertIn("not available", output)

    def test_permission_guard_blocks_action(self):
        calls = []
        set_rename_handler(lambda name: calls.append(name) or "renamed")
        set_permission_checker(lambda permission: f"missing {permission}")

        output = execute_tool(get_tools(), "rename_server", {"name": "Hive"})

        self.assertIn("missing manage_guild", output)
        self.assertEqual(calls, [])

    def test_permission_guard_allows_action(self):
        calls = []
        set_rename_handler(lambda name: calls.append(name) or "renamed")
        set_permission_checker(lambda permission: None)

        output = execute_tool(get_tools(), "rename_server", {"name": "Hive"})

        self.assertEqual(output, "renamed")
        self.assertEqual(calls, ["Hive"])

    def test_to_schemas_strips_permission_key(self):
        schema = to_schemas([rename_server])[0]
        self.assertNotIn("permission", schema)

    def test_get_member_permissions_delegates(self):
        seen = []
        set_member_permissions_handler(lambda member: seen.append(member) or "ok")

        output = execute_tool([get_member_permissions], "get_member_permissions", {"member": "bob"})

        self.assertEqual(output, "ok")
        self.assertEqual(seen, ["bob"])

    def test_get_member_permissions_without_handler_is_safe(self):
        output = execute_tool([get_member_permissions], "get_member_permissions", {})

        self.assertIn("not available", output)

    def test_ask_user_delegates(self):
        captured = {}

        def handler(question, options=None, allow_free_text=True):
            captured.update(question=question, options=options, allow_free_text=allow_free_text)
            return "Hive"

        set_ask_handler(handler)

        output = execute_tool(
            [ask_user],
            "ask_user",
            {"question": "New name?", "options": ["Hive", "Nest"]},
        )

        self.assertEqual(output, "Hive")
        self.assertEqual(captured["question"], "New name?")
        self.assertEqual(captured["options"], ["Hive", "Nest"])
        self.assertTrue(captured["allow_free_text"])

    def test_ask_user_without_handler_is_safe(self):
        output = execute_tool([ask_user], "ask_user", {"question": "New name?"})

        self.assertIn("not available", output)

    def test_execute_tool_raises_on_unknown(self):
        with self.assertRaises(KeyError):
            execute_tool(get_tools(), "no_such_tool", {})


if __name__ == "__main__":
    unittest.main()
