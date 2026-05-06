"""Baseline single-agent (augmented LLM) for comparison.

Uses the same search client as multi-agent for fair benchmarking.
One LLM call with search context → direct answer.
"""

import logging
import time

from multi_agent_research_lab.core.schemas import FinalAnswer
from multi_agent_research_lab.core.state import ResearchState
from multi_agent_research_lab.services.llm_client import LLMClient
from multi_agent_research_lab.services.search_client import SearchClient

log = logging.getLogger(__name__)


class BaselineAgent:
    """Single-agent augmented LLM — one search + one generation call.

    Fair comparison: same search client, same base model as multi-agent workers.
    """

    def __init__(self) -> None:
        self._llm = LLMClient(model="gpt-4o-mini", temperature=0.3, max_tokens=2048)
        self._search = SearchClient()

    def run(self, state: ResearchState) -> ResearchState:
        """Execute single-agent baseline: search + generate."""
        start = time.perf_counter()

        try:
            # Step 1: Search
            sources = self._search.search(state.request.query, max_results=5)
            state.sources.extend(sources)

            source_text = "\n\n".join(
                f"[{i+1}] {s.title}\n{s.snippet}"
                for i, s in enumerate(sources)
            )

            # Step 2: Generate answer in one call
            system_prompt = (
                "You are a research assistant. Based on the provided sources, "
                "write a comprehensive, well-structured answer to the user's query. "
                "Include citations to sources using [Source: title] format. "
                "Be thorough but concise. Target the audience level specified."
            )

            user_prompt = (
                f"Query: {state.request.query}\n"
                f"Audience: {state.request.audience}\n\n"
                f"Sources:\n{source_text}\n\n"
                f"Write a comprehensive answer with citations."
            )

            response = self._llm.complete(system_prompt, user_prompt)

            state.add_cost(response.input_tokens, response.output_tokens, response.cost_usd)

            content = response.content
            word_count = len(content.split())

            # Extract citation references
            citations = []
            for s in sources:
                if s.title.lower() in content.lower() or (s.url and s.url in content):
                    citations.append(f"{s.title} ({s.url or 'no url'})")

            state.final_answer = FinalAnswer(
                content=content,
                citations=citations,
                word_count=word_count,
            )

            state.record_route("baseline")
            state.add_trace_event("baseline", {
                "sources_found": len(sources),
                "word_count": word_count,
                "citations": len(citations),
                "latency_ms": (time.perf_counter() - start) * 1000,
            })

            log.info(f"Baseline: {word_count} words, {len(citations)} citations")

        except Exception as e:
            log.error(f"Baseline failed: {e}")
            state.errors.append(f"Baseline error: {e}")
            state.final_answer = FinalAnswer(
                content=f"Error: {e}",
                citations=[],
                word_count=0,
            )

        return state
