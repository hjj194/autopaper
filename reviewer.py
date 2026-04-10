"""
AutoPaper reviewer harness. Single-file LLM ensemble reviewer.
Usage: uv run reviewer.py [--dry-run]
DO NOT MODIFY -- this is the fixed evaluation harness.
"""

import argparse
import asyncio
import json
import os
import sys
import time

try:
    import tomllib
except ModuleNotFoundError:
    import tomli as tomllib

import litellm

litellm.suppress_debug_info = True

# ---------------------------------------------------------------------------
# Configuration -- edit autopaper.toml, not this file
# ---------------------------------------------------------------------------

CONFIG_PATH = "autopaper.toml"

_ENV_KEY_MAP = {
    "gpt": "OPENAI_API_KEY",
    "openai": "OPENAI_API_KEY",
    "anthropic": "ANTHROPIC_API_KEY",
    "claude": "ANTHROPIC_API_KEY",
    "gemini": "GEMINI_API_KEY",
}

_DEFAULT_MODELS = [
    {
        "model": "gpt-5.4",
        "api_key": "",
        "base_url": "https://api.openai.com/v1",
    },
    {
        "model": "anthropic/claude-sonnet-4-6",
        "api_key": "",
        "base_url": "https://api.anthropic.com/v1",
    },
    {
        "model": "gemini/gemini-2.0-flash",
        "api_key": "",
        "base_url": "https://generativelanguage.googleapis.com/v1beta/openai",
    },
]


def _resolve_api_key(model_entry: dict) -> str:
    """Return the API key from the entry, falling back to env vars."""
    key = model_entry.get("api_key", "")
    if key and key != "your-key-here":
        return key
    model_name = model_entry.get("model", "").lower()
    for prefix, env_var in _ENV_KEY_MAP.items():
        if prefix in model_name:
            return os.getenv(env_var, "")
    return ""


def load_config(path: str = CONFIG_PATH) -> dict:
    """Load configuration from TOML file, falling back to defaults."""
    defaults = {
        "reviewer": {
            "venue": "NeurIPS",
            "min_quorum": 2,
            "max_tokens": 128000,
            "request_timeout": 120,
            "temperature": 0.0,
        },
        "weights": {
            "soundness": 0.35,
            "clarity": 0.30,
            "novelty": 0.20,
            "significance": 0.15,
        },
        "models": _DEFAULT_MODELS,
    }

    if not os.path.exists(path):
        # Fall back to env vars for default model keys
        for m in defaults["models"]:
            m["api_key"] = _resolve_api_key(m)
        return defaults

    with open(path, "rb") as f:
        raw = tomllib.load(f)

    config = {
        "reviewer": {**defaults["reviewer"], **raw.get("reviewer", {})},
        "weights": {**defaults["weights"], **raw.get("weights", {})},
        "models": raw.get("models", defaults["models"]),
    }

    if not config["models"]:
        raise ValueError("autopaper.toml: [[models]] list must not be empty")

    for m in config["models"]:
        m["api_key"] = _resolve_api_key(m)

    return config


_CONFIG = load_config()
REVIEWERS = _CONFIG["models"]
TARGET_VENUE = _CONFIG["reviewer"]["venue"]
WEIGHTS = _CONFIG["weights"]
PAPER_PATH = "paper.tex"
MAX_TOKENS = _CONFIG["reviewer"]["max_tokens"]
REQUEST_TIMEOUT = _CONFIG["reviewer"]["request_timeout"]
TEMPERATURE = _CONFIG["reviewer"]["temperature"]
MIN_QUORUM = _CONFIG["reviewer"]["min_quorum"]


# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------

def compute_review_score(scores: dict, weights: dict | None = None) -> float:
    """Weighted average of dimension scores."""
    w = weights if weights is not None else WEIGHTS
    return sum(scores[dim] * weight for dim, weight in w.items())



def find_weakest_dim(scores: dict, weights: dict | None = None) -> str:
    """Return the dimension with the lowest score."""
    w = weights if weights is not None else WEIGHTS
    return min(w.keys(), key=lambda d: scores[d])



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



