"""Analyst agent — evaluates research notes, extracts claims, identifies gaps."""

import logging
import time

from multi_agent_research_lab.agents.base import BaseAgent, load_prompt
from multi_agent_research_lab.core.schemas import AgentName, AgentResult, AnalysisNote
from multi_agent_research_lab.core.state import ResearchState
from multi_agent_research_lab.observability.logging import log_agent_event
from multi_agent_research_lab.observability.tracing import trace_span
from multi_agent_research_lab.services.llm_client import LLMClient

log = logging.getLogger(__name__)


class AnalystAgent(BaseAgent):
    """Turns research notes into structured insights with gap analysis."""

    name = "analyst"

    def __init__(self) -> None:
        self._llm = LLMClient(model="gpt-4o-mini", temperature=0.1, max_tokens=1536)
        self._system_prompt = load_prompt("analyst")

    def run(self, state: ResearchState) -> ResearchState:
        """Populate state.analysis_notes with claims, gaps, and confidence."""
        started = time.perf_counter()

        with trace_span("analyst", {"research_notes": len(state.research_notes)}) as span:
            try:
                # Collect all research notes
                notes_text = "\n\n---\n\n".join(
                    f"Research Note (loop {n.loop_index}):\n{n.summary}"
                    for n in state.research_notes
                )

                sources_text = "\n".join(
                    f"- {s.title}: {s.snippet[:100]}..."
                    for s in state.sources[:10]
                )

                result = self._llm.complete_json(
                    self._system_prompt,
                    f"Original query: {state.request.query}\n\n"
                    f"Research notes:\n{notes_text}\n\n"
                    f"Available sources:\n{sources_text}\n\n"
                    f"Current research loops: {state.research_loops}/2\n"
                    f"Analyze these findings and identify claims, gaps, and confidence.",
                )

                meta = result.pop("_llm_response", {})
                cost_usd = meta.get("cost_usd", 0.0)
                state.add_cost(
                    meta.get("input_tokens", 0),
                    meta.get("output_tokens", 0),
                    cost_usd,
                )

                # Create analysis note
                note = AnalysisNote(
                    claims=result.get("claims", []),
                    gaps=result.get("gaps", []),
                    needs_more_research=result.get("needs_more_research", False),
                    confidence=min(1.0, max(0.0, result.get("confidence", 0.5))),
                    summary=result.get("summary", ""),
                )

                # Don't request more research if we're at the loop limit
                if state.research_loops >= 2:
                    note.needs_more_research = False
                    log.info("Analyst: max research loops reached, proceeding to writer")

                state.analysis_notes.append(note)

                # Record agent result
                state.agent_results.append(AgentResult(
                    agent=AgentName.ANALYST,
                    content=note.summary,
                    metadata={
                        "claims": len(note.claims),
                        "gaps": len(note.gaps),
                        "needs_more_research": note.needs_more_research,
                        "confidence": note.confidence,
                    },
                ))

                elapsed_ms = (time.perf_counter() - started) * 1000
                span["claims"] = len(note.claims)
                span["gaps"] = len(note.gaps)
                span["confidence"] = note.confidence

                state.add_trace_event("analyst", {
                    "claims": len(note.claims),
                    "gaps": note.gaps,
                    "needs_more_research": note.needs_more_research,
                    "confidence": note.confidence,
                    "duration_ms": elapsed_ms,
                    "cost_usd": cost_usd,
                })

                log_agent_event(
                    "analyst",
                    f"{len(note.claims)} claims, {len(note.gaps)} gaps, confidence={note.confidence:.2f}",
                    elapsed_ms,
                    cost_usd,
                )

            except Exception as e:
                log.error(f"Analyst failed: {e}")
                state.errors.append(f"Analyst error: {e}")
                # Create a minimal analysis note to allow workflow to continue
                state.analysis_notes.append(AnalysisNote(
                    claims=[],
                    gaps=[],
                    needs_more_research=False,
                    confidence=0.3,
                    summary=f"Analysis failed: {e}",
                ))

        return state
