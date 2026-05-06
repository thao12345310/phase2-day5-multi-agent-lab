"""Researcher agent — augmented LLM with search tool."""

import logging
import time

from multi_agent_research_lab.agents.base import BaseAgent, load_prompt
from multi_agent_research_lab.core.schemas import AgentName, AgentResult, ResearchNote
from multi_agent_research_lab.core.state import ResearchState
from multi_agent_research_lab.observability.logging import log_agent_event
from multi_agent_research_lab.observability.tracing import trace_span
from multi_agent_research_lab.services.llm_client import LLMClient
from multi_agent_research_lab.services.search_client import SearchClient

log = logging.getLogger(__name__)


class ResearcherAgent(BaseAgent):
    """Collects sources and creates concise research notes.

    Process:
    1. Decompose query into 2-3 sub-queries
    2. Search for each sub-query
    3. Synthesize findings into structured research note
    """

    name = "researcher"

    def __init__(self) -> None:
        self._llm = LLMClient(model="gpt-4o-mini", temperature=0.2, max_tokens=1536)
        self._search = SearchClient()
        self._system_prompt = load_prompt("researcher")

    def run(self, state: ResearchState) -> ResearchState:
        """Populate state.sources and state.research_notes."""
        started = time.perf_counter()
        cost_usd = 0.0

        with trace_span("researcher", {"loop": state.research_loops}) as span:
            try:
                # Determine what to search for
                query = state.request.query

                # Check if we have gap-filling sub-queries from analyst
                sub_queries_from_gaps = None
                if state.trace:
                    for event in reversed(state.trace):
                        if event.get("name") == "sub_queries":
                            sub_queries_from_gaps = event["payload"].get("queries", [])
                            break

                if sub_queries_from_gaps:
                    search_queries = sub_queries_from_gaps[:3]
                    log.info(f"Researcher using gap queries: {search_queries}")
                else:
                    # Use LLM to decompose query into sub-queries
                    decompose_result = self._llm.complete_json(
                        "You decompose research queries into 2-3 focused search queries. "
                        "Respond with JSON: {\"sub_queries\": [\"query1\", \"query2\"]}",
                        f"Decompose this research query into 2-3 search queries "
                        f"(3-8 keywords each):\n\n{query}",
                    )
                    meta = decompose_result.pop("_llm_response", {})
                    cost_usd += meta.get("cost_usd", 0.0)
                    state.add_cost(
                        meta.get("input_tokens", 0),
                        meta.get("output_tokens", 0),
                        meta.get("cost_usd", 0.0),
                    )
                    search_queries = decompose_result.get("sub_queries", [query])

                # Search for each sub-query
                all_sources = []
                for sq in search_queries[:3]:
                    results = self._search.search(sq, max_results=3)
                    all_sources.extend(results)

                # Add new sources to state (append, not overwrite)
                state.sources.extend(all_sources)

                # Synthesize findings using LLM
                source_text = "\n\n".join(
                    f"[{i+1}] {s.title}\n{s.snippet}"
                    for i, s in enumerate(all_sources)
                )

                synth_result = self._llm.complete_json(
                    self._system_prompt,
                    f"Original query: {query}\n\n"
                    f"Search queries used: {search_queries}\n\n"
                    f"Sources found:\n{source_text}\n\n"
                    f"Synthesize these findings into a research note.",
                )
                meta = synth_result.pop("_llm_response", {})
                cost_usd += meta.get("cost_usd", 0.0)
                state.add_cost(
                    meta.get("input_tokens", 0),
                    meta.get("output_tokens", 0),
                    meta.get("cost_usd", 0.0),
                )

                # Create research note
                note = ResearchNote(
                    query_used=query,
                    sources=all_sources,
                    summary=synth_result.get("summary", "No summary generated"),
                    loop_index=state.research_loops,
                )
                state.research_notes.append(note)
                state.research_loops += 1

                # Record agent result
                state.agent_results.append(AgentResult(
                    agent=AgentName.RESEARCHER,
                    content=note.summary,
                    metadata={
                        "sources_found": len(all_sources),
                        "search_queries": search_queries,
                        "loop": state.research_loops,
                    },
                ))

                elapsed_ms = (time.perf_counter() - started) * 1000
                span["sources_found"] = len(all_sources)
                span["search_queries"] = search_queries

                state.add_trace_event("researcher", {
                    "sources_found": len(all_sources),
                    "search_queries": search_queries,
                    "summary_length": len(note.summary),
                    "duration_ms": elapsed_ms,
                    "cost_usd": cost_usd,
                })

                log_agent_event(
                    "researcher",
                    f"searched {len(all_sources)} sources, loop {state.research_loops}",
                    elapsed_ms,
                    cost_usd,
                )

            except Exception as e:
                log.error(f"Researcher failed: {e}")
                state.errors.append(f"Researcher error: {e}")

        return state
