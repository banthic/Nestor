from rich.console import Console
from rich.status import Status

from ..gateway import Gateway
from ..tools import QuitRequested, get_tools
from .interface import (
    MessageHistory,
    ThinkingMode,
    ThinkingStreamer,
    prompt_user,
    render_panel,
    render_prompt_frame,
)
from .markdown_engine import render_markdown

THINKING_USAGE = "/thinking <short|full|off>"


def _handle_thinking_command(console: Console, thinking_mode: ThinkingMode, arg: str) -> ThinkingMode:
    if not arg:
        console.print(f"[cyan]Usage: {THINKING_USAGE}[/cyan]")
        console.print(f"[cyan]Current mode: {thinking_mode.value}[/cyan]")
        return thinking_mode
    try:
        return ThinkingMode(arg)
    except ValueError:
        console.print(f"[cyan]Unknown mode: {arg}. {THINKING_USAGE}[/cyan]")
        return thinking_mode


def run_cli() -> None:
    console = Console()
    history = MessageHistory()
    thinking_mode = ThinkingMode.SHORT
    usage: dict[str, int] | None = None
    render_panel(console)

    while True:
        render_prompt_frame(console, usage)
        user_input = prompt_user()
        if user_input is None or user_input in ("quit", "q"):
            console.print("Exiting... Goodbye !")
            break

        if not user_input.strip():
            continue

        if user_input.startswith("/thinking"):
            arg = user_input[len("/thinking"):].strip()
            thinking_mode = _handle_thinking_command(console, thinking_mode, arg)
            continue

        history.add_user_message(user_input)
        gateway = Gateway(tools=get_tools())
        content_parts: list[str] = []
        response_usage: dict[str, int] | None = None
        thinking_stream = ThinkingStreamer(console, mode=thinking_mode)
        content_started = False
        activity: Status | None = None

        try:
            for chunk in gateway.stream_text(user_input, history.get_messages()[:-1]):
                if chunk.type == "status":
                    if activity is None:
                        activity = console.status("Thinking", spinner="dots")
                        activity.start()
                    else:
                        activity.update(chunk.text)
                elif chunk.type == "thinking":
                    if activity is not None:
                        activity.stop()
                        activity = None
                    thinking_stream.feed(chunk.text)
                elif chunk.type == "content":
                    if activity is not None:
                        activity.stop()
                        activity = None
                    content_started = True
                    content_parts.append(chunk.text)
                elif chunk.type == "tool_call":
                    if activity is not None:
                        activity.stop()
                        activity = None
                    console.print(f"[bright_cyan]╰─ tool · {chunk.tool}[/bright_cyan]")
                elif chunk.type == "tool_result":
                    console.print(f"[bright_green]   └─ done · {chunk.tool}[/bright_green]")
                elif chunk.type == "usage":
                    response_usage = chunk.usage
                elif chunk.type == "error":
                    if activity is not None:
                        activity.stop()
                        activity = None
                    console.print(f"[bold red]{chunk.text}[/bold red]", end="")
        except QuitRequested:
            if activity is not None:
                activity.stop()
            if not content_started:
                thinking_stream.finish()
            console.print()
            console.print("Goodbye !")
            break
        finally:
            if activity is not None:
                activity.stop()
        if not content_started:
            thinking_stream.finish()
        else:
            thinking_stream.finish()
            console.print("[bold blue]Agent:[/bold blue]")
            render_markdown(console, "".join(content_parts))
        console.print()
        if content_parts:
            output_text = "".join(content_parts)
            input_tokens = (response_usage or {}).get("prompt_tokens", max(1, len(user_input) // 4))
            output_tokens = (response_usage or {}).get("completion_tokens", max(1, len(output_text) // 4))
            total_tokens = (response_usage or {}).get("total_tokens", input_tokens + output_tokens)
            usage = {
                "prompt_tokens": input_tokens,
                "completion_tokens": output_tokens,
                "total_tokens": total_tokens,
            }
        history.add_assistant_message("".join(content_parts))
