"""Base agent contract.

The concrete agent classes use LLM client for intelligent processing.
Each agent reads shared state, performs its task, and appends results.
"""

from abc import ABC, abstractmethod
from pathlib import Path

from multi_agent_research_lab.core.state import ResearchState


def load_prompt(agent_name: str) -> str:
    """Load a prompt template from the prompts directory."""
    prompt_path = Path(__file__).parent / "prompts" / f"{agent_name}.md"
    if prompt_path.exists():
        return prompt_path.read_text(encoding="utf-8")
    return f"You are a {agent_name} agent."


class BaseAgent(ABC):
    """Minimal interface every agent must implement."""

    name: str

    @abstractmethod
    def run(self, state: ResearchState) -> ResearchState:
        """Read and update shared state, then return it."""
