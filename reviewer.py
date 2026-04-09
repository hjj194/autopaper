"""
AutoPaper reviewer harness. Single-file LLM ensemble reviewer.
Usage: uv run reviewer.py [--dry-run]
DO NOT MODIFY -- this is the fixed evaluation harness.
"""

import argparse
import json
import os
import sys
import time

import litellm

litellm.suppress_debug_info = True

# ---------------------------------------------------------------------------
# Configuration -- edit these, not the code below
# ---------------------------------------------------------------------------

REVIEWERS = [
    {
        "model": "gpt-4o",
        "api_key": os.getenv("OPENAI_API_KEY", ""),
        "base_url": os.getenv("OPENAI_BASE_URL") or "https://api.openai.com/v1",
    },
    {
        "model": "anthropic/claude-sonnet-4-6",
        "api_key": os.getenv("ANTHROPIC_API_KEY", ""),
        "base_url": os.getenv("ANTHROPIC_BASE_URL") or "https://api.anthropic.com/v1",
    },
    {
        "model": "gemini/gemini-2.0-flash",
        "api_key": os.getenv("GEMINI_API_KEY", ""),
        "base_url": os.getenv("GEMINI_BASE_URL") or "https://generativelanguage.googleapis.com/v1beta/openai",
    },
]

TARGET_VENUE = "NeurIPS"
WEIGHTS = {"soundness": 0.35, "clarity": 0.30, "novelty": 0.20, "significance": 0.15}
PAPER_PATH = "paper.tex"
MAX_TOKENS = 128000
REQUEST_TIMEOUT = 120
MIN_QUORUM = 2


# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------

def compute_review_score(scores: dict) -> float:
    """Weighted average of dimension scores."""
    return sum(scores[dim] * weight for dim, weight in WEIGHTS.items())



def find_weakest_dim(scores: dict) -> str:
    """Return the dimension with the lowest score."""
    return min(WEIGHTS.keys(), key=lambda d: scores[d])



def parse_review_response(raw: str) -> dict:
    """Parse LLM JSON response, handling markdown fences robustly."""
    import re

    text = raw.strip()
    fence_match = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
    if fence_match:
        text = fence_match.group(1).strip()

    try:
        data = json.loads(text)
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON from reviewer: {e}\nRaw: {raw[:200]}") from e

    required = list(WEIGHTS.keys())
    for dim in required:
        if dim not in data:
            raise ValueError(f"Missing required field '{dim}' in reviewer response")
        score = float(data[dim])
        if not (1.0 <= score <= 10.0):
            raise ValueError(f"Score for '{dim}' out of range [1,10]: {score}")
        if score != int(score):
            raise ValueError(f"Score for '{dim}' must be an integer, got: {score}")
        data[dim] = score

    return data



def average_scores(results: list[dict]) -> dict:
    """Average scores across multiple reviewer results."""
    dims = list(WEIGHTS.keys())
    return {dim: sum(r[dim] for r in results) / len(results) for dim in dims}



def check_quorum(successes: int) -> bool:
    """Return True only if at least MIN_QUORUM reviewers succeeded."""
    return successes >= MIN_QUORUM



def truncate_paper(text: str, max_tokens: int = MAX_TOKENS) -> str:
    """
    Truncate paper if it exceeds max_tokens (approximated as words).
    Strategy: keep front 1/3 plus back 2/3.
    """
    words = text.split()
    if len(words) <= max_tokens:
        return text

    front_size = max_tokens // 3
    back_size = max_tokens - front_size
    front = words[:front_size]
    back = words[-back_size:]
    return (
        " ".join(front)
        + "\n\n[TRUNCATED] paper exceeds context limit; middle section omitted\n\n"
        + " ".join(back)
    )


# ---------------------------------------------------------------------------
# Reviewer prompt
# ---------------------------------------------------------------------------

REVIEWER_PROMPT_TEMPLATE = """You are a rigorous peer reviewer for {venue}.

Review the following LaTeX paper and score it on four dimensions using an integer scale 1-10 (whole numbers only, where 10 is best):

- **soundness**: Technical correctness, validity of experiments and methodology
- **clarity**: Writing quality, structure, and ease of understanding
- **novelty**: Originality of contributions compared to prior work
- **significance**: Importance and potential impact on the field

Score guide: 1-3 = major flaws / below bar, 4-5 = weak / borderline, 6-7 = acceptable / above average, 8-9 = strong, 10 = exceptional.

Return ONLY a JSON object in this exact format:
{{
  "soundness": <integer 1-10>,
  "clarity": <integer 1-10>,
  "novelty": <integer 1-10>,
  "significance": <integer 1-10>,
  "comments": {{
    "soundness": "<one sentence>",
    "clarity": "<one sentence>",
    "novelty": "<one sentence>",
    "significance": "<one sentence>"
  }}
}}

Example of a {venue} paper with average scores:
{{
  "soundness": 7,
  "clarity": 7,
  "novelty": 6,
  "significance": 6,
  "comments": {{
    "soundness": "Experiments are reasonable but ablations are missing.",
    "clarity": "The paper is mostly well-written with minor notation issues.",
    "novelty": "The method is an incremental improvement over baseline X.",
    "significance": "Results are competitive on standard benchmarks."
  }}
}}

--- PAPER START ---
{paper}
--- PAPER END ---

Respond with JSON only. No preamble, no explanation outside the JSON."""


