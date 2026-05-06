"""Supervisor / router — orchestrator that decides which agent runs next."""

import logging
import time

from multi_agent_research_lab.agents.base import BaseAgent, load_prompt
from multi_agent_research_lab.core.config import get_settings
from multi_agent_research_lab.core.schemas import PlanStep, RouteDecision
from multi_agent_research_lab.core.state import ResearchState
from multi_agent_research_lab.observability.logging import log_agent_event
from multi_agent_research_lab.observability.tracing import trace_span
from multi_agent_research_lab.services.llm_client import LLMClient

log = logging.getLogger(__name__)


class SupervisorAgent(BaseAgent):
    """Decides which worker should run next and when to stop.

    Routing policy implemented as deterministic rules first,
    with LLM fallback for ambiguous cases.
    """

    name = "supervisor"

    def __init__(self, enable_critic: bool = False) -> None:
        self._llm = LLMClient(model="gpt-4o-mini", temperature=0.0, max_tokens=512)
        self._system_prompt = load_prompt("supervisor")
        self._enable_critic = enable_critic
        self._settings = get_settings()

    def _deterministic_route(self, state: ResearchState) -> RouteDecision | None:
        """Try deterministic routing rules before calling LLM.

        This handles the common cases cheaply without an LLM call.
        """
        # Check termination conditions first
        if state.error:
            return RouteDecision(next_agent="done", reason="Error occurred, stopping workflow")

        if state.iteration >= self._settings.max_iterations:
            return RouteDecision(
                next_agent="done",
                reason=f"Max iterations ({self._settings.max_iterations}) reached",
            )

        # Rule 5: Final answer exists, critic enabled, no feedback yet → critic
        if state.final_answer and self._enable_critic and not state.critic_feedback:
            return RouteDecision(
                next_agent="critic",
                reason="Draft ready for critic review",
            )

        # Rule 6: Critic score low, can revise → writer
        if state.critic_feedback and state.writer_revisions < 1:
            latest_critic = state.critic_feedback[-1]
            if latest_critic.overall_score < 7.0:
                return RouteDecision(
                    next_agent="writer",
                    reason=f"Critic score {latest_critic.overall_score}/10, requesting revision",
                )

        # Rule 7: Final answer exists and passed critic (or critic disabled) → done
        if state.final_answer:
            if not self._enable_critic or state.critic_feedback:
                return RouteDecision(
                    next_agent="done",
                    reason="Final answer complete",
                )

        # Rule 1: No research notes → researcher
        if not state.research_notes:
            return RouteDecision(
                next_agent="researcher",
                reason="No research notes yet, starting research",
            )

        # Rule 2: Has research but no analysis → analyst
        if state.research_notes and not state.analysis_notes:
            return RouteDecision(
                next_agent="analyst",
                reason="Research complete, need analysis",
            )

        # Rule 3: Analyst wants more research and under loop limit
        if state.analysis_notes:
            latest_analysis = state.analysis_notes[-1]
            if latest_analysis.needs_more_research and state.research_loops < 2:
                return RouteDecision(
                    next_agent="researcher",
                    reason=f"Analyst flagged gaps, research loop {state.research_loops + 1}/2",
                    sub_queries=latest_analysis.gaps[:3] if latest_analysis.gaps else None,
                )

        # Rule 4: Analysis done, no final answer → writer
        if state.analysis_notes and not state.final_answer:
            latest_analysis = state.analysis_notes[-1]
            if not latest_analysis.needs_more_research or state.research_loops >= 2:
                return RouteDecision(
                    next_agent="writer",
                    reason="Analysis complete, ready to write",
                )

        return None

    def run(self, state: ResearchState) -> ResearchState:
        """Route to next agent using deterministic rules, LLM fallback for edge cases."""
        started = time.perf_counter()
        cost_usd = 0.0

        with trace_span("supervisor", {"iteration": state.iteration}) as span:
            # Try deterministic routing first (no LLM cost)
            decision = self._deterministic_route(state)

            if decision is None:
                # Fallback: use LLM for ambiguous cases
                try:
                    context = self._build_context(state)
                    result = self._llm.complete_json(self._system_prompt, context)

                    meta = result.pop("_llm_response", {})
                    cost_usd = meta.get("cost_usd", 0.0)
                    state.add_cost(
                        meta.get("input_tokens", 0),
                        meta.get("output_tokens", 0),
                        cost_usd,
                    )

                    decision = RouteDecision(
                        next_agent=result.get("next_agent", "done"),
                        reason=result.get("reason", "LLM routing decision"),
                        sub_queries=result.get("sub_queries"),
                    )
                except Exception as e:
                    log.error(f"Supervisor LLM routing failed: {e}")
                    decision = RouteDecision(
                        next_agent="done",
                        reason=f"Routing failed: {e}",
                    )

            span["next_agent"] = decision.next_agent
            span["reason"] = decision.reason

        elapsed_ms = (time.perf_counter() - started) * 1000

        # Log the decision
        state.planning_log.append(PlanStep(
            agent=decision.next_agent,
            reason=decision.reason,
            iteration=state.iteration,
        ))
        state.record_route(decision.next_agent)
        state.add_trace_event("supervisor", {
            "next_agent": decision.next_agent,
            "reason": decision.reason,
            "iteration": state.iteration,
            "duration_ms": elapsed_ms,
            "cost_usd": cost_usd,
        })

        log_agent_event("supervisor", f"→ {decision.next_agent} ({decision.reason})", elapsed_ms, cost_usd)

        # Store sub_queries for researcher if provided
        if decision.sub_queries:
            state.add_trace_event("sub_queries", {"queries": decision.sub_queries})

        return state

    def _build_context(self, state: ResearchState) -> str:
        """Build context string for LLM routing decision."""
        parts = [f"Query: {state.request.query}"]
        parts.append(f"Iteration: {state.iteration}/{self._settings.max_iterations}")
        parts.append(f"Research loops: {state.research_loops}/2")
        parts.append(f"Research notes: {len(state.research_notes)}")
        parts.append(f"Analysis notes: {len(state.analysis_notes)}")
        parts.append(f"Has final answer: {state.final_answer is not None}")
        parts.append(f"Critic feedback: {len(state.critic_feedback)}")
        parts.append(f"Writer revisions: {state.writer_revisions}")
        parts.append(f"Cost so far: ${state.total_cost_usd:.4f}")
        if state.errors:
            parts.append(f"Errors: {state.errors[-1]}")
        return "\n".join(parts)
