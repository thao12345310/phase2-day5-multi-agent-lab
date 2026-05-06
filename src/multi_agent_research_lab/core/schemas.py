"""Public schemas exchanged between CLI, agents, and evaluators."""

from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, Field


class AgentName(StrEnum):
    SUPERVISOR = "supervisor"
    RESEARCHER = "researcher"
    ANALYST = "analyst"
    WRITER = "writer"
    CRITIC = "critic"
    GUARDRAIL = "guardrail"


class ResearchQuery(BaseModel):
    query: str = Field(..., min_length=5)
    max_sources: int = Field(default=5, ge=1, le=20)
    audience: str = "technical learners"


class SourceDocument(BaseModel):
    title: str
    url: str | None = None
    snippet: str
    published_date: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class ResearchNote(BaseModel):
    """Structured note from the Researcher agent."""
    query_used: str
    sources: list[SourceDocument] = Field(default_factory=list)
    summary: str
    loop_index: int = 0  # which research loop produced this


class AnalysisNote(BaseModel):
    """Output of the Analyst agent."""
    claims: list[dict[str, Any]] = Field(default_factory=list)
    gaps: list[str] = Field(default_factory=list)
    needs_more_research: bool = False
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    summary: str = ""


class CriticNote(BaseModel):
    """Output of the Critic agent."""
    factual_score: int = Field(default=5, ge=1, le=10)
    coherence_score: int = Field(default=5, ge=1, le=10)
    completeness_score: int = Field(default=5, ge=1, le=10)
    citation_score: int = Field(default=5, ge=1, le=10)
    overall_score: float = Field(default=5.0, ge=1.0, le=10.0)
    reasoning: str = ""
    revision_requested: bool = False
    suggestions: list[str] = Field(default_factory=list)


class FinalAnswer(BaseModel):
    """Final output produced by the Writer agent."""
    content: str
    citations: list[str] = Field(default_factory=list)
    word_count: int = 0


class PlanStep(BaseModel):
    """A single planning/routing decision for transparency."""
    agent: str
    reason: str
    iteration: int


class FallbackEvent(BaseModel):
    """Record of a provider fallback during a run."""
    from_provider: str
    to_provider: str
    reason: str
    timestamp: str = ""


class ErrorInfo(BaseModel):
    """Friendly error info stored in state."""
    code: str
    message: str
    agent: str | None = None


class RouteDecision(BaseModel):
    """Structured routing decision from the Supervisor."""
    next_agent: Literal["researcher", "analyst", "writer", "critic", "done"]
    reason: str
    sub_queries: list[str] | None = None


class GuardrailDecision(BaseModel):
    """Result from the guardrail filter."""
    passed: bool
    category: Literal["safe", "sensitive", "out_of_scope", "policy_violation"] = "safe"
    reason: str = ""


class AgentResult(BaseModel):
    agent: AgentName
    content: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class BenchmarkMetrics(BaseModel):
    run_name: str
    latency_seconds: float
    estimated_cost_usd: float | None = None
    quality_score: float | None = Field(default=None, ge=0, le=10)
    citation_coverage: float | None = Field(default=None, ge=0, le=1)
    failure: bool = False
    agents_called: list[str] = Field(default_factory=list)
    notes: str = ""
