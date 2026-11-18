# Contributing

## The rule that has no exceptions: no game files

Nothing from the game goes into this repository, a patch, an issue or a pull request:

- no game package, module, archive, movie, sound, texture, shader, font or save, whole or in part;
- no keys, tickets or certificates;
- nothing made from the game: decompressed modules, the loaded image, disassembly, lifted C, shader dumps,
  screenshots of memory, test builds, or a log that quotes game data;
- no text that explains how to obtain or dump a game, or how to get around a console's protection.

`.gitignore` keeps the usual places out (`work/`, `gen/`, `exefs/`, `romfs/` and the game's file types), and
`tests/test_hygiene.py` fails when a tracked file has one of those types. Neither can see inside a file: check what
you add. A fix that needs a fact about the game says it as a number in code or in `docs/design.md` (an offset, a
build id, a function's address, a count), never as a copy of the game's bytes or text.

A screenshot of the running game in a report is fine when it shows the problem.

## Working on it

- Everything runs from the clone with the Python of `.venv` (`README.md`). Game-free checks:
  `python -I -B tests/run_all.py`, `python -I scripts/check_third_party.py`.
- `third_party/` holds unmodified copies. A change goes in a new folder with its own `PROVENANCE.md`, not into a part.
- Inhale follows Longshot (`PROVENANCE.md`). Keep changes to imported files small and put this game's code in files
  of its own (`host/kirby_*.c`, `nx2/kirby_*.py`), so that `scripts/sync_upstream.py` keeps applying. Code for the
  other game (`oot_*`) is gated on that game's build id, not deleted.
- Plain ASCII punctuation in code, comments, documents and commit messages. Texts shown to players in other
  languages are the exception.
- A fix comes with the check that shows it: a test under `tests/` when the game is not needed, otherwise the command
  and what it printed, in the commit message.
- Stages, their exit checks and what is known about this game are in `docs/design.md`. Update it with what you find.

## Licence

Contributions are under the GPL, version 3 or later, as the rest (`LICENSE`, `CREDITS.md`).
