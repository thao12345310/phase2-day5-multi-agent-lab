"""Guardrail agent — pre-filter classifier for input safety."""

import logging
import time

from multi_agent_research_lab.agents.base import BaseAgent, load_prompt
from multi_agent_research_lab.core.schemas import ErrorInfo, GuardrailDecision
from multi_agent_research_lab.core.state import ResearchState
from multi_agent_research_lab.observability.logging import log_agent_event
from multi_agent_research_lab.observability.tracing import trace_span
from multi_agent_research_lab.services.llm_client import LLMClient

log = logging.getLogger(__name__)


class GuardrailAgent(BaseAgent):
    """Pre-filter classifier: safe / sensitive / out_of_scope / policy_violation.

    Uses cheapest model (gpt-4o-mini) for a single classification call.
    If the query fails the guardrail, sets state.error with a friendly message.
    """

    name = "guardrail"

    def __init__(self) -> None:
        self._llm = LLMClient(model="gpt-4o-mini", temperature=0.0, max_tokens=256)
        self._system_prompt = load_prompt("guardrail")

    def run(self, state: ResearchState) -> ResearchState:
        """Check if query is safe to process."""
        started = time.perf_counter()

        with trace_span("guardrail", {"query": state.request.query[:80]}) as span:
            try:
                result = self._llm.complete_json(
                    self._system_prompt,
                    f"Classify this query:\n\n{state.request.query}",
                )

                meta = result.pop("_llm_response", {})
                cost_usd = meta.get("cost_usd", 0.0)
                state.add_cost(
                    meta.get("input_tokens", 0),
                    meta.get("output_tokens", 0),
                    cost_usd,
                )

                decision = GuardrailDecision(
                    passed=result.get("passed", True),
                    category=result.get("category", "safe"),
                    reason=result.get("reason", ""),
                )

                state.guardrail_passed = decision.passed
                span["passed"] = decision.passed
                span["category"] = decision.category

                elapsed_ms = (time.perf_counter() - started) * 1000
                state.add_trace_event("guardrail", {
                    "passed": decision.passed,
                    "category": decision.category,
                    "reason": decision.reason,
                    "duration_ms": elapsed_ms,
                    "cost_usd": cost_usd,
                })

                if not decision.passed:
                    state.error = ErrorInfo(
                        code="guardrail_blocked",
                        message=f"Query blocked ({decision.category}): {decision.reason}",
                        agent="guardrail",
                    )
                    log_agent_event("guardrail", f"blocked ({decision.category}): {decision.reason}", elapsed_ms, cost_usd)
                else:
                    log_agent_event("guardrail", f"passed ({decision.category})", elapsed_ms, cost_usd)

            except Exception as e:
                log.error(f"Guardrail check failed: {e}")
                # Fail open — allow query through if guardrail itself errors
                state.guardrail_passed = True
                state.errors.append(f"Guardrail error: {e}")

        return state
