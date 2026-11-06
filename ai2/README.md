# Ai2 fork tooling

This is Ai2's fork of [omnigent-ai/omnigent](https://github.com/omnigent-ai/omnigent).
These scripts keep it compliant with the upstream Apache 2.0 license and keep
contributions back to upstream clean.

Nothing here exists upstream, and none of it should ever reach an upstream pull
request.

## Branches

| Branch | Contents | Rule |
| --- | --- | --- |
| `main` | byte-identical to upstream | Fast-forward only. Never commit here. |
| `ai2-main` | upstream + fork notice + this directory | The default branch. What visitors see. |

```
 upstream/main   ──A───B───C───D───E───F──▶        omnigent-ai/omnigent
                                       │
            (1) fetch + merge --ff-only│
                                       ▼
 origin/main     ──A───B───C───D───E───F──▶        PRISTINE MIRROR
                           │           ▲
            (2a) cut here  │           │ (2c) merged upstream, returns
                           └──x───y────┘           on the next sync
                              feat/*  ──(2b) PR──▶ upstream
                              no Ai2 notices

        (3) rebase Ai2 commits onto upstream, re-derive notice
                                       │
                                       ▼
 origin/ai2-main ──A───B───C───D───E───F───N──▶    DEFAULT BRANCH
                                           │       always N ahead, 0 behind
                                           │
                                           └──p───q──▶ ai2/* (4) Ai2-only work

                       N = README notice + ai2/
```

**The rule that matters:** branch from `main` for anything you intend to send
upstream; branch from `ai2-main` for anything that stays Ai2's. Getting this
backwards either leaks Ai2 notices into an upstream PR or loses your tooling.

This directory exists only on `ai2-main`, so a branch cut from `main` will not
contain it. That is fine: `apply_notice.py` and `sync-upstream.sh` only ever run
on `ai2-main`, and the checker reads git refs rather than the working tree, so
it can inspect a branch without that branch — or this directory — being checked
out at all:

```sh
git show ai2-main:ai2/check_modified_notices.py \
  | python3 - --expect-none --ref feat/x
```

## Scripts

### `sync-upstream.sh`

Pulls upstream into both branches.

```sh
ai2/sync-upstream.sh
```

Fast-forwards `main`, aborting if it ever diverged — a diverged `main` makes
upstream PRs dirty. Then rebases `ai2-main` onto upstream and re-derives the
README notice, so the fork stays a clean stack of Ai2 commits with no merge
commits.

It finishes by running both checks: the fork notice, and section 4(b) across
every file that differs from upstream. A missing notice fails the sync, so it
stops you before the push rather than after the fork is published.

Rebasing rewrites history, so `ai2-main` is force-pushed:

```sh
git push origin main
git push --force-with-lease origin ai2-main
```

Treat `ai2-main` as a branch that gets rewritten. Base long-lived work on a
branch of your own and rebase it when `ai2-main` moves.

### `test-sync-upstream.sh`

Regression test for the conflict path above.

```sh
ai2/test-sync-upstream.sh
```

It builds a throwaway clone with a fabricated upstream that rewrites README's
first line, runs the sync, and asserts that upstream's content survives and the
notice is re-derived on top of it. That path only runs when upstream edits the
top of README, so it would otherwise sit unexercised until the day it matters.
It tests the working-tree scripts, so run it before committing a change to
them. `KEEP=1` retains the scratch clone for debugging.

### Conflict handling

A README conflict resolves deterministically: take upstream's README verbatim,
re-run `apply_notice.py`. The notice is the only Ai2 change to that file, so
there is nothing else in it to preserve. Conflicts in any other file stop the
script for a human.

### `apply_notice.py`

Keeps the fork notice at the top of `README.md`. The notice is re-derived from
the script rather than carried as a patch, which is why upstream edits to the
README never need a hand-merge.

```sh
python3 ai2/apply_notice.py            # apply or refresh
python3 ai2/apply_notice.py --check    # exit 1 if missing or stale
```

Idempotent. If upstream adds content above the notice, it moves the notice back
to the top and keeps the upstream content.

### `check_modified_notices.py`

Enforces Apache 2.0 section 4(b): *"You must cause any modified files to carry
prominent notices stating that You changed the files."*

```sh
python3 ai2/check_modified_notices.py --worktree   # before committing
python3 ai2/check_modified_notices.py --ref ai2-main
python3 ai2/check_modified_notices.py --list
python3 ai2/check_modified_notices.py --notice-for omnigent/cli.py
```

Before opening an upstream PR, confirm the branch carries no Ai2 notices:

```sh
python3 ai2/check_modified_notices.py --expect-none --ref feat/my-fix
```

## What needs a notice

Only files that **differ from upstream**. Files Ai2 **added** are its own work
and need no "changed" notice.

The checker prints the exact line for each file it flags, in that file's comment
syntax, and `--notice-for PATH` prints it on demand. Put it near the top of the
file.

Files that cannot carry a comment — JSON, generated lockfiles, binary assets —
are exempt and listed by the checker. Record those modifications in `NOTICE`
instead, which is also where Apache 2.0 section 4(d) allows Ai2 to add its own
attribution.
