# Inhale: Kirby and the Forgotten Land on PC

Inhale is a work-in-progress PC port of *Kirby and the Forgotten Land, Nintendo Switch 2 Edition + Star-Crossed
World* by static recompilation. Python tools translate the game's AArch64 code to C, clang compiles that C, a native
runtime written in C stands in for the console's system and its NVN2 graphics API, and a Vulkan back end replays the
graphics calls. There is no CPU or GPU emulation.

It is a fork of [Longshot](https://git.magicbean.dev/MagicBeanDev/Longshot), which does the same for another game
(`PROVENANCE.md`, `CREDITS.md`). Most of the code is still Longshot's; its name was changed through the tree by a
script (`scripts/rename_full.py`).

**Status: early.** The opening, the title screen and the first stage run at full speed; nothing past them has been
played. The stages of the work and what each has reached are in [docs/design.md](docs/design.md).

## You supply the game

Inhale contains no game code, no game data and no keys, and nothing made from them. To build anything you need your
own copy of the game's files, as one of:

- the game's `.nup` package, or
- the extracted folders: `exefs/` (the code title) and `aoc/<title id>/romfs/` (the data title).

This repository does not tell you how to get them, and its issue tracker is not the place to ask. Never commit or
post them, or anything made from them (`CONTRIBUTING.md`).

## What you need

- Linux, x86-64 (the only system tested so far; the Windows paths of Longshot are still in the tree, unverified).
- clang and lld, Python 3.12 or newer, git.
- A GPU and driver with Vulkan 1.3 and mesh shaders; SDL 3 and FFmpeg's development files.
- About 12 GB of disk for the extracted game data, plus the build's own files under `work/`.

## Set up

```
python -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
PY=".venv/bin/python -I"
```

Tell the tools where your package is, either with the `INHALE_NUP` environment variable or by writing its path as
the only line of `work/nup.txt` (`work/` is ignored by git):

```
mkdir -p work && printf '%s\n' "/path/to/your/package.nup" > work/nup.txt
NUP="$(cat work/nup.txt)"
```

## One command: a game folder

```
$PY nx2/make_game.py --nup "$NUP" --out ~/Games/Inhale
~/Games/Inhale/inhale
```

It unpacks the package into the folder, translates and compiles the code, and puts the program beside the data.
From extracted folders: `--game <folder with exefs/ and aoc/>`, or `--exefs <dir> --aoc <dir>`. `--update <folder>`
builds a folder again with newer tools from the files it keeps. Saves go to `$XDG_DATA_HOME/inhale`. The Insert key
opens the port's own menu.

The rest of this page is the same work step by step, for development.

## Check the tools and the package

```
$PY -B tests/run_all.py                    # the game-free checks
$PY scripts/check_third_party.py           # third_party/ is unmodified
$PY nx2/nup.py "$NUP"                      # list the package: a code title and a data title
$PY nx2/nup.py "$NUP" --extract work/dump  # code to work/dump/exefs, data to work/dump/aoc/<title id>/romfs
$PY nx2/dump.py --dump work/dump --set     # what the code is: platform, modules, build id
```

## Translate, build, run

```
$PY nx2/lift.py                            # translate everything and report coverage
$PY nx2/test_insn.py --per 6 --states 12   # each instruction form against Unicorn
$PY nx2/test_leaf.py --count 3000 --states 4
$PY nx2/lift.py --standalone --write       # write the C of the standalone program
$PY nx2/build.py --standalone --jobs 16    # compile and link it
work/sa/build/inhale work/sa/image/image.bin --romfs work/dump/romfs --aoc work/dump/aoc --user work/user
```

`docs/design.md` says how far each of these gets today and which switches help when one stops.

## Following Longshot

`scripts/sync_upstream.py` applies Longshot's changes since the commit recorded in `PROVENANCE.md`. It puts both
sides of Longshot's diff through the rule of `scripts/rename_full.py` first, so the changes arrive under this fork's
names; run `scripts/rename_full.py` after a sync to see that nothing is left to rename.

## Licence

GPL-3.0-or-later (`LICENSE`). Copyright lines, the notice of modification and the people whose work this is:
`CREDITS.md`.

Inhale is an unofficial fan project, not affiliated with or endorsed by Nintendo or HAL Laboratory.
