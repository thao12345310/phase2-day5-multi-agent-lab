"""Planning log persistence for transparency.

Saves planning_log and events to JSONL files for each run.
"""

import json
import logging
from pathlib import Path

from multi_agent_research_lab.core.state import ResearchState

log = logging.getLogger(__name__)

RUNS_DIR = Path("runs")


def save_run(run_id: str, state: ResearchState) -> Path:
    """Persist run artifacts to runs/<run_id>/."""
    run_dir = RUNS_DIR / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    # Save events.jsonl
    events_path = run_dir / "events.jsonl"
    with open(events_path, "w", encoding="utf-8") as f:
        for event in state.trace:
            f.write(json.dumps(event, ensure_ascii=False) + "\n")

    # Save planning.jsonl
    planning_path = run_dir / "planning.jsonl"
    with open(planning_path, "w", encoding="utf-8") as f:
        for step in state.planning_log:
            f.write(step.model_dump_json() + "\n")

    # Save state summary
    summary_path = run_dir / "summary.json"
    summary = {
        "query": state.request.query,
        "iterations": state.iteration,
        "total_cost_usd": state.total_cost_usd,
        "total_input_tokens": state.total_input_tokens,
        "total_output_tokens": state.total_output_tokens,
        "has_answer": state.final_answer is not None,
        "word_count": state.final_answer.word_count if state.final_answer else 0,
        "citations": len(state.final_answer.citations) if state.final_answer else 0,
        "route_history": state.route_history,
        "errors": state.errors,
    }
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)

    log.info(f"Run artifacts saved to {run_dir}")
    return run_dir
