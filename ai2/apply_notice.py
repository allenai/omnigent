#!/usr/bin/env python3
"""Keep the Ai2 fork notice at the top of README.md.

The notice is re-derived from this file rather than carried as a patch, so
pulling upstream never leaves a README conflict to resolve by hand: take
upstream's README verbatim, then run this script.
"""

from __future__ import annotations

import argparse
import contextlib
import sys
from pathlib import Path

# The Apache 2.0 section 4(b) wording is defined once, in the checker;
# importing it keeps this notice and the check that enforces it in step.
from check_modified_notices import NOTICE_TEXT

START_MARKER = "<!-- ai2-fork-notice:start -->"
END_MARKER = "<!-- ai2-fork-notice:end -->"

UPSTREAM_SLUG = "omnigent-ai/omnigent"
UPSTREAM_URL = f"https://github.com/{UPSTREAM_SLUG}"

# Prefixed so it can never collide with a link definition upstream adds.
LINK_LABEL = "ai2-upstream"

# One block satisfies both obligations: identifying the fork, and the section
# 4(b) statement that this file was changed. The 4(b) line stands alone rather
# than sitting mid-paragraph, which is what "prominent" asks for.
NOTICE = f"""{START_MARKER}
> [!IMPORTANT]
> **This is a fork of [{UPSTREAM_SLUG}][{LINK_LABEL}] and is not the
> official project.** It tracks upstream with Ai2-specific changes on top.
>
> {NOTICE_TEXT}
>
> For the official project, releases, and support, go to
> [{UPSTREAM_SLUG}][{LINK_LABEL}].

[{LINK_LABEL}]: {UPSTREAM_URL}
{END_MARKER}"""


class NoticeError(RuntimeError):
    """Raised when README.md carries a fork notice that cannot be rewritten."""


def render(readme_text: str) -> str:
    """Return README text with exactly one current fork notice at the top."""
    start_count = readme_text.count(START_MARKER)
    end_count = readme_text.count(END_MARKER)

    if start_count != end_count:
        raise NoticeError(f"unbalanced notice markers: {start_count} start, {end_count} end")
    if start_count > 1:
        raise NoticeError(f"found {start_count} fork notices, expected at most one")

    if start_count == 0:
        return f"{NOTICE}\n\n{readme_text.lstrip()}"

    start = readme_text.index(START_MARKER)
    end = readme_text.index(END_MARKER) + len(END_MARKER)
    if end < start:
        raise NoticeError("notice end marker precedes its start marker")

    rewritten = readme_text[:start] + NOTICE + readme_text[end:]
    if start != 0:
        # Upstream content drifted above the notice; move it back to the top.
        rewritten = rewritten.replace(NOTICE, "", 1).lstrip()
        rewritten = f"{NOTICE}\n\n{rewritten}"
    return rewritten


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--readme",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "README.md",
        help="path to the README to update (default: repository README.md)",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="exit non-zero if the notice is missing or stale; write nothing",
    )
    args = parser.parse_args()

    if not args.readme.is_file():
        print(f"error: {args.readme} does not exist", file=sys.stderr)
        return 2

    original = args.readme.read_text(encoding="utf-8")
    try:
        updated = render(original)
    except NoticeError as exc:
        print(f"error: {args.readme}: {exc}", file=sys.stderr)
        return 2

    if original == updated:
        print(f"{args.readme}: fork notice is current")
        return 0

    if args.check:
        missing = START_MARKER not in original
        reason = "missing" if missing else "stale"
        script = Path(__file__).resolve()
        with contextlib.suppress(ValueError):
            # Outside the current directory, keep the absolute path.
            script = script.relative_to(Path.cwd())
        print(
            f"error: {args.readme}: fork notice is {reason}. Run: python3 {script}",
            file=sys.stderr,
        )
        return 1

    args.readme.write_text(updated, encoding="utf-8")
    print(f"{args.readme}: fork notice updated")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
