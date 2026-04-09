# AutoPaper

[中文](README_zh.md) | English

AutoPaper is a paper-optimization loop: an external coding agent rewrites `paper.tex`, and a fixed multi-LLM reviewer scores the draft.

It is not a standalone agent runtime. You bring Claude Code, Codex, or another coding agent; this repo provides the reviewer, workflow, and guardrails.

## How It Works

1. Start your agent in this repository and ask it to read `program.md`.
2. The agent runs `uv run reviewer.py --dry-run`, then begins editing `paper.tex`.
3. `reviewer.py` scores the LaTeX source, the agent keeps or reverts the change, and the loop repeats.

## Quick Start

```bash
# 1. Install dependencies
uv sync

# 2. Edit the REVIEWERS list at the top of reviewer.py

# 3. Replace paper.tex with your draft
# results/ is optional; use it for notes, human summaries, or raw artifacts, or leave it empty

# 4. Start Claude Code or another coding agent in this directory
# Example prompt:
# Read program.md and start optimizing the paper in paper.tex.
```

## What the Agent Will Do

- Run `uv run reviewer.py --dry-run` before the first scored review.
- Track round history with git and `results.tsv`.
- Keep a short working scratchpad in `.autopaper/working_memory.md`.
- Ask the human when goals, facts, experiment details, or citations are ambiguous.
- Work from first principles: fix the problem, contribution logic, evidence, and weakest claim before polishing style.
- Treat bibliography facts conservatively. Reuse verified references already in the repo, but do not invent new citations or bibliography entries.

## Reviewer Configuration

Configure models by editing the `REVIEWERS` list in `reviewer.py`.

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

Each reviewer entry uses the same shape: `model`, `api_key`, and `base_url`. For other providers, keep that structure and point `base_url` at your endpoint.

```python
{
    "model": "your-model-name",
    "api_key": os.getenv("PROVIDER_API_KEY", ""),
    "base_url": "https://your-endpoint/v1",
}
```

At least `MIN_QUORUM` reviewers must succeed for a scored run.

## Stopping Conditions

The loop stops when one of the following happens:

- `review_score` reaches `TARGET_SCORE`
- improvement stays below the configured threshold for `CONVERGENCE_ROUNDS`
- you stop the agent manually

The full operating policy lives in `program.md`.

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

## Limits

- `reviewer.py` reviews the LaTeX source in `paper.tex`, not a compiled PDF.
- A higher `review_score` is useful, but it is still a proxy metric, not a substitute for real peer review.
- Do not commit API keys or provider secrets into the repository.
