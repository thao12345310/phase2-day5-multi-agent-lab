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


@app.command()
def evaluate(
    queries: str = typer.Option(
        "",
        "--queries", "-q",
        help="Comma-separated queries (empty = use config file)",
    ),
    skip_critic: bool = typer.Option(False, "--skip-critic", help="Skip multi-agent+critic mode"),
    skip_judge: bool = typer.Option(False, "--skip-judge", help="Skip LLM-as-Judge scoring"),
    output_dir: str = typer.Option("reports", help="Directory for output reports"),
) -> None:
    """Run FULL evaluation: baseline → multi-agent → critic → judge → report.

    This is the single command to run the entire evaluation pipeline.
    Produces:
    - Console output with live progress
    - reports/evaluation_report.md with full comparison
    - reports/evaluation_results.json with raw data
    """
    import json
    import time
    from pathlib import Path

    import yaml

    _init()

    console.print(Panel.fit(
        "🔬 Full Evaluation Pipeline\n"
        "baseline → multi-agent → multi-agent+critic → judge → report",
        style="bold magenta",
    ))

    # --- Step 1: Load queries ---
    if queries:
        query_list = [q.strip() for q in queries.split(",") if q.strip()]
    else:
        config_path = "configs/lab_default.yaml"
        try:
            with open(config_path) as f:
                config = yaml.safe_load(f)
            query_list = config.get("benchmark", {}).get("queries", [])
        except FileNotFoundError:
            query_list = [
                "What is GraphRAG and how does it differ from traditional RAG?",
                "Compare single-agent and multi-agent workflows for research tasks",
            ]

    modes = ["baseline", "multi-agent"]
    if not skip_critic:
        modes.append("multi-agent+critic")

    console.print(f"[dim]Queries: {len(query_list)} | Modes: {', '.join(modes)}[/]")
    console.print(f"[dim]Total runs: {len(query_list) * len(modes)}[/]\n")

    # --- Step 2: Run all modes ---
    all_results: list[dict] = []
    run_counter = 0
    total_runs = len(query_list) * len(modes)

    for qi, query in enumerate(query_list, 1):
        console.print(f"\n[bold cyan]━━━ Query {qi}/{len(query_list)} ━━━[/]")
        console.print(f"[bold]{query}[/]\n")

        for mode in modes:
            run_counter += 1
            console.print(f"  [{run_counter}/{total_runs}] Running [cyan]{mode}[/]...", end=" ")

            start = time.perf_counter()
            state = ResearchState(request=ResearchQuery(query=query))

            try:
                if mode == "baseline":
                    agent = BaselineAgent()
                    state = agent.run(state)
                elif mode == "multi-agent":
                    workflow = MultiAgentWorkflow(enable_critic=False)
                    state = workflow.run(state)
                else:  # multi-agent+critic
                    workflow = MultiAgentWorkflow(enable_critic=True)
                    state = workflow.run(state)

                elapsed = time.perf_counter() - start
                answer_text = state.final_answer.content if state.final_answer else ""
                word_count = state.final_answer.word_count if state.final_answer else 0
                citations = state.final_answer.citations if state.final_answer else []

                result = {
                    "query": query,
                    "mode": mode,
                    "latency_s": round(elapsed, 2),
                    "cost_usd": round(state.total_cost_usd, 6),
                    "word_count": word_count,
                    "citation_count": len(citations),
                    "citations": citations,
                    "iterations": state.iteration,
                    "agents_called": state.route_history,
                    "input_tokens": state.total_input_tokens,
                    "output_tokens": state.total_output_tokens,
                    "answer_preview": answer_text[:300],
                    "answer_full": answer_text,
                    "error": None,
                    "failure": False,
                }

                # Include critic scores if available
                if state.critic_feedback:
                    latest_critic = state.critic_feedback[-1]
                    result["critic_score"] = latest_critic.overall_score
                    result["critic_factual"] = latest_critic.factual_score
                    result["critic_coherence"] = latest_critic.coherence_score
                    result["critic_completeness"] = latest_critic.completeness_score
                    result["critic_citation"] = latest_critic.citation_score

                console.print(
                    f"[green]✓[/] ⏱ {elapsed:.1f}s | 💰 ${state.total_cost_usd:.4f} | "
                    f"📝 {word_count}w | 🔗 {len(citations)} cites"
                )

            except Exception as e:
                elapsed = time.perf_counter() - start
                result = {
                    "query": query,
                    "mode": mode,
                    "latency_s": round(elapsed, 2),
                    "cost_usd": 0,
                    "word_count": 0,
                    "citation_count": 0,
                    "error": str(e),
                    "failure": True,
                }
                console.print(f"[red]✗ Error: {e}[/]")

            all_results.append(result)

    # --- Step 3: LLM-as-Judge scoring (Claude) ---
    if not skip_judge:
        console.print(f"\n[bold magenta]━━━ LLM-as-Judge Scoring (Claude) ━━━[/]\n")

        from multi_agent_research_lab.evaluation.judge import judge_answer, judge_comparison

        successful = [r for r in all_results if not r.get("failure")]

        for r in successful:
            console.print(f"  Judging [{r['mode']}] {r['query'][:50]}...", end=" ")
            try:
                verdict = judge_answer(r["query"], r.get("answer_full", ""))
                r["judge_accuracy"] = verdict.accuracy
                r["judge_completeness"] = verdict.completeness
                r["judge_coherence"] = verdict.coherence
                r["judge_citation_quality"] = verdict.citation_quality
                r["judge_avg"] = round(verdict.average, 2)
                r["judge_reasoning"] = verdict.reasoning
                console.print(
                    f"[green]✓[/] avg={verdict.average:.1f}/5 "
                    f"(acc={verdict.accuracy} comp={verdict.completeness} "
                    f"coh={verdict.coherence} cit={verdict.citation_quality})"
                )
            except Exception as e:
                console.print(f"[yellow]⚠ Judge error: {e}[/]")

        # Pairwise comparisons: baseline vs multi-agent for same query
        console.print(f"\n[bold magenta]━━━ Pairwise Comparisons ━━━[/]\n")
        comparisons = []

        for query in query_list:
            baseline_r = next((r for r in successful if r["query"] == query and r["mode"] == "baseline"), None)
            multi_r = next((r for r in successful if r["query"] == query and r["mode"] == "multi-agent"), None)

            if baseline_r and multi_r:
                console.print(f"  Comparing: {query[:60]}...", end=" ")
                try:
                    cmp = judge_comparison(
                        query,
                        baseline_r.get("answer_full", ""),
                        multi_r.get("answer_full", ""),
                    )
                    cmp["query"] = query[:50]
                    comparisons.append(cmp)
                    winner = cmp.get("winner", "tie")
                    console.print(f"[green]✓[/] Winner: [bold]{winner}[/] (A=baseline, B=multi-agent)")
                except Exception as e:
                    console.print(f"[yellow]⚠ {e}[/]")

    # --- Step 4: Generate report ---
    console.print(f"\n[bold yellow]━━━ Generating Report ━━━[/]\n")

    out_path = Path(output_dir)
    out_path.mkdir(exist_ok=True)

    # 4a: Save raw JSON results
    json_path = out_path / "evaluation_results.json"
    # Remove full answer text from JSON to keep it manageable
    json_results = []
    for r in all_results:
        r_copy = {k: v for k, v in r.items() if k != "answer_full"}
        json_results.append(r_copy)
    with open(json_path, "w") as f:
        json.dump({
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "results": json_results,
            "comparisons": comparisons if not skip_judge else [],
        }, f, indent=2, default=str)
    console.print(f"  📄 Raw data: [link={json_path}]{json_path}[/]")

    # 4b: Generate markdown report
    md_lines = [
        "# 🔬 Full Evaluation Report",
        "",
        f"**Generated**: {time.strftime('%Y-%m-%d %H:%M:%S')}  ",
        f"**Queries**: {len(query_list)} | **Modes**: {', '.join(modes)}  ",
        f"**Total runs**: {len(all_results)}",
        "",
        "## 📊 Results Summary",
        "",
        "| Query | Mode | Latency | Cost (USD) | Words | Citations | Judge Avg |",
        "|-------|------|--------:|-----------:|------:|----------:|----------:|",
    ]

    for r in all_results:
        q_short = r["query"][:40] + "..." if len(r["query"]) > 40 else r["query"]
        if r.get("failure"):
            md_lines.append(f"| {q_short} | {r['mode']} | ERROR | - | - | - | - |")
        else:
            judge_str = f"{r.get('judge_avg', '-')}" if "judge_avg" in r else "-"
            md_lines.append(
                f"| {q_short} | {r['mode']} | {r['latency_s']:.1f}s | "
                f"${r['cost_usd']:.4f} | {r['word_count']} | "
                f"{r['citation_count']} | {judge_str} |"
            )

    # Averages per mode
    md_lines.extend(["", "## 📈 Mode Averages", ""])
    md_lines.append("| Mode | Avg Latency | Avg Cost | Avg Words | Avg Judge |")
    md_lines.append("|------|------------:|---------:|----------:|----------:|")

    for mode in modes:
        mode_results = [r for r in all_results if r["mode"] == mode and not r.get("failure")]
        if mode_results:
            avg_lat = sum(r["latency_s"] for r in mode_results) / len(mode_results)
            avg_cost = sum(r["cost_usd"] for r in mode_results) / len(mode_results)
            avg_words = sum(r["word_count"] for r in mode_results) / len(mode_results)
            judge_scores = [r["judge_avg"] for r in mode_results if "judge_avg" in r]
            avg_judge = sum(judge_scores) / len(judge_scores) if judge_scores else 0
            md_lines.append(
                f"| {mode} | {avg_lat:.1f}s | ${avg_cost:.4f} | {avg_words:.0f} | "
                f"{avg_judge:.2f}/5 |"
            )

    # Pairwise comparison summary
    if not skip_judge and comparisons:
        md_lines.extend(["", "## 🏆 Pairwise Comparisons (A=baseline, B=multi-agent)", ""])
        md_lines.append("| Query | Winner | Score A | Score B | Reasoning |")
        md_lines.append("|-------|--------|--------:|--------:|-----------|")
        for c in comparisons:
            md_lines.append(
                f"| {c.get('query', '')} | **{c.get('winner', 'tie')}** | "
                f"{c.get('score_a', '-')} | {c.get('score_b', '-')} | "
                f"{c.get('reasoning', '')[:80]}... |"
            )

    # Provider breakdown
    md_lines.extend([
        "",
        "## 🤖 Provider Architecture",
        "",
        "| Agent | Model | Provider |",
        "|-------|-------|----------|",
        "| Guardrail | gpt-4o-mini | OpenAI |",
        "| Supervisor | gpt-4o-mini | OpenAI |",
        "| Researcher | gpt-4o-mini | OpenAI |",
        "| Analyst | gpt-4o-mini | OpenAI |",
        "| **Writer** | **claude-haiku-4-5** | **Anthropic** |",
        "| **Critic** | **claude-haiku-4-5** | **Anthropic** |",
        "| **Judge** | **claude-haiku-4-5** | **Anthropic** |",
        "",
        "---",
        "",
    ])

    md_report = "\n".join(md_lines)
    md_path = out_path / "evaluation_report.md"
    with open(md_path, "w") as f:
        f.write(md_report)
    console.print(f"  📋 Report: [link={md_path}]{md_path}[/]")

    # --- Step 5: Final summary table in console ---
    console.print("\n")
    summary_table = Table(title="🔬 Evaluation Complete", show_header=True, style="bold")
    summary_table.add_column("Mode", style="cyan", width=20)
    summary_table.add_column("Avg Latency", justify="right", style="yellow")
    summary_table.add_column("Avg Cost", justify="right", style="green")
    summary_table.add_column("Avg Words", justify="right", style="blue")
    summary_table.add_column("Avg Judge", justify="right", style="magenta")
    summary_table.add_column("Failures", justify="right", style="red")

    for mode in modes:
        mode_results = [r for r in all_results if r["mode"] == mode]
        successes = [r for r in mode_results if not r.get("failure")]
        if successes:
            avg_lat = sum(r["latency_s"] for r in successes) / len(successes)
            avg_cost = sum(r["cost_usd"] for r in successes) / len(successes)
            avg_words = sum(r["word_count"] for r in successes) / len(successes)
            judge_scores = [r["judge_avg"] for r in successes if "judge_avg" in r]
            avg_judge = sum(judge_scores) / len(judge_scores) if judge_scores else 0
            failures = len(mode_results) - len(successes)
            summary_table.add_row(
                mode,
                f"{avg_lat:.1f}s",
                f"${avg_cost:.4f}",
                f"{avg_words:.0f}",
                f"{avg_judge:.1f}/5" if avg_judge else "-",
                str(failures),
            )

    console.print(summary_table)
    console.print(f"\n[bold green]✅ Reports saved to {output_dir}/[/]")


if __name__ == "__main__":
    app()

