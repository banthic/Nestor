"""State and safety budgets for one bounded model/tool agent run."""

from dataclasses import dataclass

DEFAULT_MAX_ITERATIONS = 12
DEFAULT_MAX_TOOL_CALLS = 40


@dataclass
class AgentLoop:
    """Track reasoning rounds and tool actions for one user request."""

    max_iterations: int = DEFAULT_MAX_ITERATIONS
    max_tool_calls: int = DEFAULT_MAX_TOOL_CALLS
    iterations: int = 0
    tool_calls: int = 0

    def start_iteration(self) -> bool:
        """Reserve the next model round, returning false at the configured limit."""
        if self.iterations >= self.max_iterations:
            return False
        self.iterations += 1
        return True

    def reserve_tool_call(self) -> bool:
        """Reserve one action, returning false when the action budget is exhausted."""
        if self.tool_calls >= self.max_tool_calls:
            return False
        self.tool_calls += 1
        return True

    def iteration_limit_message(self) -> str:
        return "Maximum tool iterations reached."

    def tool_limit_message(self) -> str:
        return (
            f"Agent loop reached its {self.max_tool_calls}-tool-call limit. "
            "The task may be incomplete; ask Nestor to continue from the latest result."
        )
