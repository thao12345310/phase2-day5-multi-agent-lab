"""Command-line entrypoint for the Multi-Agent Research Lab.

Provides CLI commands for:
- serve: Start FastAPI server
- routes: Show all API routes
- baseline: Run single-agent baseline
- multi-agent: Run multi-agent workflow
- benchmark: Run benchmark comparison
"""

from typing import Annotated

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from multi_agent_research_lab.core.config import get_settings
from multi_agent_research_lab.core.schemas import ResearchQuery
from multi_agent_research_lab.core.state import ResearchState
from multi_agent_research_lab.graph.baseline import BaselineAgent
from multi_agent_research_lab.graph.workflow import MultiAgentWorkflow
from multi_agent_research_lab.observability.logging import configure_logging

app = typer.Typer(help="Multi-Agent Research Lab CLI", no_args_is_help=True)
console = Console()


def _init() -> None:
    settings = get_settings()
    configure_logging(settings.log_level)


@app.command()
def serve(
    host: str = "0.0.0.0",
    port: int = 8000,
) -> None:
    """Start the FastAPI server."""
    _init()
    try:
        import uvicorn
        console.print(f"[bold green]Starting server at http://{host}:{port}[/]")
        console.print("[dim]Press Ctrl+C to stop[/]")
        uvicorn.run(
            "multi_agent_research_lab.services.api.main:app",
            host=host,
            port=port,
            reload=True,
        )
    except ImportError:
        console.print("[red]uvicorn not installed. Run: pip install uvicorn[/]")
        raise typer.Exit(code=1)


@app.command()
def routes() -> None:
    """Show all API routes — required by instructor."""
    from multi_agent_research_lab.services.api.main import app as fastapi_app

    table = Table(title="API Routes", show_header=True)
    table.add_column("Method", style="cyan", width=10)
    table.add_column("Path", style="green", width=40)
    table.add_column("Name", style="yellow")

    for route in fastapi_app.routes:
        if hasattr(route, "methods"):
            methods = ",".join(route.methods)
            table.add_row(methods, route.path, route.name)

    console.print(table)


@app.command()
def baseline(
    query: Annotated[str, typer.Option("--query", "-q", help="Research query")],
) -> None:
    """Run a minimal single-agent baseline."""
    import time

    _init()
    console.print(Panel.fit(f"🤖 Baseline: {query}", style="bold white"))

    start = time.perf_counter()
    request = ResearchQuery(query=query)
    state = ResearchState(request=request)
    agent = BaselineAgent()
    state = agent.run(state)
    elapsed = time.perf_counter() - start

    if state.final_answer:
        console.print(Panel(
            state.final_answer.content,
            title="Single-Agent Baseline",
            subtitle=f"⏱ {elapsed:.1f}s | 💰 ${state.total_cost_usd:.4f} | "
                     f"📝 {state.final_answer.word_count} words",
            style="white",
        ))
    else:
        console.print("[red]No answer generated[/]")

    if state.errors:
        for e in state.errors:
            console.print(f"[yellow]⚠ {e}[/]")


@app.command("multi-agent")
def multi_agent(
    query: Annotated[str, typer.Option("--query", "-q", help="Research query")],
    critic: bool = typer.Option(False, "--critic", help="Enable critic agent"),
) -> None:
    """Run the multi-agent workflow."""
    import time

    _init()
    mode = "multi-agent + critic" if critic else "multi-agent"
    console.print(Panel.fit(f"🧭 {mode}: {query}", style="bold cyan"))

    start = time.perf_counter()
    state = ResearchState(request=ResearchQuery(query=query))
    workflow = MultiAgentWorkflow(enable_critic=critic)
    state = workflow.run(state)
    elapsed = time.perf_counter() - start

    if state.final_answer:
        console.print(Panel(
            state.final_answer.content,
            title=f"Multi-Agent Result",
            subtitle=f"⏱ {elapsed:.1f}s | 💰 ${state.total_cost_usd:.4f} | "
                     f"📝 {state.final_answer.word_count} words | "
                     f"🔄 {state.iteration} iterations",
            style="cyan",
        ))

        if state.final_answer.citations:
            console.print("\n[bold]Citations:[/]")
            for c in state.final_answer.citations:
                console.print(f"  📎 {c}")
    else:
        console.print("[red]No answer generated[/]")

    # Show planning log
    if state.planning_log:
        table = Table(title="Planning Log", show_header=True)
        table.add_column("Iter", style="dim", width=5)
        table.add_column("Agent", style="cyan", width=15)
        table.add_column("Reason", style="white")
        for step in state.planning_log:
            table.add_row(str(step.iteration), step.agent, step.reason)
        console.print(table)

    if state.errors:
        for e in state.errors:
            console.print(f"[yellow]⚠ {e}[/]")


@app.command()
def benchmark(
    suite: str = typer.Option("default", help="Benchmark suite name"),
) -> None:
    """Run benchmark comparing baseline vs multi-agent."""
    import time

    import yaml

    _init()
    console.print(Panel.fit("📊 Running Benchmark", style="bold yellow"))

    # Load queries from config
    config_path = "configs/lab_default.yaml"
    try:
        with open(config_path) as f:
            config = yaml.safe_load(f)
        queries = config.get("benchmark", {}).get("queries", [])
    except FileNotFoundError:
        queries = ["Research GraphRAG state-of-the-art and write a 500-word summary"]

    results = []
    modes = ["baseline", "multi-agent"]

    for query in queries:
        console.print(f"\n[bold]Query:[/] {query[:80]}...")
        for mode in modes:
            start = time.perf_counter()
            state = ResearchState(request=ResearchQuery(query=query))

            try:
                if mode == "baseline":
                    agent = BaselineAgent()
                    state = agent.run(state)
                else:
                    workflow = MultiAgentWorkflow()
                    state = workflow.run(state)

                elapsed = time.perf_counter() - start
                results.append({
                    "query": query[:50],
                    "mode": mode,
                    "latency": elapsed,
                    "cost": state.total_cost_usd,
                    "words": state.final_answer.word_count if state.final_answer else 0,
                    "citations": len(state.final_answer.citations) if state.final_answer else 0,
                    "error": bool(state.error),
                })
                console.print(
                    f"  [{mode}] ⏱ {elapsed:.1f}s | 💰 ${state.total_cost_usd:.4f} | "
                    f"📝 {state.final_answer.word_count if state.final_answer else 0} words"
                )
            except Exception as e:
                console.print(f"  [{mode}] [red]Error: {e}[/]")
                results.append({"query": query[:50], "mode": mode, "error": True})

    # Summary table
    console.print("\n")
    table = Table(title="Benchmark Summary", show_header=True)
    table.add_column("Query", style="white", width=30)
    table.add_column("Mode", style="cyan", width=15)
    table.add_column("Latency", style="yellow", justify="right")
    table.add_column("Cost", style="green", justify="right")
    table.add_column("Words", style="blue", justify="right")
    table.add_column("Citations", justify="right")

    for r in results:
        if "latency" in r:
            table.add_row(
                r["query"],
                r["mode"],
                f"{r['latency']:.1f}s",
                f"${r['cost']:.4f}",
                str(r["words"]),
                str(r["citations"]),
            )
        else:
            table.add_row(r["query"], r["mode"], "ERROR", "-", "-", "-")

    console.print(table)


if __name__ == "__main__":
    app()
