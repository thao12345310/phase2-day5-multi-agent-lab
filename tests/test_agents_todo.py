"""Tests for agent implementations — verifies agents are properly implemented."""

from multi_agent_research_lab.agents import SupervisorAgent
from multi_agent_research_lab.core.schemas import ResearchQuery
from multi_agent_research_lab.core.state import ResearchState


def test_supervisor_routes_to_researcher_initially() -> None:
    """Supervisor should route to researcher when no research notes exist."""
    state = ResearchState(request=ResearchQuery(query="Explain multi-agent systems"))
    result = SupervisorAgent().run(state)
    assert result.route_history[-1] == "researcher"
    assert result.iteration == 1
    assert len(result.planning_log) == 1
    assert result.planning_log[0].agent == "researcher"


def test_supervisor_routes_done_on_error() -> None:
    """Supervisor should route to done when error exists."""
    from multi_agent_research_lab.core.schemas import ErrorInfo

    state = ResearchState(request=ResearchQuery(query="Explain multi-agent systems"))
    state.error = ErrorInfo(code="test", message="test error")
    result = SupervisorAgent().run(state)
    assert result.route_history[-1] == "done"
