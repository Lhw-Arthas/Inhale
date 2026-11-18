---
name: sync-upstream
description: Bring Longshot's later changes into Inhale with scripts/sync_upstream.py, settle the conflicts, check the result and sort out what arrived. Use when asked to sync with, follow, update from or catch up with Longshot (upstream), or to move PROVENANCE.md's upstream-base.
---

# Syncing with Longshot

`scripts/sync_upstream.py` takes Longshot's diff from the base recorded in `PROVENANCE.md` to a revision, puts both
sides through the rename (`scripts/rename_full.py`), applies it with `git apply -3` and rewrites the base line. Its
docstring has the details. It commits nothing. This is the order of the work around it.

Sync every day or two. Longshot makes about 80 commits a day, and the conflicts grow faster than the window: measured
on 2026-11-17, one day back was 6 conflicted files with 13 places, three days 14 files with 45.

## 1. Before

- **A clean tree.** The script refuses changes under the imported paths (`git apply -3` works on the index). Ask the
  person you work for to commit or stash; don't do either on your own.
- **Fetch and pick a revision.** `git -C ../Longshot fetch` (it writes to that clone and uses the network: ask
  first), then choose `origin/main` or a commit of it. `--upstream` names a clone somewhere else.
- **Read the list.** `python -I scripts/sync_upstream.py --to <rev> --list` prints what would be applied and what
  would not, and changes nothing. A file "not tracked here" was left out at the import or removed since.

## 2. Sync

`python -I scripts/sync_upstream.py --to <rev>`. It ends with the new base, and says so when files have conflicts.
When it says nothing was applied, nothing changed and the base stays: read git's message above it.

## 3. Settle the conflicts

`git diff --name-only --diff-filter=U` lists them. In each, this fork's side is small and usually marked `(inhale)`:
take Longshot's change and put this fork's lines back on it. The usual places:

- **`gpu/vk/vk_api.h`, `MKWVK_API_VERSION`**: conflicts each time Longshot bumps it, since the number differs here.
  Take Longshot's number plus one.
- **`gpu/vk/menu_i18n.h`** has nothing of this fork's and merges clean: this fork's rows are in
  `gpu/vk/menu_i18n_inhale.h`. Keep it so; never settle anything by writing a row of this fork's there.
  `python -I -B tests/test_menu_i18n_inhale.py` says what a sync moved under them: a retired text that Longshot
  dropped (take it out of `kRetired`), a text of this fork's that Longshot now has (take the rows out here), or a new
  text of Longshot's that this fork's menu does not show (its row stays; add the text to `kRetired`).
- **`gpu/vk/vk_menu.cpp`**: this fork hides or rewords rows; keep its side of those rows on Longshot's new code, and
  run the checks that read the file (`git grep -l vk_menu.cpp tests`).
- **`nx2/make_game.py`, `nx2/nup.py`**: the messages about game files were reworded at the import (`PROVENANCE.md`,
  *Files changed at import*). Keep this fork's wording; `tests/test_make_game_cache.py` expects it.

`git add` each file once its marks are gone. A conflict that needs a decision about this game's behaviour is the
person's to make: stop and ask.

## 4. The stand-in

`nx2/oot_patches.py` is never applied: Longshot's file holds text made from the other game, and the one here is a
stand-in with the same names and empty tables. When Longshot changed its file, the sync prints the top-level names it
gained that the stand-in lacks. For each one the tree uses (`git grep -n "oot_patches\.<name>" nx2`), add a table
that is empty or a function with Longshot's arguments that changes nothing, as the ones there. Read Longshot's file
for the signature only; none of its text is copied.

## 5. Check

- `python -I scripts/rename_full.py` ends with `0 places in 0 files, 0 files renamed`. Anything else is a name that
  arrived outside the rule: look at it, then `--write`, or fix the rule (and `tests/test_sync_rules.py`).
- `python -I scripts/check_third_party.py`.
- `python -I -B tests/run_all.py`. Compare the failures with the run before the sync: a new one is the sync's.
- With the game's files at hand, the lift and a build (`README.md`): the checks run no game.

## 6. Sort out what arrived

A file new in Longshot is applied whatever it is. About one in five belongs to something this fork left out
(`PROVENANCE.md`, *What was left out*): scripts of Longshot's releases, packaging and team workflow, tests bound to
those or to the text of Longshot's `nx2/oot_patches.py`, and tests that fail in this tree for that reason.
`git status --short` shows the new files as `A`. For each that belongs to a kind left out: `git rm -f` it and add it
to that kind's list in `PROVENANCE.md` (the lists are sorted, and each names its count). Longshot's later changes to
it are then skipped as "not tracked here".

## 7. Commit

When the person asks: one commit for the sync, with the revision in its message, holding the applied changes, the
settled conflicts, the stand-in's new names and `PROVENANCE.md` (the base line and the lists).
