"""Critic agent — independent quality reviewer for bonus work."""

import logging
import time

from multi_agent_research_lab.agents.base import BaseAgent, load_prompt
from multi_agent_research_lab.core.schemas import AgentName, AgentResult, CriticNote
from multi_agent_research_lab.core.state import ResearchState
from multi_agent_research_lab.observability.logging import log_agent_event
from multi_agent_research_lab.observability.tracing import trace_span
from multi_agent_research_lab.services.llm_client import LLMClient

log = logging.getLogger(__name__)


class CriticAgent(BaseAgent):
    """Independent quality reviewer scoring drafts on 4 axes.

    Scores: factual / coherence / completeness / citations (each 1-10).
    Requests revision only if overall_score < 7 and max 1 revision.
    """

    name = "critic"

    def __init__(self) -> None:
        self._llm = LLMClient(model="claude-haiku-4-5", temperature=0.1, max_tokens=1024)
        self._system_prompt = load_prompt("critic")

    def run(self, state: ResearchState) -> ResearchState:
        """Evaluate final answer and append critic feedback."""
        if not state.final_answer:
            log.warning("Critic called but no final answer to review")
            return state

        started = time.perf_counter()

        with trace_span("critic", {"has_previous_feedback": bool(state.critic_feedback)}) as span:
            try:
                # Build review context
                user_prompt = (
                    f"## Original Query\n{state.request.query}\n\n"
                    f"## Draft to Review\n{state.final_answer.content}\n\n"
                    f"## Citations Provided\n"
                    + "\n".join(f"- {c}" for c in state.final_answer.citations)
                    + f"\n\n## Word Count: {state.final_answer.word_count}\n"
                    f"## Research Sources Available: {len(state.sources)}\n\n"
                    f"Evaluate this draft on the 4 axes."
                )

                result = self._llm.complete_json(self._system_prompt, user_prompt)

                meta = result.pop("_llm_response", {})
                cost_usd = meta.get("cost_usd", 0.0)
                state.add_cost(
                    meta.get("input_tokens", 0),
                    meta.get("output_tokens", 0),
                    cost_usd,
                )

                note = CriticNote(
                    factual_score=min(10, max(1, result.get("factual_score", 5))),
                    coherence_score=min(10, max(1, result.get("coherence_score", 5))),
                    completeness_score=min(10, max(1, result.get("completeness_score", 5))),
                    citation_score=min(10, max(1, result.get("citation_score", 5))),
                    overall_score=min(10.0, max(1.0, result.get("overall_score", 5.0))),
                    reasoning=result.get("reasoning", ""),
                    revision_requested=result.get("revision_requested", False),
                    suggestions=result.get("suggestions", []),
                )

                # Only allow revision request if under limit
                if note.revision_requested and state.writer_revisions >= 1:
                    note.revision_requested = False
                    log.info("Critic: revision already done, not requesting another")

                state.critic_feedback.append(note)

                # Record agent result
                state.agent_results.append(AgentResult(
                    agent=AgentName.CRITIC,
                    content=note.reasoning,
                    metadata={
                        "overall_score": note.overall_score,
                        "factual": note.factual_score,
                        "coherence": note.coherence_score,
                        "completeness": note.completeness_score,
                        "citations": note.citation_score,
                        "revision_requested": note.revision_requested,
                    },
                ))

                elapsed_ms = (time.perf_counter() - started) * 1000
                span["overall_score"] = note.overall_score
                span["revision_requested"] = note.revision_requested

                state.add_trace_event("critic", {
                    "overall_score": note.overall_score,
                    "revision_requested": note.revision_requested,
                    "suggestions": note.suggestions,
                    "duration_ms": elapsed_ms,
                    "cost_usd": cost_usd,
                })

                log_agent_event(
                    "critic",
                    f"score {note.overall_score}/10, revision={note.revision_requested}",
                    elapsed_ms,
                    cost_usd,
                )

            except Exception as e:
                log.error(f"Critic failed: {e}")
                state.errors.append(f"Critic error: {e}")
                # Add a passing score to not block the workflow
                state.critic_feedback.append(CriticNote(
                    overall_score=7.0,
                    reasoning=f"Critic evaluation failed: {e}",
                    revision_requested=False,
                ))

        return state
