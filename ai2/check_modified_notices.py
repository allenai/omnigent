#!/usr/bin/env python3
"""Verify Apache-2.0 section 4(b) notices on upstream files that Ai2 changed.

Section 4(b) of this repository's LICENSE requires modified files to carry
prominent notices stating that you changed them. Files Ai2 *added* are its own
work and need no such notice, so only files that differ from upstream are
checked.

Everything is read through git, so this never needs to run inside the branch it
inspects:

    ai2/check_modified_notices.py                    # check HEAD
    ai2/check_modified_notices.py --worktree         # check uncommitted work
    ai2/check_modified_notices.py --ref ai2-main
    ai2/check_modified_notices.py --list
    ai2/check_modified_notices.py --notice-for omnigent/cli.py

Branches destined for an upstream pull request must carry no Ai2 notices at
all; --expect-none asserts that:

    ai2/check_modified_notices.py --expect-none --ref feat/my-fix
"""

from __future__ import annotations

import argparse
import fnmatch
import subprocess
import sys
from pathlib import Path

# The canonical wording. Kept here so this one file defines both the required
# text and the test for it; apply_notice.py imports it rather than repeating it.
NOTICE_TEXT = "Modified by The Allen Institute for Artificial Intelligence."

# Matched instead of NOTICE_TEXT so surrounding punctuation and comment syntax
# do not matter.
NOTICE_TOKEN = "Modified by The Allen Institute for Artificial Intelligence"

# Tried in order when --upstream is not given.
UPSTREAM_CANDIDATES = ("upstream/main", "origin/main", "main")

# Files that cannot carry an inline notice. Record these in NOTICE instead.
EXEMPT: tuple[tuple[str, str], ...] = (
    ("*.json", "JSON has no comment syntax"),
    ("*.lock", "generated lockfile; comments are rewritten"),
    ("uv.lock", "generated lockfile; comments are rewritten"),
    ("pnpm-lock.yaml", "generated lockfile; comments are rewritten"),
    ("*.svg", "binary-ish asset"),
    ("*.png", "binary asset"),
    ("*.jpg", "binary asset"),
    ("*.ico", "binary asset"),
    ("*.woff*", "binary asset"),
    ("LICENSE", "license text must be reproduced verbatim"),
)

# Comment syntax used by --notice-for.
COMMENT_STYLES: dict[str, str] = {
    ".py": "# {}",
    ".sh": "# {}",
    ".bash": "# {}",
    ".nix": "# {}",
    ".rb": "# {}",
    ".toml": "# {}",
    ".yaml": "# {}",
    ".yml": "# {}",
    ".js": "// {}",
    ".jsx": "// {}",
    ".mjs": "// {}",
    ".cjs": "// {}",
    ".ts": "// {}",
    ".tsx": "// {}",
    ".go": "// {}",
    ".rs": "// {}",
    ".java": "// {}",
    ".kt": "// {}",
    ".kts": "// {}",
    ".swift": "// {}",
    ".c": "// {}",
    ".h": "// {}",
    ".css": "/* {} */",
    ".md": "<!-- {} -->",
    ".html": "<!-- {} -->",
    ".xml": "<!-- {} -->",
    ".sql": "-- {}",
}


class GitError(RuntimeError):
    """Raised when a git command fails."""


def git(*args: str) -> str:
    """Run a git command and return stdout, raising GitError on failure."""
    result = subprocess.run(["git", *args], capture_output=True, text=True, check=False)
    if result.returncode != 0:
        raise GitError(f"git {' '.join(args)}: {result.stderr.strip()}")
    return result.stdout


def ref_exists(ref: str) -> bool:
    return (
        subprocess.run(
            ["git", "rev-parse", "--verify", "--quiet", f"{ref}^{{commit}}"],
            capture_output=True,
            check=False,
        ).returncode
        == 0
    )


def resolve_upstream(explicit: str | None) -> str:
    if explicit:
        if not ref_exists(explicit):
            raise GitError(f"upstream ref {explicit!r} does not exist")
        return explicit
    for candidate in UPSTREAM_CANDIDATES:
        if ref_exists(candidate):
            return candidate
    raise GitError(
        "no upstream ref found (tried "
        + ", ".join(UPSTREAM_CANDIDATES)
        + "). Add the remote: git remote add upstream "
        "https://github.com/omnigent-ai/omnigent.git && git fetch upstream"
    )


def changed_paths(upstream: str, ref: str | None) -> list[tuple[str, str]]:
    """Return (status, path) for each path differing between upstream and ref.

    A two-dot diff is deliberate: "differs from upstream right now" is what
    section 4(b) means by modified, and it gives the same answer on any branch.
    A ref of None compares against the working tree instead of a commit.
    """
    diff_args = ["diff", "--name-status", "-M", upstream]
    if ref is not None:
        diff_args.append(ref)
    raw = git(*diff_args)
    entries: list[tuple[str, str]] = []
    for line in raw.splitlines():
        if not line.strip():
            continue
        fields = line.split("\t")
        status = fields[0]
        # Renames and copies report the destination path last.
        path = fields[-1]
        entries.append((status[0], path))

    if ref is None:
        # Untracked files are additions; git diff does not report them.
        for path in git("ls-files", "--others", "--exclude-standard").splitlines():
            if path.strip():
                entries.append(("A", path.strip()))
    return entries


