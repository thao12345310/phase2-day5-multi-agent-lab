"""LLM-as-Judge for automated quality evaluation (bonus).

Uses a stronger model for pairwise comparison and rubric scoring.
Not a replacement for peer review, but useful for scaling evaluation.
"""

import logging

from multi_agent_research_lab.services.llm_client import LLMClient

log = logging.getLogger(__name__)


class JudgeResult:
    """Result from an LLM judge evaluation."""

    def __init__(
        self,
        accuracy: int,
        completeness: int,
        coherence: int,
        citation_quality: int,
        reasoning: str,
    ):
        self.accuracy = accuracy
        self.completeness = completeness
        self.coherence = coherence
        self.citation_quality = citation_quality
        self.reasoning = reasoning
        self.total = accuracy + completeness + coherence + citation_quality
        self.average = self.total / 4


def judge_answer(query: str, answer: str, model: str = "claude-haiku-4-5") -> JudgeResult:
    """Evaluate a single answer using LLM-as-judge.

    Scores on 4 axes (1-5 each):
    - accuracy: factual correctness
    - completeness: coverage of the topic
    - coherence: logical structure and clarity
    - citation_quality: proper source attribution
    """
    llm = LLMClient(model=model, temperature=0.0, max_tokens=512)

    system_prompt = (
        "You are an expert research quality evaluator. Score the answer on 4 axes "
        "(1-5 each). Be strict but fair. Respond in JSON only.\n\n"
        "Axes:\n"
        "- accuracy (1-5): Are facts correct and well-supported?\n"
        "- completeness (1-5): Does it fully address the query?\n"
        "- coherence (1-5): Is it well-structured and logical?\n"
        "- citation_quality (1-5): Are sources properly cited?\n\n"
        'Format: {"accuracy": N, "completeness": N, "coherence": N, '
        '"citation_quality": N, "reasoning": "..."}'
    )

    user_prompt = f"Query: {query}\n\nAnswer to evaluate:\n{answer}"

    try:
        result = llm.complete_json(system_prompt, user_prompt)
        return JudgeResult(
            accuracy=min(5, max(1, result.get("accuracy", 3))),
            completeness=min(5, max(1, result.get("completeness", 3))),
            coherence=min(5, max(1, result.get("coherence", 3))),
            citation_quality=min(5, max(1, result.get("citation_quality", 3))),
            reasoning=result.get("reasoning", ""),
        )
    except Exception as e:
        log.error(f"Judge evaluation failed: {e}")
        return JudgeResult(
            accuracy=3, completeness=3, coherence=3,
            citation_quality=3, reasoning=f"Evaluation failed: {e}",
        )


def judge_comparison(
    query: str, answer_a: str, answer_b: str, model: str = "claude-haiku-4-5"
) -> dict:
    """Pairwise comparison between two answers.

    Returns which answer is better and by how much.
    """
    llm = LLMClient(model=model, temperature=0.0, max_tokens=512)

    system_prompt = (
        "You are comparing two research answers for quality. Evaluate which is better "
        "and explain why. Respond in JSON only.\n\n"
        'Format: {"winner": "A" or "B" or "tie", "score_a": 1-10, "score_b": 1-10, '
        '"reasoning": "..."}'
    )

    user_prompt = (
        f"Query: {query}\n\n"
        f"Answer A:\n{answer_a[:2000]}\n\n"
        f"Answer B:\n{answer_b[:2000]}"
    )

    try:
        result = llm.complete_json(system_prompt, user_prompt)
        result.pop("_llm_response", None)
        return result
    except Exception as e:
        log.error(f"Judge comparison failed: {e}")
        return {"winner": "tie", "reasoning": f"Comparison failed: {e}"}
