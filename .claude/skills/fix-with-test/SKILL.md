---
name: fix-with-test
description: Fix an Inhale bug with a game-free test that fails before the fix for the bug's reason and passes after it, and check the test and the fix the way a reviewer would. Use when fixing a bug, a regression or a crash, or when adding or changing a check under tests/.
---

# A fix and its game-free test

A fix comes with the check that shows it ([CONTRIBUTING.md](../../../CONTRIBUTING.md)), and the best check is a test
that fails without the fix and passes with it. How tests are declared and run is in `tests/run_all.py`'s docstring;
this is the order of the work, and the checks a passing test does not do for you.

## 1. The cause first

Find the cause before writing the fix: a log line, a trace, a measurement, the code path read through. When the code
is Longshot's, look whether Longshot fixed it since the base (`git -C ../Longshot log -- <path>`): a sync is then the
fix, not a change here. Can't reproduce or explain it: stop and say so; don't fix a guess.

## 2. Write the test

- A `tests/test_<topic>.py` on the standard library, its docstring saying what it checks and how to run it, what it
  needs declared at the top (`RUN_ALL_ARGS = ["--cxx", "{cxx}"]` and the others in `tests/run_all.py`'s docstring).
- Most C and C++ checks cut the function out of the real source by its text and compile it with stand-ins for what it
  calls. Start from a check that already reads the same file (`git grep -l <file name> tests`) and copy its way of
  cutting; a new check cuts with `tests/srccut.py`. Cut from the source in the tree, never a copy pasted into the
  test: the test has to fail when the source goes back.
- Check the behaviour the bug broke (what the function returns, writes or calls), not the text of the new line: a
  regex for the fix passes a wrong fix and fails a right one written differently.
- A fix behind a switch is tested both ways: unset (fixed) and with the switch that brings back the old behaviour.
- Fast (seconds); `RUN_ALL_SKIP` with the reason where it can't run.

## 3. See it fail, then fix

1. **The test alone, before the fix.** Run it: it must fail, and for the bug's reason. Read the failure; a test that
   fails because it doesn't compile proves nothing. Keep the output.
2. **The fix.** The test passes.

The test and the fix go in one commit, and its message has what the test printed before the fix and after it
([CONTRIBUTING.md](../../../CONTRIBUTING.md)). Mechanical changes (renames, moves) go in commits of their own.

## 4. What the test doesn't check

- **The test against a broken fix.** Undo or change the fix's key line, run the test, see it fail, put the line back.
  A test that passes either way checks nothing.
- **The changed files whole.** The test compiled a cut, so a fix can pass it and not build (a variable declared
  further down the file, a missing include). Build what changed: the renderer alone needs no game
  (`RX_VK_ONLY=1 python -I nx2/build.py --standalone --jobs 4`); or compile each changed `.c`/`.cpp` with
  `-fsyntax-only -Wall -Wextra` and the build's include folders, with the change and without it, and compare the
  warnings. Host files can need headers only the game's lift makes. Say what was compiled and what wasn't.
- **Both compilers.** C++ tests compile with `-Werror`, and clang warns where g++ doesn't:
  `CXX=g++ python -I -B tests/run_all.py <name>`, then `CXX=clang++ ...`. The runner falls back to another compiler
  without a word when `CXX` names one it can't find: check `clang++ --version` first, and with no clang say the clang
  run wasn't done.
- **Skips.** A check whose compiler, headers or tool is missing is skipped, and a skip is not a pass. Read the table,
  or run with `--strict`.
- **The other checks that read the file.** Tests read the source: `git grep -l <file name> tests`, run them, and
  update one your change breaks in the same commit rather than weakening it.
- **The whole suite once**, `python -I -B tests/run_all.py`. A failure there that also fails without your change is
  named as such; check it without the change rather than assuming.
- **What the test doesn't model**: threads, timing, the GPU, a driver, the game's real data. Name it. For a fix in
  memory ownership, threads, timing, saves or anything every player runs, have a second agent review it cold before
  calling it validated: give it the diff and the test, not your conclusion, and ask it to break them.

## 5. Stop and ask the person you work for

- When no game-free test can show the bug: say why, and agree on the in-game evidence instead (the command and what
  it printed, in the commit message).
- When the fix needs a decision: a new default, a switch, a change to a rule in
  [docs/design.md](../../../docs/design.md), or a large change to a file imported from Longshot.
- When the test needs something outside the standard library or a tool the runner doesn't know.
