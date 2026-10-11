"""Tests for Zetelton gateway (provider calls + tool use loop)."""

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import agent.gateway.gateway as gateway_module
from agent.gateway import Gateway
from agent.gateway.gateway import SYSTEM_PROMPT, ModelResponse, StreamChunk
from agent.tools import QuitRequested, get_tools


def _ollama_message(content="", tool_calls=None, thinking=""):
    return {
        "message": {
            "role": "assistant",
            "content": content,
            "thinking": thinking,
            "tool_calls": tool_calls or [],
        }
    }


class TestGateway(unittest.TestCase):
    def setUp(self):
        self.gw = Gateway(tools=get_tools())
        self.gw.default_provider = "local_ollama"
        self.gw.ollama_model = "test-model"

    @patch.object(gateway_module.ollama, "chat", return_value=_ollama_message("Hello there"))
    def test_direct_reply(self, mock_chat):
        response = self.gw.generate_text("Hi")
        self.assertIsInstance(response, ModelResponse)
        self.assertEqual(response.content, "Hello there")
        self.assertEqual(response.thinking, "")

    @patch.object(
        gateway_module.ollama,
        "chat",
        return_value=_ollama_message("Final answer", thinking="Let me think"),
    )
    def test_thinking_extracted(self, mock_chat):
        response = self.gw.generate_text("Why?")
        self.assertEqual(response.thinking, "Let me think")
        self.assertEqual(response.content, "Final answer")

    @patch.object(
        gateway_module.ollama,
        "chat",
        return_value=_ollama_message("Ok"),
    )
    def test_system_prompt_prepended(self, mock_chat):
        self.gw.generate_text("Hi", history=[{"role": "user", "content": "earlier"}])
        kwargs = mock_chat.call_args.kwargs
        self.assertEqual(kwargs["messages"][0]["role"], "system")
        self.assertEqual(kwargs["messages"][0]["content"], SYSTEM_PROMPT)

    def test_system_prompt_describes_readfile(self):
        self.assertIn("readfile reads and returns the content", SYSTEM_PROMPT)
        self.assertIn("MUST inspect the project first", SYSTEM_PROMPT)
        self.assertIn("Never invent source code", SYSTEM_PROMPT)

    @patch.object(
        gateway_module.ollama,
        "chat",
        return_value=_ollama_message("Bonjour !"),
    )
    def test_tools_are_available_for_greeting_without_forcing_tool_use(self, mock_chat):
        self.gw.generate_text("bonjour ?")
        self.assertIn("tools", mock_chat.call_args.kwargs)

    @patch.object(
        gateway_module.ollama,
        "chat",
        return_value=_ollama_message("Ok"),
    )
    def test_tools_attached_when_keyword_present(self, mock_chat):
        self.gw.generate_text("liste les fichiers du dossier /tmp")
        self.assertIn("tools", mock_chat.call_args.kwargs)

    @patch.object(
        gateway_module.ollama,
        "chat",
        return_value=_ollama_message("Ok"),
    )
    def test_tools_attached_when_prompt_mentions_file_name(self, mock_chat):
        self.gw.generate_text("et dans chatbot.py y'a quoi")
        self.assertIn("tools", mock_chat.call_args.kwargs)

    @patch.object(
        gateway_module.ollama,
        "chat",
        return_value=_ollama_message("Ok"),
    )
    def test_tools_attached_when_tool_name_present(self, mock_chat):
        self.gw.generate_text("quitte maintenant")
        self.assertIn("tools", mock_chat.call_args.kwargs)

    @patch.object(
        gateway_module.ollama,
        "chat",
        side_effect=[[_ollama_message(tool_calls=[
            {"function": {"name": "quit", "arguments": {}}}
        ])]],
    )
    def test_quit_tool_propagates_quit_requested(self, mock_chat):
        with self.assertRaises(QuitRequested):
            list(self.gw.stream_text("quitte maintenant"))

    def test_tool_use_flow(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "report.txt").touch()
            tool_response = _ollama_message(tool_calls=[
                {"function": {"name": "listfiles", "arguments": {"path": tmp}}}
            ])
            final_response = _ollama_message("Here is the listing!")
            with patch.object(
                gateway_module.ollama,
                "chat",
                side_effect=[tool_response, final_response],
            ) as mock_chat:
                response = self.gw.generate_text("List the files")

        self.assertEqual(response.content, "Here is the listing!")
        called_messages = mock_chat.call_args_list[1].kwargs["messages"]
        self.assertTrue(any(
            msg["role"] == "tool" and "report.txt" in msg["content"]
            for msg in called_messages
        ))

    def test_tool_failure_fed_back(self):
        tool_response = _ollama_message(tool_calls=[
            {"function": {"name": "broken_tool", "arguments": {}}}
        ])
        final_response = _ollama_message("I ran into a problem.")
        with patch.object(
            gateway_module.ollama,
            "chat",
            side_effect=[tool_response, final_response],
        ) as mock_chat:
            response = self.gw.generate_text("Do something")

        self.assertEqual(response.content, "I ran into a problem.")
        called_messages = mock_chat.call_args_list[1].kwargs["messages"]
        self.assertTrue(any(
            msg["role"] == "tool" and "failed" in msg["content"]
            for msg in called_messages
        ))

    @patch.object(
        gateway_module.ollama,
        "chat",
        side_effect=lambda **kwargs: _ollama_message(tool_calls=[
            {"function": {"name": "listfiles", "arguments": {"path": "/"}}}
        ]),
    )
    def test_max_tool_iterations(self, mock_chat):
        response = self.gw.generate_text("Loop forever")
        self.assertEqual(response.content, "Maximum tool iterations reached.")

    def test_unknown_provider_raises(self):
        self.gw.default_provider = "mars_provider"
        with self.assertRaises(ValueError):
            self.gw.generate_text("Hi")

    def test_openai_tool_calls_normalized(self):
        message = SimpleNamespace(
            content="call me",
            thinking="reasoning here",
            tool_calls=[
                SimpleNamespace(
                    id="call_123",
                    function=SimpleNamespace(name="listfiles", arguments='{"path": "/"}'),
                )
            ],
        )
        response = SimpleNamespace(
            choices=[SimpleNamespace(message=message)]
        )
        fake_client = SimpleNamespace(
            chat=SimpleNamespace(completions=SimpleNamespace(create=lambda **kwargs: response))
        )
        self.gw.default_provider = "external_api_openai_compatible"
        self.gw.openai_client = fake_client

        content, thinking, tool_calls = self.gw._call_openai([], None)
        self.assertEqual(content, "call me")
        self.assertEqual(thinking, "reasoning here")
        self.assertEqual(tool_calls[0]["id"], "call_123")
        self.assertEqual(tool_calls[0]["name"], "listfiles")
        self.assertEqual(tool_calls[0]["arguments"], {"path": "/"})


