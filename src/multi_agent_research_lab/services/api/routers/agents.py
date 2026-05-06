"""Agent run endpoints: /run/baseline and /run/multi-agent."""

import time

from fastapi import APIRouter
from pydantic import BaseModel

from multi_agent_research_lab.core.schemas import ResearchQuery
from multi_agent_research_lab.core.state import ResearchState
from multi_agent_research_lab.graph.baseline import BaselineAgent
from multi_agent_research_lab.graph.workflow import MultiAgentWorkflow

router = APIRouter()


class RunRequest(BaseModel):
    query: str
    enable_critic: bool = False


class RunResponse(BaseModel):
    answer: str
    trace_id: str | None = None
    cost_usd: float = 0.0
    latency_seconds: float = 0.0
    agents_called: list[str] = []
    word_count: int = 0
    citations: list[str] = []
    errors: list[str] = []


@router.post("/baseline")
def run_baseline(req: RunRequest) -> RunResponse:
    """Run a single-agent baseline."""
    start = time.perf_counter()
    state = ResearchState(request=ResearchQuery(query=req.query))
    agent = BaselineAgent()
    state = agent.run(state)
    latency = time.perf_counter() - start

    return RunResponse(
        answer=state.final_answer.content if state.final_answer else "No answer",
        cost_usd=state.total_cost_usd,
        latency_seconds=latency,
        agents_called=["baseline"],
        word_count=state.final_answer.word_count if state.final_answer else 0,
        citations=state.final_answer.citations if state.final_answer else [],
        errors=state.errors,
    )


@router.post("/multi-agent")
def run_multi_agent(req: RunRequest) -> RunResponse:
    """Run the multi-agent workflow."""
    start = time.perf_counter()
    state = ResearchState(request=ResearchQuery(query=req.query))
    workflow = MultiAgentWorkflow(enable_critic=req.enable_critic)
    state = workflow.run(state)
    latency = time.perf_counter() - start

    return RunResponse(
        answer=state.final_answer.content if state.final_answer else "No answer",
        cost_usd=state.total_cost_usd,
        latency_seconds=latency,
        agents_called=state.route_history,
        word_count=state.final_answer.word_count if state.final_answer else 0,
        citations=state.final_answer.citations if state.final_answer else [],
        errors=state.errors,
    )
