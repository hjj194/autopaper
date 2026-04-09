# AutoPaper

[中文](README_zh.md) | English

Autonomous academic paper writing optimization, inspired by [autoresearch](https://github.com/karpathy/autoresearch).

## What this repo does

AutoPaper lets an AI agent iteratively improve a LaTeX paper draft.

The loop is simple:
1. Edit `paper.tex`
2. Run `reviewer.py`
3. Read the weakest dimension and score
4. Keep or discard the draft change
5. Repeat

The reviewer is a fixed multi-LLM ensemble that scores four dimensions:
- soundness
- clarity
- novelty
- significance

Those scores are aggregated into a single `review_score`.

## Minimal repo layout

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

## Key files

- `paper.tex`: the only file the agent should edit
- `reviewer.py`: fixed review harness
- `program.md`: agent instructions for the experiment loop

## Requirements

- Python 3.10+
- [uv](https://docs.astral.sh/uv/)
- At least 2 reachable LLM reviewers

## Quick start

```bash
# 1. Install dependencies
uv sync

# 2. Configure reviewers in reviewer.py
# Use environment variables for API keys

# 3. Replace paper.tex with your draft

# 4. Run a baseline review
uv run reviewer.py

# 5. Start your coding agent in this directory
# Example prompt:
# Read program.md and kick off a new experiment.
```

## Reviewer configuration

Edit the `REVIEWERS` list in `reviewer.py`.

Example:

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

## Notes

- `reviewer.py` runs a connectivity preflight before full evaluation.
- At least `MIN_QUORUM` reviewers must succeed.
- `results/` is optional input for human notes or raw experiment artifacts.
- Do not commit secrets into `reviewer.py`.
