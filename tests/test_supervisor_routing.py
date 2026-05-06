"""Tests for supervisor routing logic (mock LLM)."""

from multi_agent_research_lab.agents.supervisor import SupervisorAgent
from multi_agent_research_lab.core.schemas import (
    AnalysisNote,
    ErrorInfo,
    FinalAnswer,
    ResearchNote,
    ResearchQuery,
    CriticNote,
)
from multi_agent_research_lab.core.state import ResearchState


def _make_state(query: str = "Test query for routing") -> ResearchState:
    return ResearchState(request=ResearchQuery(query=query))


def test_route_to_researcher_when_no_notes() -> None:
    """First call should always go to researcher."""
    state = _make_state()
    result = SupervisorAgent().run(state)
    assert result.route_history[-1] == "researcher"


def test_route_to_analyst_after_research() -> None:
    """After research notes exist, should go to analyst."""
    state = _make_state()
    state.research_notes.append(
        ResearchNote(query_used="test", summary="findings", loop_index=0)
    )
    result = SupervisorAgent().run(state)
    assert result.route_history[-1] == "analyst"


def test_route_to_writer_after_analysis() -> None:
    """After analysis (no gaps), should go to writer."""
    state = _make_state()
    state.research_notes.append(
        ResearchNote(query_used="test", summary="findings", loop_index=0)
    )
    state.analysis_notes.append(
        AnalysisNote(needs_more_research=False, confidence=0.9, summary="done")
    )
    result = SupervisorAgent().run(state)
    assert result.route_history[-1] == "writer"


def test_route_to_researcher_on_gaps() -> None:
    """Analyst flags gaps → researcher again."""
    state = _make_state()
    state.research_notes.append(
        ResearchNote(query_used="test", summary="findings", loop_index=0)
    )
    state.analysis_notes.append(
        AnalysisNote(
            needs_more_research=True,
            gaps=["missing info"],
            confidence=0.5,
            summary="needs more",
        )
    )
    state.research_loops = 1  # first loop done
    result = SupervisorAgent().run(state)
    assert result.route_history[-1] == "researcher"


def test_route_done_on_error() -> None:
    """Error state → done immediately."""
    state = _make_state()
    state.error = ErrorInfo(code="test", message="fail")
    result = SupervisorAgent().run(state)
    assert result.route_history[-1] == "done"


def test_route_done_on_max_iterations() -> None:
    """Max iterations → done."""
    state = _make_state()
    state.iteration = 100
    result = SupervisorAgent().run(state)
    assert result.route_history[-1] == "done"


def test_route_done_after_final_answer() -> None:
    """Final answer exists and no critic → done."""
    state = _make_state()
    state.final_answer = FinalAnswer(content="answer", word_count=1)
    result = SupervisorAgent().run(state)
    assert result.route_history[-1] == "done"


def test_route_to_critic_when_enabled() -> None:
    """Critic enabled + final answer + no feedback → critic."""
    state = _make_state()
    state.final_answer = FinalAnswer(content="answer", word_count=1)
    result = SupervisorAgent(enable_critic=True).run(state)
    assert result.route_history[-1] == "critic"


def test_route_done_after_critic() -> None:
    """Critic feedback exists + final answer → done."""
    state = _make_state()
    state.final_answer = FinalAnswer(content="answer", word_count=1)
    state.critic_feedback.append(CriticNote(overall_score=8.0))
    result = SupervisorAgent(enable_critic=True).run(state)
    assert result.route_history[-1] == "done"
