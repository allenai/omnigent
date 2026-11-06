# Agent instructions

These rules apply to all files in the `ai2` directory.

## Use the deterministic tools

These scripts exist because they give the same result every time. Use them.
Do not do their work by hand. Do not write their output from memory.

| Do not do this by hand | Run this |
| --- | --- |
| Write or edit the fork notice in `README.md` | `python3 ai2/apply_notice.py` |
| Type the section 4(b) notice line | `python3 ai2/check_modified_notices.py --notice-for <path>` |
| Decide which files need a notice | `python3 ai2/check_modified_notices.py --worktree` |
| Merge or rebase upstream | `ai2/sync-upstream.sh` |
| Resolve a `README.md` conflict | `ai2/sync-upstream.sh` resolves it |
| Test a change to these scripts | `ai2/test-sync-upstream.sh` |

The notice text has one source: `NOTICE_TEXT` in
`ai2/check_modified_notices.py`. Change it there. Then run
`python3 ai2/apply_notice.py` to update `README.md`.

## Branch rules

- Read `ai2/README.md` first. It gives the branch model.
- Do not commit to the `main` branch. Keep `main` identical to upstream.
- Branch from `main` for work that goes to upstream. Branch from `ai2-main` for
  work that stays at Ai2.
- Add the section 4(b) notice to each upstream file that you change. A file
  that you add does not need the notice.
- Push `ai2-main` with `--force-with-lease`. The sync rebases that branch.

## More commands

Prove that a branch has no Ai2 notice. Run this before you open an upstream
pull request:

```sh
python3 ai2/check_modified_notices.py --expect-none --ref <branch>
```

Check a branch or a commit instead of the working tree:

```sh
python3 ai2/check_modified_notices.py --ref <ref>
```

List the files that differ from upstream:

```sh
python3 ai2/check_modified_notices.py --list
```

Verify the README notice:

```sh
python3 ai2/apply_notice.py --check
```

The checker reads git refs. Run it against a branch that does not contain this
directory:

```sh
git show ai2-main:ai2/check_modified_notices.py \
  | python3 - --expect-none --ref <branch>
```
