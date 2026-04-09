# AutoPaper

This is an experiment to have the LLM autonomously optimize academic paper writing.

## Configuration

```
CONVERGENCE_ROUNDS = 5     # stop if improvement < 0.05 for this many consecutive rounds
TARGET_SCORE      = 8.5    # stop if review_score reaches this threshold
                           # set either to 0 to disable

PYTHON_CMD        = "uv run"   # change to "python3" or "python" if uv is not available
```

## Setup

To set up a new experiment, work with the user to:

1. **Agree on a run tag**: propose a tag based on today's date (e.g. `apr10`). The branch `autopaper/<tag>` must not already exist — this is a fresh run.
2. **Create the branch**: `git checkout -b autopaper/<tag>` from current master.
3. **Read the in-scope files**: Read these files for full context:
   - `README.md` — repository context.
   - `reviewer.py` — fixed evaluation harness. Do not modify.
   - `paper.tex` — **primary source of truth**. This is the file you modify. If the paper already contains results, figures, and tables, this is all you need.
   - `results/results.md` — (optional) human-written experiment summary. Only present when writing a paper from scratch or when the human wants to provide extra context.
   - `results/raw/` — (optional) raw experimental data (CSV, figures, logs). Only consult if present and you need to verify specific numbers not already in `paper.tex`.
4. **Initialize results.tsv**: Create `results.tsv` with just the header row:
   ```
   commit	review_score	cost_usd	status	weakest_dim	description
   ```
5. **Run connectivity preflight**: `$PYTHON_CMD reviewer.py --dry-run` and confirm reviewer APIs are reachable before scoring anything.
6. **Run baseline**: `$PYTHON_CMD reviewer.py > review.log 2>&1` to establish the first scored baseline.
7. **Confirm and go**: Confirm setup looks good.

Once you get confirmation, kick off the experimentation.

## Experimentation

**What you CAN do:**
- Modify `paper.tex` — this is the only file you edit. Everything is fair game: abstract, introduction, related work, methodology, experiments, conclusion, argument structure, sentence-level clarity.

**What you CANNOT do:**
- Modify `reviewer.py`. It is read-only. It contains the fixed evaluation harness.
- Modify anything under `results/`. It is read-only input.
- Install new packages or add dependencies.

**The goal is simple: get the highest review_score.** Each reviewer assigns integer scores from 1-10 for the four dimensions, then the system averages across reviewers and computes a weighted final score (soundness 35%, clarity 30%, novelty 20%, significance 15%). This means the aggregated dimension scores and `review_score` can be fractional.

**Focus each round on the weakest dimension** (from `weakest_dim` in review.log). Don't try to improve everything at once.

**Writing quality criterion**: Do not inflate the paper to chase scores. Adding filler sentences, buzzwords, or padding degrades real quality. A 0.05 score gain from padding is not worth keeping. A 0.05 gain from genuinely clearer writing? Keep it. Same score but more concise? Keep it.

## Output format

Once the reviewer finishes it prints a summary like this. Individual reviewer scores are integers, but the aggregated metrics below may be fractional:

```
---
review_score:   7.234
soundness:      7.8
clarity:        6.9
novelty:        6.5
significance:   7.1
weakest_dim:    clarity
cost_usd:       0.87
duration_sec:   142
reviewers_ok:   3/3
---
```

Extract key metrics:
```bash
grep -E "^(review_score|cost_usd|weakest_dim):" review.log
```

## Logging results

Log every experiment to `results.tsv` (tab-separated, NOT comma-separated).

The TSV has a header row and 6 columns:
```
commit	review_score	cost_usd	status	weakest_dim	description
```

1. git commit hash (short, 7 chars)
2. review_score achieved (e.g. 7.234) — use 0.000 for crashes
3. cost in USD, round to .2f (e.g. 0.87) — use 0.00 for crashes
4. status: `keep`, `discard`, or `crash`
5. weakest_dim from this round's review
6. short description of what this experiment tried

Example:
```
commit	review_score	cost_usd	status	weakest_dim	description
a1b2c3d	6.120	0.82	keep	clarity	baseline
b2c3d4e	6.580	0.91	keep	clarity	sharpen thesis statement and contributions list
c3d4e5f	6.510	0.88	discard	novelty	rewrote abstract — no improvement
d4e5f6g	6.890	0.85	keep	novelty	add explicit comparison to prior work in intro
```

## The experiment loop

The experiment runs on a dedicated branch (e.g. `autopaper/apr10`).

**Do not pause to ask the human if you should continue.** The human might be asleep. Before the first scored run, make sure the reviewer preflight passes. If the reviewer API fails, try to fix it and retry. If you get 3 consecutive crashes, check `reviewer.py` configuration and environment variables.

The loop stops automatically when either stopping condition is met (see Configuration above), or when the human interrupts manually.

LOOP FOREVER (until a stop condition triggers):

1. Read review.log, extract weakest dimension: `grep "^weakest_dim:" review.log`
2. Edit `paper.tex` to improve that dimension. If `results/results.md` or `results/raw/` exist, consult them to verify specific numbers; otherwise rely on what is already in `paper.tex`.
3. `git commit` — one commit per round only, so that `HEAD~1` revert is precise.
4. Run the reviewer: `$PYTHON_CMD reviewer.py > review.log 2>&1`
5. Extract results: `grep -E "^(review_score|cost_usd|weakest_dim):" review.log`
6. If grep output is empty, the reviewer crashed. Run `tail -n 30 review.log` to read the error. If fixable (e.g., missing API key, JSON parse error), fix and re-run. If not, log as crash and revert.
7. Record in results.tsv (6 columns: commit, review_score, cost_usd, status, weakest_dim, description)
8. If review_score improved (higher) → keep the commit, advance the branch
9. If review_score equal or worse → `git reset --hard HEAD~1` to revert
10. **Check stop conditions** (evaluate after each round):
    - If `TARGET_SCORE > 0` and `review_score >= TARGET_SCORE` → stop, report final score
    - If `CONVERGENCE_ROUNDS > 0` and the last N rounds all had improvement < 0.05 → stop, report convergence
    - Otherwise continue
