"""Trace endpoints: /trace/{run_id}."""

from fastapi import APIRouter

router = APIRouter()

# In-memory trace storage (populated during workflow runs)
_traces: dict[str, dict] = {}


def store_trace(run_id: str, trace_data: dict) -> None:
    """Store trace data for a run (called from workflow)."""
    _traces[run_id] = trace_data


@router.get("/{run_id}")
def get_trace(run_id: str) -> dict:
    """Retrieve trace/planning log for a specific run."""
    if run_id in _traces:
        return _traces[run_id]
    return {"error": f"Trace {run_id} not found", "available": list(_traces.keys())}
