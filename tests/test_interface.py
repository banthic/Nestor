"""Tests for Nestor CLI interface components."""

import unittest

from rich.console import Console

from agent.cli.interface.messages import MessageHistory
from agent.cli.interface.panel import get_footer, get_panel, get_separator, render_panel
from agent.cli.interface.prompt import PromptArea
from agent.cli.interface.thinking import (
    DEFAULT_MAX_LENGTH,
    ThinkingMode,
    ThinkingStreamer,
    render_thinking,
)


class TestInterface(unittest.TestCase):
    def test_panel_content(self):
        """Verify that the panel contains its identity and status information."""
        panel = get_panel()
        self.assertIsNotNone(panel)

        console = Console(record=True, width=80)
        render_panel(console)
        output = console.export_text()

        self.assertIn("Nestor", output)
        self.assertNotIn("emiliendaix@gmail.com", output)
        self.assertNotIn("Starter Quota", output)
        self.assertNotIn("High", output)

    def test_separator_has_terminal_rule_character(self):
        self.assertIn("─", get_separator(20).plain)

    def test_panel_displays_usage(self):
        """Verify that the latest token usage is displayed in the base panel."""
        console = Console(record=True, width=100)
        console.print(get_footer(usage={
            "prompt_tokens": 12,
            "completion_tokens": 8,
            "total_tokens": 20,
        }))
        output = console.export_text()
        self.assertIn("Tokens 20", output)
        self.assertIn("in", output)
        self.assertIn("out 8", output)

    def test_message_history(self):
        """Verify message history operations (add, clear, get)."""
        history = MessageHistory()
        self.assertEqual(len(history.get_messages()), 0)

        history.add_user_message("Hello world")
        history.add_assistant_message("How can I assist you?")
        history.add_system_message("System initiated")

        messages = history.get_messages()
        self.assertEqual(len(messages), 3)
        self.assertEqual(messages[0]["role"], "user")
        self.assertEqual(messages[0]["content"], "Hello world")
        self.assertEqual(messages[1]["role"], "assistant")
        self.assertEqual(messages[2]["role"], "system")

        console = Console(record=True, width=80)
        history.render(console)
        rendered = console.export_text()
        self.assertIn("Hello world", rendered)
        self.assertIn("How can I assist you?", rendered)

        history.clear()
        self.assertEqual(len(history.get_messages()), 0)

    def test_prompt_area_init(self):
        """Verify PromptArea initialization."""
        prompt_area = PromptArea(prompt_symbol="Test > ")
        self.assertEqual(prompt_area.prompt_symbol, "Test > ")
        self.assertIsNotNone(prompt_area.session)

    def test_render_thinking_full(self):
        """Verify FULL mode prints the whole thinking content."""
        console = Console(record=True, width=100)
        render_thinking(console, "deep thought", ThinkingMode.FULL)
        output = console.export_text()
        self.assertIn("Thinking: deep thought", output)

    def test_render_thinking_short_truncates(self):
        """Verify SHORT mode truncates long thinking and suggests /thinking full."""
        console = Console(record=True, width=100)
        long_content = "x" * (DEFAULT_MAX_LENGTH + 50)
        render_thinking(console, long_content, ThinkingMode.SHORT)
        output = console.export_text()
        self.assertIn("...", output)
        self.assertIn("/thinking full", output)

    def test_render_thinking_short_fits(self):
        """Verify SHORT mode keeps short thinking intact."""
        console = Console(record=True, width=100)
        render_thinking(console, "short", ThinkingMode.SHORT)
        output = console.export_text()
        self.assertIn("Thinking: short", output)
        self.assertNotIn("/thinking full", output)

    def test_render_thinking_off(self):
        """Verify OFF mode renders nothing."""
        console = Console(record=True, width=100)
        render_thinking(console, "hidden", ThinkingMode.OFF)
        self.assertEqual(console.export_text(), "")

    def test_thinking_mode_values(self):
        """Verify ThinkingMode enum values."""
        self.assertEqual([mode.value for mode in ThinkingMode], ["short", "full", "off"])

    def test_thinking_streamer_separates_sections(self):
        """Verify the streamer only labels thinking, leaving content display separate."""
        console = Console(record=True, width=100)
        streamer = ThinkingStreamer(console, mode=ThinkingMode.FULL)
        streamer.feed("Okay")
        streamer.feed(" let me think.")
        streamer.finish()
        output = console.export_text()
        self.assertTrue(output.startswith("Thinking: Okay let me think."))
        self.assertIn("\n", output)

    def test_thinking_streamer_off_prints_nothing(self):
        """Verify OFF mode produces no output at all."""
        console = Console(record=True, width=100)
        streamer = ThinkingStreamer(console, mode=ThinkingMode.OFF)
        streamer.feed("hidden")
        streamer.finish()
        self.assertEqual(console.export_text(), "")

    def test_thinking_streamer_short_truncates(self):
        """Verify SHORT mode truncates and adds the expansion hint on finish."""
        console = Console(record=True, width=100)
        streamer = ThinkingStreamer(console, mode=ThinkingMode.SHORT, max_length=20)
        streamer.feed("x" * 40)
        streamer.finish()
        output = console.export_text()
        self.assertTrue(output.startswith("Thinking: xxxxxxxxxxxxxxxxxxxx"))
        self.assertIn("/thinking full", output)


if __name__ == "__main__":
    unittest.main()

