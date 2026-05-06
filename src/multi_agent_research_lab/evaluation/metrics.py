"""Evaluation metrics computation.

Implements the 5 mandatory metrics from the lab guide:
1. Latency (wall-clock time)
2. Cost (token usage × pricing)
3. Quality (rubric-based)
4. Citation coverage
5. Failure rate
"""

from multi_agent_research_lab.core.state import ResearchState


def compute_citation_coverage(state: ResearchState) -> float:
    """Compute ratio of main claims with at least one supporting citation.

    Citation coverage is a hard metric that shows whether research was actually
    used in the final answer. If baseline coverage = 0.4 and multi-agent = 0.85,
    that's evidence the Researcher + Analyst are worth their tokens.
    """
    if not state.analysis_notes:
        return 0.0

    main_claims = []
    for analysis in state.analysis_notes:
        for claim in analysis.claims:
            if isinstance(claim, dict) and claim.get("is_main", False):
                main_claims.append(claim)

    if not main_claims:
        # Fallback: check citation count vs expected
        if state.final_answer and state.final_answer.citations:
            return min(1.0, len(state.final_answer.citations) / 3)
        return 0.0

    covered = sum(
        1 for c in main_claims
        if isinstance(c, dict) and c.get("citation_ids")
    )
    return covered / len(main_claims)


def compute_failure_rate(results: list[dict]) -> float:
    """Compute failure rate across benchmark runs.

    Failure = run has error state or raised exception.
    """
    if not results:
        return 0.0
    failures = sum(1 for r in results if r.get("failure", False) or r.get("error"))
    return failures / len(results)


def compute_cost_vnd(cost_usd: float, rate: float = 25_000) -> float:
    """Convert USD to VND at given exchange rate."""
    return cost_usd * rate