# ---------------------------------------------------------------------------
# Preflight check
# ---------------------------------------------------------------------------

def preflight_check() -> None:
    """Check connectivity for all reviewers before full evaluation."""
    print("[preflight] Checking reviewer connectivity...")
    reachable = 0
    for reviewer in REVIEWERS:
        model = _resolve_model(reviewer)
        kwargs = {
            "model": model,
            "messages": [{"role": "user", "content": "Reply with the single word: ok"}],
            "max_tokens": 5,
            "temperature": 0,
            "timeout": REQUEST_TIMEOUT,
        }
        if reviewer.get("api_key"):
            kwargs["api_key"] = reviewer["api_key"]
        if reviewer.get("base_url"):
            kwargs["base_url"] = reviewer["base_url"]
        try:
            litellm.completion(**kwargs)
            print(f"[preflight] ✓ {reviewer['model']}")
            reachable += 1
        except Exception as e:
            print(f"[preflight] ✗ {reviewer['model']} -- {e}", file=sys.stderr)

    if not check_quorum(reachable):
        print(
            f"[preflight] FAIL: only {reachable}/{len(REVIEWERS)} reviewers reachable "
            f"(need {MIN_QUORUM}). Fix configuration before running.",
            file=sys.stderr,
        )
        sys.exit(1)
    print(f"[preflight] OK: {reachable}/{len(REVIEWERS)} reviewers reachable.\n")


# ---------------------------------------------------------------------------
# Core evaluation
# ---------------------------------------------------------------------------

def _resolve_model(reviewer: dict) -> str:
    """Resolve the litellm model string for this reviewer."""
    model = reviewer["model"]
    if reviewer.get("base_url") and "/" not in model:
        model = f"openai/{model}"
    return model



def call_reviewer(reviewer: dict, paper_text: str) -> tuple[dict, float] | None:
    """Call a single reviewer. Returns (parsed_scores, cost_usd) or None on failure."""
    prompt = REVIEWER_PROMPT_TEMPLATE.format(venue=TARGET_VENUE, paper=paper_text)
    kwargs = {
        "model": _resolve_model(reviewer),
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.3,
        "timeout": REQUEST_TIMEOUT,
    }
    if reviewer.get("api_key"):
        kwargs["api_key"] = reviewer["api_key"]
    if reviewer.get("base_url"):
        kwargs["base_url"] = reviewer["base_url"]

    try:
        response = litellm.completion(**kwargs)
        raw = response.choices[0].message.content
        scores = parse_review_response(raw)
        try:
            cost = litellm.completion_cost(completion_response=response)
        except Exception:
            cost = 0.0
        return scores, cost
    except Exception as e:
        print(f"[WARN] Reviewer {reviewer['model']} failed: {e}", file=sys.stderr)
        return None



def evaluate(paper_path: str = PAPER_PATH, skip_preflight: bool = False) -> dict:
    """Run all reviewers and return aggregated scores."""
    if not skip_preflight:
        preflight_check()
    with open(paper_path, "r", encoding="utf-8") as f:
        paper_text = f.read()

    paper_text = truncate_paper(paper_text)

    results = []
    total_cost = 0.0

    for reviewer in REVIEWERS:
        outcome = call_reviewer(reviewer, paper_text)
        if outcome is not None:
            scores, cost = outcome
            results.append(scores)
            total_cost += cost

    successes = len(results)
    if not check_quorum(successes):
        print(
            f"[ERROR] Only {successes}/{len(REVIEWERS)} reviewers succeeded "
            f"(minimum {MIN_QUORUM} required)",
            file=sys.stderr,
        )
        sys.exit(1)

    avg = average_scores(results)
    score = compute_review_score(avg)
    weakest = find_weakest_dim(avg)

    return {
        "review_score": score,
        "soundness": avg["soundness"],
        "clarity": avg["clarity"],
        "novelty": avg["novelty"],
        "significance": avg["significance"],
        "weakest_dim": weakest,
        "cost_usd": total_cost,
        "reviewers_ok": successes,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Only run reviewer connectivity preflight without scoring the paper.",
    )
    args = parser.parse_args()

    if args.dry_run:
        preflight_check()
        sys.exit(0)

    t0 = time.time()
    metrics = evaluate()
    duration = time.time() - t0

    print("---")
    print(f"review_score:   {metrics['review_score']:.3f}")
    print(f"soundness:      {metrics['soundness']:.1f}")
    print(f"clarity:        {metrics['clarity']:.1f}")
    print(f"novelty:        {metrics['novelty']:.1f}")
    print(f"significance:   {metrics['significance']:.1f}")
    print(f"weakest_dim:    {metrics['weakest_dim']}")
    print(f"cost_usd:       {metrics['cost_usd']:.2f}")
    print(f"duration_sec:   {duration:.0f}")
    print(f"reviewers_ok:   {metrics['reviewers_ok']}/{len(REVIEWERS)}")
    print("---")
