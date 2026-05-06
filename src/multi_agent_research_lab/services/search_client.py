"""Search client abstraction with 3-tier fallback chain.

Fallback strategy (per lab_plan.md):
1. Tavily API (if TAVILY_API_KEY set)
2. Mock data keyword match from graphrag_corpus.json
3. Direct LLM knowledge (marks uncertain with [unverified])
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from multi_agent_research_lab.core.config import get_settings
from multi_agent_research_lab.core.schemas import SourceDocument

log = logging.getLogger(__name__)

MOCK_DATA_PATH = Path(__file__).parent / "mock_data" / "graphrag_corpus.json"


class SearchClient:
    """Provider-agnostic search client with 3-tier fallback."""

    def __init__(self) -> None:
        settings = get_settings()
        self._tavily_key = settings.tavily_api_key
        self._mock_corpus: list[dict] | None = None

    def _load_mock_corpus(self) -> list[dict]:
        """Lazy-load mock corpus from JSON file."""
        if self._mock_corpus is None:
            if MOCK_DATA_PATH.exists():
                with open(MOCK_DATA_PATH, encoding="utf-8") as f:
                    self._mock_corpus = json.load(f)
                log.info(f"Loaded {len(self._mock_corpus)} mock documents")
            else:
                log.warning(f"Mock data not found at {MOCK_DATA_PATH}")
                self._mock_corpus = []
        return self._mock_corpus

    def _search_tavily(self, query: str, max_results: int) -> list[SourceDocument] | None:
        """Tier 1: Search via Tavily API."""
        if not self._tavily_key:
            return None

        try:
            from tavily import TavilyClient  # type: ignore[import-untyped]

            client = TavilyClient(api_key=self._tavily_key)
            response = client.search(query=query, max_results=max_results)
            results = []
            for r in response.get("results", []):
                results.append(
                    SourceDocument(
                        title=r.get("title", ""),
                        url=r.get("url"),
                        snippet=r.get("content", "")[:500],
                        published_date=r.get("published_date"),
                    )
                )
            log.info(f"Tavily search returned {len(results)} results for: {query[:60]}")
            return results
        except Exception as e:
            log.warning(f"Tavily search failed: {e}")
            return None

    def _search_mock(self, query: str, max_results: int) -> list[SourceDocument]:
        """Tier 2: Keyword match against local mock corpus."""
        corpus = self._load_mock_corpus()
        query_lower = query.lower()
        keywords = [w for w in query_lower.split() if len(w) > 3]

        scored: list[tuple[float, dict]] = []
        for doc in corpus:
            text = (doc.get("title", "") + " " + doc.get("snippet", "")).lower()
            score = sum(1 for kw in keywords if kw in text)
            if score > 0:
                scored.append((score, doc))

        scored.sort(key=lambda x: x[0], reverse=True)
        results = []
        for _, doc in scored[:max_results]:
            results.append(
                SourceDocument(
                    title=doc.get("title", ""),
                    url=doc.get("url"),
                    snippet=doc.get("snippet", ""),
                    published_date=doc.get("published_date"),
                )
            )
        log.info(f"Mock search returned {len(results)} results for: {query[:60]}")
        return results

    def _search_llm_fallback(self, query: str, max_results: int) -> list[SourceDocument]:
        """Tier 3: Use LLM's training knowledge as last resort."""
        from multi_agent_research_lab.services.llm_client import LLMClient

        llm = LLMClient(temperature=0.2, max_tokens=1024)
        system_prompt = (
            "You are a research assistant. Answer based on your training knowledge. "
            "Mark any uncertain claims with [unverified]. Provide structured information "
            "as if you found it from research sources."
        )
        user_prompt = (
            f"Research the following topic and provide {max_results} key findings. "
            f"For each finding, provide a title and a 2-3 sentence summary.\n\n"
            f"Topic: {query}\n\n"
            f"Respond in JSON format:\n"
            f'{{"findings": [{{"title": "...", "snippet": "..."}}]}}'
        )

        response = llm.complete_json(system_prompt, user_prompt)
        results = []
        for f in response.get("findings", []):
            results.append(
                SourceDocument(
                    title=f.get("title", "LLM Knowledge"),
                    url=None,
                    snippet=f.get("snippet", "") + " [unverified - from LLM knowledge]",
                    metadata={"source": "llm_fallback"},
                )
            )
        log.info(f"LLM fallback returned {len(results)} results for: {query[:60]}")
        return results

    def search(self, query: str, max_results: int = 5) -> list[SourceDocument]:
        """Search with 3-tier fallback chain: Tavily → Mock → LLM.

        Args:
            query: Search query string (3-8 keywords recommended)
            max_results: Maximum number of results to return

        Returns:
            List of SourceDocument with title, url, snippet
        """
        # Tier 1: Tavily
        tavily_results = self._search_tavily(query, max_results)
        if tavily_results:
            return tavily_results

        # Tier 2: Mock data
        mock_results = self._search_mock(query, max_results)
        if mock_results:
            return mock_results

        # Tier 3: LLM fallback
        log.warning("Falling back to LLM knowledge for search")
        return self._search_llm_fallback(query, max_results)
