"""
Validate paper_diff.tex for annotation errors that cause LaTeX compilation failures.
Usage: uv run python check_diff.py [paper_diff.tex]
Exits 0 if clean, 1 if issues found (prints each issue with line number).
"""

import re
import sys

DIFF_PATH = "paper_diff.tex"

# Annotation commands from the `changes` package
ANNOTATION_CMDS = (r"\added{", r"\deleted{", r"\replaced{")


def find_annotation_spans(text: str) -> list[tuple[int, int, str]]:
    """Return list of (start_char, end_char, cmd) for each annotation block."""
    spans = []
    for cmd in ANNOTATION_CMDS:
        pos = 0
        while True:
            idx = text.find(cmd, pos)
            if idx == -1:
                break
            # find the matching closing brace for the first argument
            open_at = idx + len(cmd) - 1  # position of opening '{'
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
    spans = find_annotation_spans(text)

    for start, end, cmd in spans:
        block = text[start : end + 1]
        line = char_to_line(text, start)

        # 1. Annotation wraps a LaTeX environment
        if re.search(r"\\begin\s*\{|\\end\s*\{", block):
            issues.append(
                f"Line {line}: `{cmd}` wraps a \\begin{{}} or \\end{{}} environment. "
                "Use % [ADDED BEGIN] / % [ADDED END] comment markers instead."
            )

        # 2. Annotation crosses a paragraph break
        if "\n\n" in block:
            issues.append(
                f"Line {line}: `{cmd}` spans a paragraph break (blank line). "
                "Split into separate annotations per paragraph."
            )

        # 3. Nested annotation commands
        inner = block[len(cmd) + 1 :]  # content inside the first {
        for other_cmd in ANNOTATION_CMDS:
            if other_cmd in inner:
                issues.append(
                    f"Line {line}: `{cmd}` contains nested annotation `{other_cmd.rstrip('{')}`. "
                    "Flatten nested annotations."
                )
                break

    # 4. Check that the changes package is loaded
    if r"\usepackage" in text and "changes" not in text:
        issues.append(
            "Missing `\\usepackage[final]{changes}` in preamble — "
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