def compute_spread(results: list[dict], weights: dict | None = None) -> tuple[str, float]:
    """Return (dimension, spread) for the dimension with the highest reviewer disagreement."""
    w = weights if weights is not None else WEIGHTS
    spreads = {
        dim: max(r[dim] for r in results) - min(r[dim] for r in results)
        for dim in w
    }
    worst = max(spreads, key=spreads.get)
    return worst, spreads[worst]



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

async def _ping_reviewer(reviewer: dict) -> tuple[str, bool, str]:
    """Ping one reviewer. Returns (model_name, success, error_msg)."""
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
        await litellm.acompletion(**kwargs)
        return reviewer["model"], True, ""
    except Exception as e:
        return reviewer["model"], False, str(e)


async def preflight_check() -> None:
    """Check connectivity for all reviewers before full evaluation."""
    print("[preflight] Checking reviewer connectivity...")
    results = await asyncio.gather(
        *[_ping_reviewer(r) for r in REVIEWERS], return_exceptions=True
    )
    reachable = 0
    for result in results:
        if isinstance(result, Exception):
            print(f"[preflight] ✗ (unexpected error) -- {result}", file=sys.stderr)
            continue
        name, ok, err = result
        if ok:
            print(f"[preflight] ✓ {name}")
            reachable += 1
        else:
            print(f"[preflight] ✗ {name} -- {err}", file=sys.stderr)

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



async def call_reviewer(reviewer: dict, paper_text: str) -> tuple[dict, float] | None:
    """Call a single reviewer. Returns (parsed_scores, cost_usd) or None on failure."""
    prompt = REVIEWER_PROMPT_TEMPLATE.format(venue=TARGET_VENUE, paper=paper_text)
    kwargs = {
        "model": _resolve_model(reviewer),
        "messages": [{"role": "user", "content": prompt}],
        "temperature": TEMPERATURE,
        "timeout": REQUEST_TIMEOUT,
    }
    if reviewer.get("api_key"):
        kwargs["api_key"] = reviewer["api_key"]
    if reviewer.get("base_url"):
        kwargs["base_url"] = reviewer["base_url"]

    try:
        response = await litellm.acompletion(**kwargs)
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



async def evaluate(paper_path: str = PAPER_PATH, skip_preflight: bool = False) -> dict:
    """Run all reviewers and return aggregated scores."""
    if not skip_preflight:
        await preflight_check()
    with open(paper_path, "r", encoding="utf-8") as f:
        paper_text = f.read()

    paper_text = truncate_paper(paper_text)

    outcomes = await asyncio.gather(
        *[call_reviewer(r, paper_text) for r in REVIEWERS], return_exceptions=True
    )

    results = []
    per_reviewer = []
    total_cost = 0.0

    for i, outcome in enumerate(outcomes):
        if isinstance(outcome, Exception):
            print(
                f"[WARN] Reviewer {REVIEWERS[i]['model']} failed: {outcome}",
                file=sys.stderr,
            )
            continue
        if outcome is None:
            continue
        scores, cost = outcome
        results.append(scores)
        per_reviewer.append({"model": REVIEWERS[i]["model"], "scores": scores})
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
    spread_dim, spread_val = compute_spread(results)

    return {
        "review_score": score,
        "soundness": avg["soundness"],
        "clarity": avg["clarity"],
        "novelty": avg["novelty"],
        "significance": avg["significance"],
        "weakest_dim": weakest,
        "cost_usd": total_cost,
        "reviewers_ok": successes,
        "per_reviewer": per_reviewer,
        "max_spread_dim": spread_dim,
        "max_spread_val": spread_val,
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
        asyncio.run(preflight_check())
        sys.exit(0)

    t0 = time.time()
    metrics = asyncio.run(evaluate())
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
    for entry in metrics["per_reviewer"]:
        s = entry["scores"]
        dims = " ".join(f"{d}={int(s[d])}" for d in WEIGHTS)
        print(f"reviewer:{entry['model']}:  {dims}")
    print(f"max_spread_dim:   {metrics['max_spread_dim']}")
    print(f"max_spread_val:   {metrics['max_spread_val']:.1f}")
    print("---")
