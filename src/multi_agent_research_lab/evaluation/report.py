"""Benchmark report rendering in Markdown format."""

from multi_agent_research_lab.core.pricing import VND_PER_USD
from multi_agent_research_lab.core.schemas import BenchmarkMetrics


def render_markdown_report(metrics: list[BenchmarkMetrics], title: str = "Benchmark Report") -> str:
    """Render benchmark metrics to a markdown report.

    Includes:
    - Summary table with all 5 required metrics
    - Cost breakdown in USD and VND
    - Agent call patterns
    """
    lines = [
        f"# {title}",
        "",
        "## Setup",
        "",
        "| Setting | Value |",
        "|---------|-------|",
        f"| Runs | {len(metrics)} |",
        f"| Modes | {', '.join(set(m.run_name.rsplit('_', 1)[0] for m in metrics))} |",
        "",
        "## Results",
        "",
        "| Run | Latency (s) | Cost (USD) | Cost (VND) | Citation Coverage | Failure | Agents |",
        "|-----|------------:|----------:|-----------:|------------------:|:-------:|--------|",
    ]

    for m in metrics:
        cost_str = f"${m.estimated_cost_usd:.4f}" if m.estimated_cost_usd else "-"
        vnd_str = f"{m.estimated_cost_usd * VND_PER_USD:,.0f}₫" if m.estimated_cost_usd else "-"
        cov_str = f"{m.citation_coverage:.2f}" if m.citation_coverage is not None else "-"
        fail_str = "❌" if m.failure else "✅"
        agents = " → ".join(m.agents_called[:5]) if m.agents_called else "-"
        lines.append(
            f"| {m.run_name} | {m.latency_seconds:.2f} | {cost_str} | {vnd_str} | "
            f"{cov_str} | {fail_str} | {agents} |"
        )

    # Summary stats
    baseline_runs = [m for m in metrics if "baseline" in m.run_name]
    multi_runs = [m for m in metrics if "multi" in m.run_name]

    if baseline_runs and multi_runs:
        avg_baseline_lat = sum(m.latency_seconds for m in baseline_runs) / len(baseline_runs)
        avg_multi_lat = sum(m.latency_seconds for m in multi_runs) / len(multi_runs)
        avg_baseline_cost = sum((m.estimated_cost_usd or 0) for m in baseline_runs) / len(baseline_runs)
        avg_multi_cost = sum((m.estimated_cost_usd or 0) for m in multi_runs) / len(multi_runs)

        lines.extend([
            "",
            "## Summary Statistics",
            "",
            "| Metric | Baseline (avg) | Multi-Agent (avg) | Ratio |",
            "|--------|---------------:|------------------:|------:|",
            f"| Latency | {avg_baseline_lat:.2f}s | {avg_multi_lat:.2f}s | {avg_multi_lat/max(avg_baseline_lat, 0.001):.1f}x |",
            f"| Cost (USD) | ${avg_baseline_cost:.4f} | ${avg_multi_cost:.4f} | {avg_multi_cost/max(avg_baseline_cost, 0.000001):.1f}x |",
            f"| Cost (VND) | {avg_baseline_cost * VND_PER_USD:,.0f}₫ | {avg_multi_cost * VND_PER_USD:,.0f}₫ | |",
        ])

    lines.extend(["", "---", ""])
    return "\n".join(lines) + "\n"
