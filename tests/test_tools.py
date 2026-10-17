"""Tests for Nestor tools registry and dispatch."""

import tempfile
import unittest
from pathlib import Path

from agent.tools import TOOLS, QuitRequested, execute_tool, get_tools, to_schemas
from agent.tools.readfiles import _read_file, read_file


class TestTools(unittest.TestCase):
    def test_get_tools_registers_listfiles(self):
        names = [tool["function"]["name"] for tool in get_tools()]
        self.assertIn("listfiles", names)

    def test_get_tools_registers_quit(self):
        names = [tool["function"]["name"] for tool in get_tools()]
        self.assertIn("quit", names)

    def test_quit_tool_raises_quit_requested(self):
        with self.assertRaises(QuitRequested):
            execute_tool(get_tools(), "quit", {})

    def test_get_tools_returns_registry(self):
        self.assertEqual(get_tools(), TOOLS)

    def test_to_schemas_strips_call_key(self):
        schemas = to_schemas(get_tools())
        for schema in schemas:
            self.assertNotIn("call", schema)
            self.assertEqual(schema["type"], "function")
            self.assertIn("function", schema)
        names = [schema["function"]["name"] for schema in schemas]
        self.assertIn("listfiles", names)

    def test_execute_tool_lists_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "hello.txt").touch()
            output = execute_tool(get_tools(), "listfiles", {"path": tmp})
            self.assertIn("hello.txt", output)

    def test_execute_tool_raises_on_unknown(self):
        with self.assertRaises(KeyError):
            execute_tool(get_tools(), "no_such_tool", {})

    def test_read_file_returns_file_content(self):
        with tempfile.TemporaryDirectory() as tmp:
            file_path = Path(tmp) / "hello.txt"
            file_path.write_text("Hello, Nestor!\n")

            self.assertEqual(_read_file(str(file_path)), "Hello, Nestor!\n")

    def test_execute_tool_reads_file_with_spaces_in_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp) / "banthic AI" / "HiveSTA" / "code"
            directory.mkdir(parents=True)
            file_path = directory / "chatbot.py"
            file_path.write_text("print('hello')\n")

            output = execute_tool(get_tools(), "readfile", {"path": str(file_path)})

            self.assertEqual(output, "print('hello')\n")

    def test_read_file_raises_for_missing_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            file_path = Path(tmp) / "missing.txt"

            with self.assertRaises(FileNotFoundError):
                _read_file(str(file_path))

    def test_read_file_has_expected_tool_schema(self):
        self.assertEqual(read_file["function"]["name"], "readfile")
        self.assertEqual(read_file["function"]["parameters"]["required"], ["path"])
        self.assertIs(read_file["call"], _read_file)


if __name__ == "__main__":
    unittest.main()