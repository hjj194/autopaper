# AutoPaper

[中文](README_zh.md) | English

AutoPaper is a minimal framework for iteratively improving a LaTeX paper with an AI agent and a fixed multi-LLM reviewer.

The agent edits the draft, the reviewer scores it, and the loop repeats around a single metric: `review_score`.

## Why AutoPaper

- Single editable target. The agent only changes `paper.tex`.
- Fixed evaluation harness. `reviewer.py` stays constant across runs.
- Multi-reviewer scoring. Multiple LLMs score the same draft independently.
- Simple optimization loop. Improve, review, keep or discard, repeat.

## How It Works

AutoPaper is built around three files:

- `paper.tex`: the paper draft the agent edits
- `reviewer.py`: the review harness that scores the draft
- `program.md`: the operating instructions for the agent loop

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
# Use environment variables for API keys

# 3. Replace paper.tex with your draft

# 4. Run a baseline review
uv run reviewer.py

# 5. Start your coding agent in this directory
# Example:
# Read program.md and kick off a new experiment.
```

## Reviewer Configuration

Edit the `REVIEWERS` list in `reviewer.py`.

```python
REVIEWERS = [
    {
        "model": "gpt-4o",
        "api_key": os.getenv("OPENAI_API_KEY", ""),
        "base_url": None,
    },
    {
        "model": "claude-sonnet-4-6",
        "api_key": os.getenv("ANTHROPIC_API_KEY", ""),
        "base_url": None,
    },
    {
        "model": "gemini/gemini-2.0-flash",
        "api_key": os.getenv("GEMINI_API_KEY", ""),
        "base_url": None,
    },
]
```

For OpenAI-compatible providers, set both `api_key` and `base_url`.

At least `MIN_QUORUM` reviewers must succeed for a run to count.

## Repository Layout

```text
autopaper/
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
- `results/` can hold experiment notes or raw artifacts, but can also stay empty.
- Do not commit API keys or provider secrets into the repository.
- Higher `review_score` is useful, but it is still a proxy metric, not a substitute for real peer review.
