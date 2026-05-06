"""Tests for guardrail agent."""

from multi_agent_research_lab.core.schemas import ResearchQuery
from multi_agent_research_lab.core.state import ResearchState


def test_guardrail_passes_safe_query() -> None:
    """Safe research query should pass guardrail."""
    from multi_agent_research_lab.agents.guardrail import GuardrailAgent

    state = ResearchState(request=ResearchQuery(query="What is GraphRAG?"))
    agent = GuardrailAgent()
    result = agent.run(state)
    assert result.guardrail_passed is True
    assert result.error is None
