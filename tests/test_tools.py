"""Tests for the Nestor tools registry and the server-rename tool."""

import unittest

from agent.tools import (
    TOOLS,
    clear_rename_handler,
    execute_tool,
    get_tools,
    rename_server,
    set_rename_handler,
    to_schemas,
)


class TestTools(unittest.TestCase):
    def tearDown(self):
        clear_rename_handler()

    def test_registry_contains_only_rename_server(self):
        names = [tool["function"]["name"] for tool in get_tools()]
        self.assertEqual(names, ["rename_server"])

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

    def test_execute_tool_raises_on_unknown(self):
        with self.assertRaises(KeyError):
            execute_tool(get_tools(), "no_such_tool", {})


if __name__ == "__main__":
    unittest.main()
