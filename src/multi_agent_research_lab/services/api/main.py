"""FastAPI application for the Multi-Agent Research Lab."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from multi_agent_research_lab.services.api.routers import agents, benchmarks, traces

app = FastAPI(
    title="Multi-Agent Research Lab",
    description="API for running and benchmarking single-agent vs multi-agent research workflows",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(agents.router, prefix="/run", tags=["agents"])
app.include_router(benchmarks.router, prefix="/benchmark", tags=["benchmarks"])
app.include_router(traces.router, prefix="/trace", tags=["traces"])


@app.get("/")
def root():
    return {"docs": "/docs", "version": app.version, "title": app.title}


@app.get("/health")
def health():
    return {"status": "ok"}
