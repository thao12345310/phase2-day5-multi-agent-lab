"""Benchmark endpoints: /benchmark/run, /benchmark/{id}."""

import time
import uuid

from fastapi import APIRouter
from pydantic import BaseModel

from multi_agent_research_lab.core.schemas import BenchmarkMetrics, ResearchQuery
from multi_agent_research_lab.core.state import ResearchState
from multi_agent_research_lab.graph.baseline import BaselineAgent
from multi_agent_research_lab.graph.workflow import MultiAgentWorkflow

router = APIRouter()

# In-memory benchmark storage
_benchmarks: dict[str, dict] = {}


class BenchmarkRequest(BaseModel):
    queries: list[str] = [
        "Research GraphRAG state-of-the-art and write a 500-word summary",
        "Compare single-agent and multi-agent workflows",
    ]
    modes: list[str] = ["baseline", "multi-agent"]
    repeats: int = 1


class BenchmarkResponse(BaseModel):
    benchmark_id: str
    status: str = "completed"
    results: list[dict] = []


@router.post("/run")
def run_benchmark(req: BenchmarkRequest) -> BenchmarkResponse:
    """Run a benchmark comparing modes across queries."""
    benchmark_id = str(uuid.uuid4())[:8]
    results = []

    for query in req.queries:
        for mode in req.modes:
            for repeat in range(req.repeats):
                start = time.perf_counter()
                state = ResearchState(request=ResearchQuery(query=query))

                try:
                    if mode == "baseline":
                        agent = BaselineAgent()
                        state = agent.run(state)
                    else:
                        workflow = MultiAgentWorkflow(enable_critic="critic" in mode)
                        state = workflow.run(state)

                    latency = time.perf_counter() - start
                    metrics = BenchmarkMetrics(
                        run_name=f"{mode}_{repeat}",
                        latency_seconds=latency,
                        estimated_cost_usd=state.total_cost_usd,
                        citation_coverage=_calc_citation_coverage(state),
                        failure=state.error is not None,
                        agents_called=state.route_history,
                        notes=query[:50],
                    )
                    results.append(metrics.model_dump())

                except Exception as e:
                    results.append({
                        "run_name": f"{mode}_{repeat}",
                        "error": str(e),
                        "failure": True,
                    })

    _benchmarks[benchmark_id] = {"results": results}
    return BenchmarkResponse(
        benchmark_id=benchmark_id,
        status="completed",
        results=results,
    )


@router.get("/{benchmark_id}")
def get_benchmark(benchmark_id: str) -> dict:
    """Retrieve benchmark results."""
    if benchmark_id in _benchmarks:
        return _benchmarks[benchmark_id]
    return {"error": "Benchmark not found"}


def _calc_citation_coverage(state: ResearchState) -> float:
    """Calculate citation coverage metric."""
    if not state.analysis_notes:
        return 0.0

    main_claims = []
    for analysis in state.analysis_notes:
        for claim in analysis.claims:
            if isinstance(claim, dict) and claim.get("is_main", False):
                main_claims.append(claim)

    if not main_claims:
        # If no claims flagged as main, check if answer has citations
        if state.final_answer and state.final_answer.citations:
            return min(1.0, len(state.final_answer.citations) / 3)
        return 0.0

    if state.final_answer and state.final_answer.citations:
        covered = min(len(main_claims), len(state.final_answer.citations))
        return covered / len(main_claims)
    return 0.0
