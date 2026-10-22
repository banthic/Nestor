"""Tests for the interactive ask_user prompt."""

import unittest
from types import SimpleNamespace

from agent.discord_app.ui.ask import _AnswerView


def _member():
    return SimpleNamespace(id=1, mention="<@1>")


def _items(view):
    return [type(item).__name__ for item in view.children]


class TestAnswerView(unittest.TestCase):
    def test_options_build_a_selector(self):
        view = _AnswerView(_member(), "Pick one", ["Hive", "Nest"], True)

        self.assertIn("Select", _items(view))
        select = next(item for item in view.children if type(item).__name__ == "Select")
        self.assertEqual([option.label for option in select.options], ["Hive", "Nest"])

    def test_free_text_is_available_without_options(self):
        view = _AnswerView(_member(), "New name?", [], True)

        self.assertNotIn("Select", _items(view))
        self.assertIn("Button", _items(view))

    def test_options_are_capped_at_discord_limit(self):
        view = _AnswerView(_member(), "Pick one", [str(index) for index in range(30)], False)

        select = next(item for item in view.children if type(item).__name__ == "Select")
        self.assertEqual(len(select.options), 25)


if __name__ == "__main__":
    unittest.main()