def exemption_for(path: str) -> str | None:
    name = Path(path).name
    for pattern, reason in EXEMPT:
        if fnmatch.fnmatch(path, pattern) or fnmatch.fnmatch(name, pattern):
            return reason
    return None


def read_bytes(ref: str | None, path: str) -> bytes:
    """Read a path's contents at ref, or from the working tree when ref is None."""
    if ref is None:
        try:
            return Path(path).read_bytes()
        except OSError as exc:
            raise GitError(f"cannot read {path}: {exc}") from exc
    result = subprocess.run(["git", "show", f"{ref}:{path}"], capture_output=True, check=False)
    if result.returncode != 0:
        raise GitError(f"cannot read {path} at {ref}")
    return result.stdout


def is_binary(data: bytes) -> bool:
    return b"\x00" in data[:8000]


def comment_line(path: str) -> str:
    style = COMMENT_STYLES.get(Path(path).suffix.lower(), "# {}")
    return style.format(NOTICE_TEXT)


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--ref", default="HEAD", help="ref to inspect")
    parser.add_argument(
        "--worktree",
        action="store_true",
        help="inspect the working tree, including uncommitted changes",
    )
    parser.add_argument(
        "--upstream",
        default=None,
        help=f"upstream ref to compare against (default: first of {UPSTREAM_CANDIDATES})",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="list the modified files and their status; check nothing",
    )
    parser.add_argument(
        "--expect-none",
        action="store_true",
        help="fail if any Ai2 notice is present (for upstream-bound branches)",
    )
    parser.add_argument(
        "--notice-for",
        metavar="PATH",
        help="print the notice line with the comment syntax for PATH, then exit",
    )
    args = parser.parse_args()

    if args.notice_for:
        print(comment_line(args.notice_for))
        return 0

    source: str | None = None if args.worktree else args.ref
    label = "working tree" if args.worktree else args.ref

    try:
        upstream = resolve_upstream(args.upstream)
        if source is not None and not ref_exists(source):
            raise GitError(f"ref {source!r} does not exist")
        entries = changed_paths(upstream, source)
    except GitError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    added: list[str] = []
    deleted: list[str] = []
    modified: list[str] = []
    for status, path in entries:
        if status == "A":
            added.append(path)
        elif status == "D":
            deleted.append(path)
        else:
            modified.append(path)

    if args.list:
        print(f"comparing {label} against {upstream}")
        for label, paths in (
            ("modified (notice required)", modified),
            ("added (no notice required)", added),
            ("deleted", deleted),
        ):
            print(f"\n{label}: {len(paths)}")
            for path in sorted(paths):
                print(f"  {path}")
        return 0

    # Upstream-bound branches must carry no Ai2 notices at all.
    if args.expect_none:
        offenders = []
        for path in sorted(modified + added):
            try:
                data = read_bytes(source, path)
            except GitError:
                continue
            if not is_binary(data) and NOTICE_TOKEN in data.decode("utf-8", errors="replace"):
                offenders.append(path)
        if offenders:
            print(
                f"error: {len(offenders)} file(s) carry an Ai2 notice but are bound for upstream:",
                file=sys.stderr,
            )
            for path in offenders:
                print(f"  {path}", file=sys.stderr)
            print(
                "\nUpstream PRs must not carry Ai2 notices. Cut the branch from "
                "main, not ai2-main.",
                file=sys.stderr,
            )
            return 1
        print(f"{label}: no Ai2 notices present ({len(modified)} modified)")
        return 0

    missing: list[str] = []
    exempt_hits: list[tuple[str, str]] = []
    for path in sorted(modified):
        reason = exemption_for(path)
        if reason:
            exempt_hits.append((path, reason))
            continue
        try:
            data = read_bytes(source, path)
        except GitError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 2
        if is_binary(data):
            exempt_hits.append((path, "binary file"))
            continue
        if NOTICE_TOKEN not in data.decode("utf-8", errors="replace"):
            missing.append(path)

    print(f"comparing {label} against {upstream}")
    print(f"  modified: {len(modified)}   added: {len(added)} (no notice required)")
    if exempt_hits:
        print(f"  exempt:   {len(exempt_hits)} (record these in NOTICE)")
        for path, reason in exempt_hits:
            print(f"    {path} — {reason}")

    if missing:
        print(
            f"\nerror: {len(missing)} modified file(s) lack the Apache 2.0 section 4(b) notice:",
            file=sys.stderr,
        )
        for path in missing:
            print(f"  {path}", file=sys.stderr)
            print(f"      add: {comment_line(path)}", file=sys.stderr)
        return 1

    print("\nall modified files carry the required notice")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
