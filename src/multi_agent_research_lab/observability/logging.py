"""Rich console logging with per-agent color coding.

Provides beautiful structured logging as specified in lab_plan.md Phase 5.
Baseline gets one color, multi-agent gets per-agent colors.
"""

import logging
import sys

from rich.console import Console
from rich.logging import RichHandler
from rich.theme import Theme

# Agent-specific color theme
AGENT_THEME = Theme({
    "guardrail": "bold magenta",
    "supervisor": "bold cyan",
    "researcher": "bold green",
    "analyst": "bold yellow",
    "writer": "bold blue",
    "critic": "bold red",
    "baseline": "bold white",
    "system": "dim",
})

# Agent emoji mapping
AGENT_EMOJI = {
    "guardrail": "🛡️ ",
    "supervisor": "🧭",
    "researcher": "🔍",
    "analyst": "📊",
    "writer": "✍️ ",
    "critic": "⚖️ ",
    "baseline": "🤖",
}

console = Console(theme=AGENT_THEME)


def configure_logging(level: str = "INFO") -> None:
    """Configure rich logging with structured format."""
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(message)s",
        datefmt="[%X]",
        handlers=[
            RichHandler(
                console=console,
                show_path=False,
                markup=True,
                rich_tracebacks=True,
            )
        ],
        force=True,
    )

    # Suppress noisy loggers
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("openai").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)


def log_agent_event(
    agent_name: str,
    message: str,
    duration_ms: float | None = None,
    cost_usd: float | None = None,
) -> None:
    """Log a structured agent event with emoji and optional metrics."""
    emoji = AGENT_EMOJI.get(agent_name, "❓")
    parts = [f"{emoji} [{agent_name}]", message]

    if duration_ms is not None:
        if duration_ms >= 1000:
            parts.append(f"{duration_ms/1000:.1f}s")
        else:
            parts.append(f"{duration_ms:.0f}ms")

    if cost_usd is not None:
        parts.append(f"${cost_usd:.4f}")

    style = agent_name if agent_name in AGENT_EMOJI else "system"
    console.print(" ".join(parts), style=style)
