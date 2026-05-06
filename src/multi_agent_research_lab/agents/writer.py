"""Writer agent — produces final answer from research and analysis notes."""

import logging

from multi_agent_research_lab.agents.base import BaseAgent, load_prompt
from multi_agent_research_lab.core.schemas import AgentName, AgentResult, FinalAnswer
from multi_agent_research_lab.core.state import ResearchState
from multi_agent_research_lab.services.llm_client import LLMClient

log = logging.getLogger(__name__)


class WriterAgent(BaseAgent):
    """Produces final answer from research and analysis notes.

    Respects word count constraints and includes proper citations.
    If critic feedback exists, addresses suggested improvements.
    """

    name = "writer"

    def __init__(self) -> None:
        self._llm = LLMClient(model="gpt-4o-mini", temperature=0.4, max_tokens=2048)
        self._system_prompt = load_prompt("writer")

    def run(self, state: ResearchState) -> ResearchState:
        """Populate state.final_answer with the written response."""
        try:
            # Build context from research + analysis
            research_text = "\n\n".join(
                f"Research Note {i+1} (loop {n.loop_index}):\n{n.summary}"
                for i, n in enumerate(state.research_notes)
            )

            analysis_text = "\n\n".join(
                f"Analysis {i+1}:\nClaims: {len(a.claims)}\nGaps: {a.gaps}\n"
                f"Confidence: {a.confidence}\nSummary: {a.summary}"
                for i, a in enumerate(state.analysis_notes)
            )

            sources_text = "\n".join(
                f"[{i+1}] {s.title} ({s.url or 'no url'})"
                for i, s in enumerate(state.sources[:10])
            )

            # Include critic feedback if this is a revision
            critic_section = ""
            if state.critic_feedback:
                latest = state.critic_feedback[-1]
                critic_section = (
                    f"\n\n## Critic Feedback (address these in revision):\n"
                    f"Score: {latest.overall_score}/10\n"
                    f"Suggestions:\n" +
                    "\n".join(f"- {s}" for s in latest.suggestions)
                )

            # Include previous draft if revising
            revision_context = ""
            if state.final_answer:
                revision_context = (
                    f"\n\n## Previous Draft (revise based on critic feedback):\n"
                    f"{state.final_answer.content[:1000]}"
                )

            user_prompt = (
                f"Query: {state.request.query}\n"
                f"Audience: {state.request.audience}\n\n"
                f"## Research Notes:\n{research_text}\n\n"
                f"## Analysis:\n{analysis_text}\n\n"
                f"## Available Sources:\n{sources_text}"
                f"{critic_section}"
                f"{revision_context}\n\n"
                f"Write the final response."
            )

            result = self._llm.complete_json(self._system_prompt, user_prompt)

            meta = result.pop("_llm_response", {})
            state.add_cost(
                meta.get("input_tokens", 0),
                meta.get("output_tokens", 0),
                meta.get("cost_usd", 0.0),
            )

            content = result.get("content", "")
            citations = result.get("citations", [])
            word_count = len(content.split()) if content else 0

            state.final_answer = FinalAnswer(
                content=content,
                citations=citations,
                word_count=word_count,
            )

            if state.critic_feedback:
                state.writer_revisions += 1

            # Record agent result
            state.agent_results.append(AgentResult(
                agent=AgentName.WRITER,
                content=content[:500],
                metadata={
                    "word_count": word_count,
                    "citations": len(citations),
                    "is_revision": state.writer_revisions > 0,
                },
            ))

            state.add_trace_event("writer", {
                "word_count": word_count,
                "citations": len(citations),
                "is_revision": state.writer_revisions > 0,
            })

            log.info(f"Writer produced {word_count} words with {len(citations)} citations")

        except Exception as e:
            log.error(f"Writer failed: {e}")
            state.errors.append(f"Writer error: {e}")
            # Produce a fallback answer from raw research
            if state.research_notes:
                fallback = "\n\n".join(n.summary for n in state.research_notes)
                state.final_answer = FinalAnswer(
                    content=f"[Fallback - Writer error]\n\n{fallback}",
                    citations=[],
                    word_count=len(fallback.split()),
                )

        return state
