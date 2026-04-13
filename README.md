# AutoPaper

[中文](README_zh.md) | English

Academic papers go through dozens of revision cycles before submission. You rewrite a paragraph, reread the whole draft, wonder if the framing got better or worse, and repeat. It's slow, and self-review has blind spots.

AutoPaper turns this into a tight automated loop. An AI coding agent rewrites your `paper.tex`, a panel of LLMs scores the draft across four dimensions, bad changes get reverted automatically, and the loop continues — round after round — until the score converges or hits your target.

You bring the agent (Claude Code, Codex, or anything that can edit files and run shell commands). This repo provides the reviewer harness, the operating protocol, and the guardrails.

## How It Works

```
          ┌──── edit paper.tex ────┐
          │                        ▼
      Agent                   reviewer.py
   (Claude Code,              (GPT-4o +
    Codex, etc.)               Claude +
          ▲                    Gemini)
          │                        │
          └── score + feedback ────┘
```

Each round, the agent reads the last review, identifies the weakest scoring dimension, and makes a targeted edit. It commits the change, runs the reviewer, and decides:

- **Score improved?** Keep the commit and move on.
- **Score dropped?** Revert via `git reset --hard HEAD~1`.
- **Too close to call?** Run a confirmation round to break the tie.

Every attempt is logged to `results.tsv` with the commit hash, score, cost, and what was tried. Git history gives you a full audit trail — you can diff any two rounds to see exactly what changed.

## The Review

The reviewer scores your paper on four dimensions, each on a 1–10 integer scale:

| Dimension | Weight | What it measures |
|-----------|--------|-----------------|
| **Soundness** | 35% | Technical correctness, valid methodology and experiments |
| **Clarity** | 30% | Writing quality, structure, ease of understanding |
| **Novelty** | 20% | Originality of contributions vs. prior work |
| **Significance** | 15% | Importance and potential impact on the field |

Three different LLMs review independently, then scores are averaged. The weighted sum becomes `review_score`. The dimension with the lowest average becomes `weakest_dim` — that's where the agent focuses next.

A typical reviewer output looks like this:

```
---
review_score:   6.580
soundness:      7.3
clarity:        5.7
novelty:        6.5
significance:   7.0
weakest_dim:    clarity
cost_usd:       0.91
duration_sec:   48
reviewers_ok:   3/3
---
reviewer:gpt-5.4:  soundness=8 clarity=5 novelty=7 significance=7
reviewer:claude-sonnet-4-6:  soundness=7 clarity=6 novelty=6 significance=7
reviewer:gemini-2.0-flash:  soundness=7 clarity=6 novelty=7 significance=7
max_spread_dim:   soundness
max_spread_val:   1.0
---
```

Per-reviewer breakdowns let you see when models agree and when they don't. `max_spread_val` flags the dimension with the highest disagreement — when it's large, the score is noisy and the agent treats it more carefully.

## What a Run Looks Like

The agent logs every round to `results.tsv`:

```
commit   review_score  cost_usd  status   weakest_dim  description
a1b2c3d  6.120         0.82      keep     clarity      baseline
b2c3d4e  6.580         0.91      keep     clarity      sharpen thesis statement and contributions list
c3d4e5f  6.510         0.88      discard  novelty      rewrote abstract — no improvement
d4e5f6g  6.890         0.85      keep     novelty      add explicit comparison to prior work in intro
e5f6g7h  7.150         0.79      keep     novelty      expand methodology with formal problem statement
f6g7h8i  7.130         0.83      discard  clarity      tighten related work — marginal regression
g7h8i9j  7.340         0.90      keep     clarity      restructure experiments section
```

The loop stops when `review_score` hits the target (default 8.5), improvement plateaus for several consecutive rounds, or you interrupt manually.

## Quick Start

```bash
uv sync                                          # install deps
cp autopaper.example.toml autopaper.toml          # copy config template
# fill in your API keys in autopaper.toml

# replace paper.tex with your draft, then start your agent:
# "Read program.md and start optimizing the paper."
```

## Configuration

Edit `autopaper.toml` to set your reviewer models, target venue, and scoring weights:

```toml
[reviewer]
venue = "NeurIPS"
min_quorum = 2
temperature = 0.0

[weights]
soundness = 0.35
clarity = 0.30
novelty = 0.20
significance = 0.15

[[models]]
model = "gpt-5.4"
api_key = "sk-..."
base_url = "https://api.openai.com/v1"

[[models]]
model = "anthropic/claude-sonnet-4-6"
api_key = "sk-ant-..."
base_url = "https://api.anthropic.com/v1"

[[models]]
model = "gemini/gemini-2.0-flash"
api_key = "gai-..."
base_url = "https://generativelanguage.googleapis.com/v1beta/openai"
```

Add as many `[[models]]` entries as you like — any model that [litellm](https://docs.litellm.ai/docs/providers) supports will work. At least `min_quorum` must succeed for a scored round. Keys live in the TOML file (gitignored) or fall back to environment variables if omitted.

See `autopaper.example.toml` for the full template.

## What the Agent Does

The agent follows `program.md` — a detailed protocol that governs the entire loop:

- Scores the paper, reads the weakest dimension, plans a targeted edit.
- Commits one change per round. Keeps improvements, reverts regressions.
- Asks you when it hits something ambiguous — missing citations, unclear claims, unverifiable numbers.
- Prioritizes substance over polish: argument structure and evidence first, wording second.
- Never invents references. If a citation is needed and not already in the repo, it stops and asks.

## Layout

```
paper.tex              ← your paper (the thing being optimized)
reviewer.py            ← fixed scoring harness — do not edit
program.md             ← full operating protocol for the agent
autopaper.toml         ← your model config and API keys (gitignored)
autopaper.example.toml ← config template (committed)
.autopaper/            ← working memory for the agent
results/               ← optional: raw data, human notes
```

## Caveats

The reviewer scores LaTeX source, not compiled PDF — it cannot see your figures or rendered tables. A higher `review_score` is a useful optimization signal, not a replacement for real peer review.
