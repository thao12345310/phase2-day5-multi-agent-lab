"""LangGraph multi-agent workflow + baseline single-agent.

graph/workflow.py builds a StateGraph with guardrail → supervisor → workers loop.
graph/baseline.py provides a simple single-agent augmented LLM for comparison.
"""

import logging
import time
import uuid

from multi_agent_research_lab.agents import (
    AnalystAgent,
    CriticAgent,
    GuardrailAgent,
    ResearcherAgent,
    SupervisorAgent,
    WriterAgent,
)
from multi_agent_research_lab.core.config import get_settings
from multi_agent_research_lab.core.schemas import ErrorInfo
from multi_agent_research_lab.core.state import ResearchState
from multi_agent_research_lab.observability.logging import log_agent_event
from multi_agent_research_lab.observability.planning_log import save_run
from multi_agent_research_lab.observability.tracing import trace_span

log = logging.getLogger(__name__)


class MultiAgentWorkflow:
    """Builds and runs the multi-agent orchestrator-workers graph.

    Flow: guardrail → supervisor → [researcher|analyst|writer|critic] → supervisor → ...
    Workers always return to supervisor for next routing decision.
    """

    def __init__(self, enable_critic: bool = False) -> None:
        self._enable_critic = enable_critic
        self._settings = get_settings()

        # Initialize agents
        self._guardrail = GuardrailAgent()
        self._supervisor = SupervisorAgent(enable_critic=enable_critic)
        self._researcher = ResearcherAgent()
        self._analyst = AnalystAgent()
        self._writer = WriterAgent()
        self._critic = CriticAgent() if enable_critic else None

        self._agents = {
            "researcher": self._researcher,
            "analyst": self._analyst,
            "writer": self._writer,
        }
        if self._critic:
            self._agents["critic"] = self._critic

    def run(self, state: ResearchState) -> ResearchState:
        """Execute the multi-agent workflow and return final state.

        Implements the orchestrator-workers pattern:
        1. Guardrail check
        2. Supervisor routes to next worker
        3. Worker executes and returns
        4. Back to supervisor until done or max iterations
        """
        run_id = f"multi_{uuid.uuid4().hex[:8]}"
        start_time = time.perf_counter()

        with trace_span("workflow", {"query": state.request.query[:80], "run_id": run_id}) as wf_span:
            # Step 1: Guardrail
            log_agent_event("system", "Starting multi-agent workflow")

            state = self._guardrail.run(state)
            if not state.guardrail_passed:
                log.warning("Query blocked by guardrail")
                return state

            # Step 2: Supervisor loop
            max_iter = self._settings.max_iterations
            while state.iteration < max_iter:
                # Check timeout
                elapsed = time.perf_counter() - start_time
                if elapsed > self._settings.timeout_seconds:
                    state.error = ErrorInfo(
                        code="timeout",
                        message=f"Workflow timeout ({self._settings.timeout_seconds}s)",
                        agent="supervisor",
                    )
                    log.warning(f"Workflow timeout after {elapsed:.1f}s")
                    break

                # Supervisor decides next agent
                state = self._supervisor.run(state)

                # Get the last route decision
                if not state.route_history:
                    break

                next_agent = state.route_history[-1]

                if next_agent == "done":
                    log_agent_event("system", "Workflow complete — supervisor decided done")
                    break

                # Execute the worker agent
                worker = self._agents.get(next_agent)
                if worker:
                    try:
                        state = worker.run(state)
                    except Exception as e:
                        log.error(f"Worker {next_agent} raised exception: {e}")
                        state.errors.append(f"{next_agent} exception: {e}")
                        state.error = ErrorInfo(
                            code="agent_exception",
                            message=str(e),
                            agent=next_agent,
                        )
                        break
                else:
                    log.warning(f"Unknown agent: {next_agent}")
                    state.errors.append(f"Unknown agent: {next_agent}")
                    break

            # Final logging
            elapsed = time.perf_counter() - start_time
            wf_span["iterations"] = state.iteration
            wf_span["total_cost_usd"] = state.total_cost_usd
            wf_span["elapsed_seconds"] = elapsed

            state.add_trace_event("workflow_complete", {
                "total_iterations": state.iteration,
                "total_cost_usd": state.total_cost_usd,
                "elapsed_seconds": elapsed,
                "agents_called": state.route_history,
                "has_answer": state.final_answer is not None,
            })

            log_agent_event(
                "system",
                f"Workflow done: {state.iteration} iters, {len(state.route_history)} agent calls",
                elapsed * 1000,
                state.total_cost_usd,
            )

        # Persist run artifacts to disk
        try:
            save_run(run_id, state)
        except Exception as e:
            log.warning(f"Failed to persist run artifacts: {e}")

        return state
