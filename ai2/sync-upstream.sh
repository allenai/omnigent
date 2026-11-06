#!/usr/bin/env bash
# Sync the Ai2 fork against omnigent-ai/omnigent.
#
#   main      stays byte-identical to upstream (fast-forward only), so PRs
#             cut back to upstream carry no Ai2 content.
#   ai2-main  gets upstream merged in, then the fork notice re-applied.
#
# A README.md conflict is resolved deterministically: take upstream's README
# verbatim and re-derive the notice. The notice is the only Ai2 change to that
# file, so there is nothing else in it to preserve.

set -euo pipefail

UPSTREAM_SLUG="omnigent-ai/omnigent"
UPSTREAM_REMOTE="upstream"
MIRROR_BRANCH="main"
FORK_BRANCH="ai2-main"

# Resolve the sibling scripts against this file, not the working directory, so
# moving or renaming this directory does not break the call sites below.
script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
notice_script="$script_dir/apply_notice.py"
check_script="$script_dir/check_modified_notices.py"

repo_root="$(git rev-parse --show-toplevel)"
cd "$repo_root"

for required in "$notice_script" "$check_script"; do
  [ -f "$required" ] || {
    printf 'error: cannot find %s\n' "$required" >&2
    exit 1
  }
done

say() { printf '\n==> %s\n' "$1"; }
die() { printf 'error: %s\n' "$1" >&2; exit 1; }

if [ -n "$(git status --porcelain --untracked-files=no)" ]; then
  die "working tree has uncommitted changes; commit or stash first"
fi

starting_branch="$(git rev-parse --abbrev-ref HEAD)"
restore_branch() { git checkout --quiet "$starting_branch" 2>/dev/null || true; }
trap restore_branch EXIT

if ! git remote get-url "$UPSTREAM_REMOTE" >/dev/null 2>&1; then
  say "adding $UPSTREAM_REMOTE remote -> $UPSTREAM_SLUG"
  git remote add "$UPSTREAM_REMOTE" "https://github.com/$UPSTREAM_SLUG.git"
fi

say "fetching $UPSTREAM_REMOTE"
git fetch --prune "$UPSTREAM_REMOTE"

# --- mirror branch: fast-forward only -----------------------------------
say "fast-forwarding $MIRROR_BRANCH"
git checkout --quiet "$MIRROR_BRANCH"
if ! git merge --ff-only "$UPSTREAM_REMOTE/$MIRROR_BRANCH"; then
  die "$MIRROR_BRANCH has diverged from upstream. It must stay a pristine
mirror so upstream PRs stay clean. Move the extra commits to a branch, reset
$MIRROR_BRANCH to $UPSTREAM_REMOTE/$MIRROR_BRANCH, then re-run."
fi

# --- fork branch: replay Ai2 commits on top of upstream ------------------
# Rebase rather than merge, so the branch stays a clean stack of Ai2 commits on
# top of upstream with no merge commits. The cost is that it rewrites history,
# so the push below needs --force-with-lease.
say "rebasing $FORK_BRANCH onto $UPSTREAM_REMOTE/$MIRROR_BRANCH"
git checkout --quiet "$FORK_BRANCH"

# Resolve a README conflict and continue, as many times as it recurs. The first
# pass starts the rebase; every later pass resumes the one already in progress.
rebase_step=(git rebase "$UPSTREAM_REMOTE/$MIRROR_BRANCH")
while ! GIT_EDITOR=true "${rebase_step[@]}"; do
  conflicts="$(git diff --name-only --diff-filter=U)"
  if [ -z "$conflicts" ]; then
    git rebase --abort 2>/dev/null || true
    die "rebase failed without conflicts; resolve by hand and re-run."
  fi

  # Any conflict outside README.md is real Ai2-vs-upstream drift: stop and
  # let a human resolve it rather than guessing.
  others="$(printf '%s\n' "$conflicts" | grep -v '^README\.md$' || true)"
  if [ -n "$others" ]; then
    die "conflicts need manual resolution:
$others
Resolve them, run 'git rebase --continue', then re-run this script."
  fi

  # During a rebase the sides are inverted relative to a merge: --ours is the
  # upstream commit being replayed onto, --theirs is the Ai2 commit. Upstream's
  # README is the one to keep; the notice is re-derived on top of it.
  say "resolving README.md: taking upstream, re-deriving notice"
  git checkout --ours -- README.md
  python3 "$notice_script"
  git add README.md
  rebase_step=(git rebase --continue)
done

python3 "$notice_script"

if [ -n "$(git status --porcelain -- README.md)" ]; then
  git add README.md
  git commit -m "chore(ai2): refresh fork notice after upstream sync"
fi

python3 "$notice_script" --check

# The fork notice is only half the obligation. Check section 4(b) on every file
# that differs from upstream, so a missing notice stops the push rather than
# reaching the published fork.
say "checking Apache 2.0 section 4(b) notices"
if ! python3 "$check_script" --ref "$FORK_BRANCH" \
  --upstream "$UPSTREAM_REMOTE/$MIRROR_BRANCH"; then
  die "$FORK_BRANCH is synced, but a modified file carries no section 4(b)
notice. Add the line shown above, commit it, then push."
fi

say "done. $FORK_BRANCH is synced; review, then push:"
printf '    git push origin %s\n' "$MIRROR_BRANCH"
printf '    git push --force-with-lease origin %s\n' "$FORK_BRANCH"
