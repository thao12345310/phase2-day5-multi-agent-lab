"""Benchmark runner for single-agent vs multi-agent comparison.

Measures latency, cost, citation coverage, and failure rate.
"""

import logging
import time
from typing import Callable

from multi_agent_research_lab.core.schemas import BenchmarkMetrics
from multi_agent_research_lab.core.state import ResearchState

log = logging.getLogger(__name__)

Runner = Callable[[str], ResearchState]


def run_benchmark(run_name: str, query: str, runner: Runner) -> tuple[ResearchState, BenchmarkMetrics]:
    """Measure latency, cost, and quality for a single run.

    Args:
        run_name: Identifier for this benchmark run
        query: The research query to benchmark
        runner: Callable that takes a query string and returns ResearchState

    Returns:
        Tuple of (final_state, metrics)
    """
    started = perf_counter = time.perf_counter()
    state = runner(query)
    latency = time.perf_counter() - started

    # Calculate citation coverage
    citation_coverage = _calculate_citation_coverage(state)

    metrics = BenchmarkMetrics(
        run_name=run_name,
        latency_seconds=latency,
        estimated_cost_usd=state.total_cost_usd,
        citation_coverage=citation_coverage,
        failure=state.error is not None,
        agents_called=state.route_history,
        notes=query[:50],
    )

    log.info(
        f"Benchmark [{run_name}]: {latency:.1f}s, "
        f"${state.total_cost_usd:.4f}, "
        f"coverage={citation_coverage:.2f}"
    )

    return state, metrics


def _calculate_citation_coverage(state: ResearchState) -> float:
    """Calculate ratio of main claims with supporting citations."""
    if not state.analysis_notes:
        return 0.0

    main_claims = []
    for analysis in state.analysis_notes:
        for claim in analysis.claims:
            if isinstance(claim, dict) and claim.get("is_main", False):
                main_claims.append(claim)

    if not main_claims:
        if state.final_answer and state.final_answer.citations:
            return min(1.0, len(state.final_answer.citations) / 3)
        return 0.0

    if state.final_answer and state.final_answer.citations:
        covered = min(len(main_claims), len(state.final_answer.citations))
        return covered / len(main_claims)
    return 0.0
