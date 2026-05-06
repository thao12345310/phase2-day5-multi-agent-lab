"""Token pricing for cost estimation.

Prices in USD per 1M tokens, sourced from provider pricing pages (May 2025).
"""

from dataclasses import dataclass

# USD per 1M tokens
PRICING: dict[str, dict[str, float]] = {
    "gpt-4o-mini": {"input": 0.15, "output": 0.60},
    "gpt-4o": {"input": 2.50, "output": 10.00},
    "gpt-4.1-mini": {"input": 0.40, "output": 1.60},
    "gpt-4.1-nano": {"input": 0.10, "output": 0.40},
    "claude-haiku-4-5": {"input": 0.80, "output": 4.00},
    "claude-sonnet-4-6": {"input": 3.00, "output": 15.00},
}

VND_PER_USD = 25_000


@dataclass(frozen=True)
class CostBreakdown:
    input_tokens: int
    output_tokens: int
    input_cost_usd: float
    output_cost_usd: float
    total_cost_usd: float
    total_cost_vnd: float
    model: str


def calculate_cost(model: str, input_tokens: int, output_tokens: int) -> CostBreakdown:
    """Calculate cost in USD and VND for a given model and token counts."""
    prices = PRICING.get(model, {"input": 0.15, "output": 0.60})  # default to cheapest
    input_cost = (input_tokens / 1_000_000) * prices["input"]
    output_cost = (output_tokens / 1_000_000) * prices["output"]
    total = input_cost + output_cost
    return CostBreakdown(
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        input_cost_usd=input_cost,
        output_cost_usd=output_cost,
        total_cost_usd=total,
        total_cost_vnd=total * VND_PER_USD,
        model=model,
    )
