#!/usr/bin/env bash
# Regression test for sync-upstream.sh's rebase conflict path.
#
# That path only runs when upstream edits the top of README.md, which may be
# weeks apart, so it would otherwise go unexercised until it matters. It is
# also the easiest part to get backwards: during a rebase --ours is the
# upstream commit being replayed onto, not the Ai2 commit.
#
# The test fabricates an upstream that edits README's first line -- guaranteed
# to collide with the fork notice -- and asserts that upstream's content
# survives and the notice is re-derived on top of it. If the sides were
# inverted, upstream's change would be silently discarded and the first
# assertion would fail.
#
# Everything happens in a throwaway clone; this repository is never modified.
# The working-tree copy of ai2/ is used, so uncommitted changes are tested.
#
#   ai2/test-sync-upstream.sh        # run it
#   KEEP=1 ai2/test-sync-upstream.sh # keep the scratch clone for debugging

set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TD="$(mktemp -d)"
MARKER="UPSTREAM-EDITED-THE-HEADER"

cleanup() {
  if [ "${KEEP:-0}" = "1" ]; then
    printf '\nscratch clone kept at %s\n' "$TD"
  else
    rm -rf "$TD"
  fi
}
trap cleanup EXIT

say() { printf '\n=== %s ===\n' "$1"; }
pass() { printf 'PASS  %s\n' "$1"; }
fail() {
  printf 'FAIL: %s\n' "$1"
  exit 1
}

say "build a fake upstream that edits the top of README.md"
git clone -q --branch main --single-branch "$REPO" "$TD/fake-upstream"
cd "$TD/fake-upstream"
{
  printf '[![%s](https://example.invalid/b.svg)](https://example.invalid)\n\n' "$MARKER"
  cat README.md
} > README.new
mv README.new README.md
git -c user.email=test@invalid -c user.name=test commit -q -am \
  "upstream: add a badge at the top of README"
echo "upstream README line 1: $(head -1 README.md)"

say "clone this repository as the working copy"
git clone -q "$REPO" "$TD/work"
cd "$TD/work"
git checkout -q -B main origin/main
git checkout -q -B ai2-main origin/ai2-main

# Test the working-tree scripts rather than the committed ones, so this catches
# a regression before it is committed.
cp "$REPO"/ai2/*.py "$REPO"/ai2/*.sh ai2/
git -c user.email=test@invalid -c user.name=test commit -q --amend --no-edit -a

git remote add upstream "$TD/fake-upstream"
echo "ai2-main: $(git log --oneline -1)"

say "run sync-upstream.sh (expect a README conflict it resolves itself)"
set +e
./ai2/sync-upstream.sh > "$TD/sync.log" 2>&1
rc=$?
set -e
echo "exit code: $rc"
grep -E 'resolving README|rebasing|fast-forward|done\.' "$TD/sync.log" || true
if [ "$rc" -ne 0 ]; then
  echo "--- log tail ---"
  tail -30 "$TD/sync.log"
  fail "script exited $rc"
fi

say "ASSERTIONS"

# The assertion that catches an inverted --ours/--theirs.
if grep -q "$MARKER" README.md; then
  pass "upstream's new content survived the conflict"
else
  echo "--- README head ---"
  head -20 README.md
  fail "upstream content was DISCARDED (--ours is the wrong side)"
fi

if grep -q 'ai2-fork-notice:start' README.md; then
  pass "fork notice re-derived"
else
  fail "fork notice missing after resolve"
fi

if [ "$(head -1 README.md)" = "<!-- ai2-fork-notice:start -->" ]; then
  pass "notice sits at line 1"
else
  fail "notice is not at the top (line 1 = $(head -1 README.md))"
fi

if python3 ai2/apply_notice.py --check > /dev/null 2>&1; then
  pass "apply_notice --check clean"
else
  fail "apply_notice --check failed"
fi

if python3 ai2/check_modified_notices.py --ref ai2-main > /dev/null 2>&1; then
  pass "section 4(b) check clean"
else
  fail "4(b) check failed"
fi

behind="$(git rev-list --count ai2-main..upstream/main)"
if [ "$behind" -eq 0 ]; then
  pass "0 behind upstream ($(git rev-list --count upstream/main..ai2-main) ahead)"
else
  fail "still $behind behind upstream"
fi

merges="$(git log --merges --oneline upstream/main..ai2-main | wc -l | tr -d ' ')"
if [ "$merges" -eq 0 ]; then
  pass "no merge commits"
else
  fail "$merges merge commit(s) present"
fi

if [ "$(git rev-parse main)" = "$(git rev-parse upstream/main)" ]; then
  pass "main == upstream/main"
else
  fail "main diverged from upstream"
fi

say "a modified upstream file with no notice must fail the sync"

printf '\n<!-- an Ai2 edit that carries no notice -->\n' >> CONTRIBUTING.md
git -c user.email=test@invalid -c user.name=test commit -q -am \
  "ai2: edit an upstream file without a notice"

set +e
./ai2/sync-upstream.sh > "$TD/sync2.log" 2>&1
rc2=$?
set -e

if [ "$rc2" -ne 0 ]; then
  pass "sync fails when a modified file has no section 4(b) notice"
else
  echo "--- log tail ---"
  tail -20 "$TD/sync2.log"
  fail "sync accepted a tree that breaks section 4(b)"
fi

if grep -q 'CONTRIBUTING.md' "$TD/sync2.log"; then
  pass "sync names the file that needs the notice"
else
  fail "sync did not name the offending file"
fi

if grep -q 'review, then push' "$TD/sync2.log"; then
  fail "sync told us to push a tree that breaks section 4(b)"
else
  pass "sync withholds the push instructions on failure"
fi

printf '\nALL ASSERTIONS PASSED\n'
