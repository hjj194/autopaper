# AutoPaper

[中文](README_zh.md) | English

AutoPaper is a minimal framework for iteratively improving a LaTeX paper with an AI agent and a fixed multi-LLM reviewer.

The agent edits the draft, the reviewer scores it, and the loop repeats around a single metric: `review_score`.

## Why AutoPaper

- Focused write scope. The agent optimizes `paper.tex` and may keep short operational notes in `.autopaper/working_memory.md`.
- Fixed evaluation harness. `reviewer.py` stays constant across runs.
- Multi-reviewer scoring. Multiple LLMs score the same draft independently.
- Simple optimization loop. Improve, review, keep or discard, repeat.

## How It Works

AutoPaper is built around three files:

- `paper.tex`: the paper draft the agent edits
- `reviewer.py`: the review harness that scores the draft
- `program.md`: the operating instructions for the agent loop

During a run, the agent may also maintain `.autopaper/working_memory.md` as a short scratchpad for current hypotheses, failed ideas, and open questions.

The reviewer scores four dimensions:

- `soundness`
- `clarity`
- `novelty`
- `significance`

Each reviewer returns integer scores from 1 to 10. AutoPaper then averages across reviewers and computes a weighted `review_score`, so aggregated outputs can be fractional.

## Quick Start

```bash
# 1. Install dependencies
uv sync

# 2. Configure reviewers in reviewer.py
# Edit the REVIEWERS list at the top of reviewer.py

# 3. Replace paper.tex with your draft
# results/ is optional; use it for experiment notes, human summaries, or raw artifacts, or leave it empty

# 4. Start Claude Code or another coding agent in this directory
# Example prompt:
# Read program.md and start optimizing the paper in paper.tex.
```

The agent should run `uv run reviewer.py --dry-run` first to verify reviewer connectivity, then start the scored optimization loop. The full workflow is designed to run through an external agent such as Claude Code or Codex.

`reviewer.py` reviews the LaTeX source in `paper.tex`, not a compiled PDF.

## Reviewer Configuration

Configure models by editing the `REVIEWERS` list at the top of `reviewer.py`.

```python
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
```

Each entry uses the same OpenAI-compatible shape: `model`, `api_key`, and `base_url`. For other providers, keep the same structure and point `base_url` at your endpoint.

```python
{
    "model": "your-model-name",
    "api_key": os.getenv("PROVIDER_API_KEY", ""),
    "base_url": "https://your-endpoint/v1",
}
```

At least `MIN_QUORUM` reviewers must succeed for a run to count.

## Stopping Conditions

The optimization loop stops when one of the following happens:

- `review_score` reaches `TARGET_SCORE`
- score improvement stays below the configured threshold for `CONVERGENCE_ROUNDS`
- you stop the agent manually

These rules are defined in `program.md`.

## Agent Rules

- Use git and `results.tsv` for round-by-round history, and `.autopaper/working_memory.md` for short-lived working memory.
- When goals, facts, missing experiment details, or missing citations are ambiguous, ask the human instead of guessing.
- Work from first principles: strengthen the problem statement, contribution logic, evidence chain, and weakest claim before polishing style.
- Treat bibliography facts conservatively. Reuse verified references already in the repo, but do not invent new citations or bibliography entries.

## Repository Layout

```text
autopaper/
├── .autopaper/
│   └── working_memory.md
├── paper.tex
├── reviewer.py
├── program.md
├── pyproject.toml
├── uv.lock
├── results/
│   └── raw/
├── README.md
└── README_zh.md
```

## Notes

- `reviewer.py` runs a connectivity preflight before the full review.
- Do not commit API keys or provider secrets into the repository.
- Higher `review_score` is useful, but it is still a proxy metric, not a substitute for real peer review.