class TestStream(unittest.TestCase):
    def setUp(self):
        self.gw = Gateway(tools=get_tools())
        self.gw.default_provider = "local_ollama"
        self.gw.ollama_model = "test-model"

    @patch.object(
        gateway_module.ollama,
        "chat",
        return_value=[
            _ollama_message(content="Hel"),
            _ollama_message(content="lo there"),
        ],
    )
    def test_stream_content(self, mock_chat):
        chunks = list(self.gw.stream_text("Hi"))
        self.assertEqual(chunks, [
            StreamChunk("status", "Thinking"),
            StreamChunk("content", "Hel"),
            StreamChunk("content", "lo there"),
        ])

    @patch.object(
        gateway_module.ollama,
        "chat",
        return_value=[
            _ollama_message(thinking="I think"),
            _ollama_message(content="Answer"),
        ],
    )
    def test_stream_thinking_and_content(self, mock_chat):
        chunks = list(self.gw.stream_text("Why?"))
        self.assertEqual(chunks, [
            StreamChunk("status", "Thinking"),
            StreamChunk("thinking", "I think"),
            StreamChunk("content", "Answer"),
        ])

    def test_openai_stream_reassembles_tool_call_fragments(self):
        chunks = [
            SimpleNamespace(choices=[SimpleNamespace(delta=SimpleNamespace(
                content=None,
                thinking=None,
                tool_calls=[SimpleNamespace(
                    index=0,
                    id="call_1",
                    function=SimpleNamespace(name="readfile", arguments=""),
                )],
            ))]),
            SimpleNamespace(choices=[SimpleNamespace(delta=SimpleNamespace(
                content=None,
                thinking=None,
                tool_calls=[SimpleNamespace(
                    index=0,
                    id=None,
                    function=SimpleNamespace(name=None, arguments='{"path":'),
                )],
            ))]),
            SimpleNamespace(choices=[SimpleNamespace(delta=SimpleNamespace(
                content=None,
                thinking=None,
                tool_calls=[SimpleNamespace(
                    index=0,
                    id=None,
                    function=SimpleNamespace(name=None, arguments='"/tmp/chatbot.py"}'),
                )],
            ))]),
        ]
        fake_client = SimpleNamespace(
            chat=SimpleNamespace(
                completions=SimpleNamespace(create=lambda **kwargs: chunks),
            ),
        )
        self.gw.default_provider = "external_api_openai_compatible"
        self.gw.openai_client = fake_client

        stream = self.gw._stream_openai([], None)
        try:
            while True:
                next(stream)
        except StopIteration as result:
            _content, _thinking, tool_calls = result.value

        self.assertEqual(tool_calls, [{
            "id": "call_1",
            "name": "readfile",
            "arguments": {"path": "/tmp/chatbot.py"},
        }])

    def test_stream_provider_rate_limit_is_returned_as_error_chunk(self):
        error = RuntimeError("upstream provider is overloaded")
        error.status_code = 429
        self.gw.default_provider = "local_ollama"
        self.gw._stream_ollama = lambda messages, tools: (_ for _ in ()).throw(error)

        chunks = list(self.gw.stream_text("Hi"))

        self.assertEqual(chunks, [StreamChunk("status", "Thinking"), StreamChunk(
            "error",
            "Le fournisseur IA est temporairement saturé (429). Réessayez dans quelques secondes.",
        )])

    def test_stream_tool_loop(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "data.txt").touch()
            first_turn = [
                {"message": {"role": "assistant", "content": "", "thinking": "", "tool_calls": [
                    {"function": {"name": "listfiles", "arguments": {"path": tmp}}}
                ]}}
            ]
            second_turn = [_ollama_message(content="Here is the list.")]
            with patch.object(
                gateway_module.ollama,
                "chat",
                side_effect=[first_turn, second_turn],
            ) as mock_chat:
                chunks = list(self.gw.stream_text("List the files"))

        types = [chunk.type for chunk in chunks]
        self.assertIn("tool_call", types)
        self.assertIn("tool_result", types)
        self.assertEqual(chunks[-1], StreamChunk("content", "Here is the list."))
        self.assertEqual(mock_chat.call_count, 2)

    @patch.object(
        gateway_module.ollama,
        "chat",
        side_effect=lambda **kwargs: [{"message": {"role": "assistant", "content": "", "thinking": "", "tool_calls": [
            {"function": {"name": "broken_tool", "arguments": {}}}
        ]}}],
    )
    def test_stream_max_iterations(self, mock_chat):
        chunks = list(self.gw.stream_text("Loop"))
        self.assertEqual(chunks[-1], StreamChunk("error", "Maximum tool iterations reached."))


if __name__ == "__main__":
    unittest.main()