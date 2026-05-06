"""Shared state for the multi-agent workflow.

Golden rule: agents only APPEND to state, never overwrite — helps trace and debug.
"""

from typing import Any

from pydantic import BaseModel, Field

from multi_agent_research_lab.core.schemas import (
    AgentResult,
    AnalysisNote,
    CriticNote,
    ErrorInfo,
    FallbackEvent,
    FinalAnswer,
    PlanStep,
    ResearchNote,
    ResearchQuery,
    SourceDocument,
)


class ResearchState(BaseModel):
    """Single source of truth passed through the workflow."""

    request: ResearchQuery
    iteration: int = 0
    route_history: list[str] = Field(default_factory=list)

    # Guardrail
    guardrail_passed: bool = True

    # Research data
    sources: list[SourceDocument] = Field(default_factory=list)
    research_notes: list[ResearchNote] = Field(default_factory=list)
    research_loops: int = 0

    # Analysis data
    analysis_notes: list[AnalysisNote] = Field(default_factory=list)

    # Writer output
    final_answer: FinalAnswer | None = None

    # Critic output (bonus)
    critic_feedback: list[CriticNote] = Field(default_factory=list)
    writer_revisions: int = 0

    # Transparency & observability
    planning_log: list[PlanStep] = Field(default_factory=list)
    agent_results: list[AgentResult] = Field(default_factory=list)
    trace: list[dict[str, Any]] = Field(default_factory=list)

    # Cost tracking
    total_cost_usd: float = 0.0
    total_input_tokens: int = 0
    total_output_tokens: int = 0

    # Error handling
    fallback_events: list[FallbackEvent] = Field(default_factory=list)
    error: ErrorInfo | None = None
    errors: list[str] = Field(default_factory=list)

    def record_route(self, route: str) -> None:
        self.route_history.append(route)
        self.iteration += 1

    def add_trace_event(self, name: str, payload: dict[str, Any]) -> None:
        import time
        self.trace.append({
            "name": name,
            "timestamp": time.time(),
            "iso_time": time.strftime("%H:%M:%S"),
            "payload": payload,
        })

    def add_cost(self, input_tokens: int, output_tokens: int, cost_usd: float) -> None:
        """Accumulate token usage and cost."""
        self.total_input_tokens += input_tokens
        self.total_output_tokens += output_tokens
        self.total_cost_usd += cost_usd
