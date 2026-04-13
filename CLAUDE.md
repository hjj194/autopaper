# AutoPaper

Read `program.md` for the full operational protocol. That is the primary instruction set.

## Key files

- `program.md` — full operational protocol. **Read this first.**
- `reviewer.py` — fixed evaluation harness. DO NOT MODIFY.
- `autopaper.toml` — reviewer and model configuration.
- `paper.tex` — the paper being optimized. This is what you edit.
- `results.tsv` — tab-separated scoring history (one row per round).
- `.autopaper/working_memory.md` — lightweight run state.

## Hard rules

- Never modify `reviewer.py` or anything under `results/`.
- Do not invent citations or bibliography entries.
