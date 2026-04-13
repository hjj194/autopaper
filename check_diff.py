"""
Validate paper_diff.tex for annotation errors that cause LaTeX compilation failures.
Usage: uv run python check_diff.py [paper_diff.tex]
Exits 0 if clean, 1 if issues found (prints each issue with line number).
"""

import re
import sys

DIFF_PATH = "paper_diff.tex"

# Allowed annotation commands (changes package)
ANNOTATION_CMDS = (r"\added{", r"\deleted{", r"\replaced{")

# Forbidden patterns — old approach, always wrong
FORBIDDEN_PATTERNS = [
    (r"\\textcolor\{red\}\{\\sout\{", "\\textcolor{red}{\\sout{...}} — use \\deleted{} or comment markers instead"),
    (r"\\textcolor\{blue\}\{",        "\\textcolor{blue}{...} — use \\added{} instead"),
    (r"\\sout\{",                     "bare \\sout{} — use \\deleted{} or comment markers instead"),
]

# Deleted block line limit before comment markers are required
DELETED_LINE_LIMIT = 3


def find_annotation_spans(text: str) -> list[tuple[int, int, str]]:
    """Return list of (start_char, end_char, cmd) for each annotation block."""
    spans = []
    for cmd in ANNOTATION_CMDS:
        pos = 0
        while True:
            idx = text.find(cmd, pos)
            if idx == -1:
                break
            open_at = idx + len(cmd) - 1
            depth = 0
            end = open_at
            while end < len(text):
                if text[end] == "{":
                    depth += 1
                elif text[end] == "}":
                    depth -= 1
                    if depth == 0:
                        break
                end += 1
            spans.append((idx, end, cmd.rstrip("{")))
            pos = idx + 1
    return spans


def char_to_line(text: str, pos: int) -> int:
    return text[:pos].count("\n") + 1


def check(path: str) -> list[str]:
    with open(path, "r", encoding="utf-8") as f:
        text = f.read()

    issues = []

    # --- Forbidden pattern check ---
    for pattern, message in FORBIDDEN_PATTERNS:
        for m in re.finditer(pattern, text):
            line = char_to_line(text, m.start())
            issues.append(f"Line {line}: Forbidden annotation — {message}")

    # --- Annotation span checks ---
    spans = find_annotation_spans(text)

    for start, end, cmd in spans:
        block = text[start : end + 1]
        line = char_to_line(text, start)

        # 1. Wraps a LaTeX environment
        if re.search(r"\\begin\s*\{|\\end\s*\{", block):
            issues.append(
                f"Line {line}: `{cmd}` wraps a \\begin{{}} or \\end{{}} environment. "
                "Use comment markers instead:\n"
                "    % [DELETED BEGIN]\n"
                "    ...equation or environment...\n"
                "    % [DELETED END]"
            )

        # 2. Crosses a paragraph break
        if "\n\n" in block:
            issues.append(
                f"Line {line}: `{cmd}` spans a paragraph break. "
                "Split into separate annotations per paragraph."
            )

        # 3. Deleted block exceeds line limit
        if cmd == r"\deleted" and block.count("\n") > DELETED_LINE_LIMIT:
            issues.append(
                f"Line {line}: `\\deleted` block is {block.count(chr(10))} lines "
                f"(limit {DELETED_LINE_LIMIT}). "
                "Use comment markers for large deleted sections."
            )

        # 4. Nested annotation commands
        inner = block[len(cmd) + 1:]
        for other_cmd in ANNOTATION_CMDS:
            if other_cmd in inner:
                issues.append(
                    f"Line {line}: `{cmd}` contains nested `{other_cmd.rstrip('{')}`. "
                    "Flatten nested annotations."
                )
                break

    # --- Preamble check ---
    if any(cmd in text for cmd in ANNOTATION_CMDS):
        if "changes" not in text:
            issues.append(
                "Missing \\usepackage[final]{changes} in preamble — "
                "required for \\added, \\deleted, \\replaced commands."
            )

    return issues


def main() -> None:
    path = sys.argv[1] if len(sys.argv) > 1 else DIFF_PATH
    try:
        issues = check(path)
    except FileNotFoundError:
        print(f"[check_diff] File not found: {path}", file=sys.stderr)
        sys.exit(1)

    if not issues:
        print(f"[check_diff] OK — no annotation errors found in {path}")
        sys.exit(0)

    print(f"[check_diff] {len(issues)} issue(s) found in {path}:\n")
    for issue in issues:
        print(f"  - {issue}")
    print("\nFix each issue in paper_diff.tex and re-run check_diff.py until it passes.")
    sys.exit(1)


if __name__ == "__main__":
    main()
