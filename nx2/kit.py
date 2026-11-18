"""Paths: the vendored a64-kit (third_party/a64-kit) on sys.path, the dump, the work folder.

The dump (the user's own decrypted copy: a folder with exefs/ and romfs/) is never copied into the repository. Its
location comes from, in order: INHALE_EXEFS (the exefs folder itself), INHALE_DUMP (the folder holding exefs/ and romfs/),
or the first line of work/dump.txt (the same, written once by hand or by nx2/dump.py). Each INHALE_ variable falls back to
upstream's OOT_ one of the same name, which the imported tools and tests still set.
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
KIT = os.path.join(ROOT, "third_party", "a64-kit")
for sub in ("lift", "tools", "hos", "rt"):
    p = os.path.join(KIT, sub)
    if p not in sys.path:
        sys.path.insert(0, p)
HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

# (each name is written out where it is read: tests/test_lift_cache.py finds the lift's variables that way)
WORK = os.environ.get("INHALE_WORK") or os.environ.get("OOT_WORK") or os.path.join(ROOT, "work")


def env_on(name):
    """An on/off switch, the game's rule (gpu/vk/compat/inhale_env.h env_on): unset, empty, 0, false, off or no (any
    case) is off; anything else is on"""
    return os.environ.get(name, "").strip().lower() not in ("", "0", "false", "off", "no")


def _dump_root():
    if os.environ.get("INHALE_DUMP") or os.environ.get("OOT_DUMP"):
        return os.environ.get("INHALE_DUMP") or os.environ["OOT_DUMP"]
    cfg = os.path.join(WORK, "dump.txt")
    if os.path.exists(cfg):
        for line in open(cfg, encoding="utf-8"):
            line = line.strip()
            if line and not line.startswith("#"):
                return line
    return None


def data_romfs(dump):
    """The romfs that holds the game's data under a dump folder: romfs/, or, when the code title has none or an empty one
    and the data is a title of its own, that title's (nx2/nup.py unpacks it to aoc/<title id>/romfs)"""
    own = os.path.join(dump, "romfs")
    if os.path.isdir(own) and os.listdir(own):
        return own
    aoc = os.path.join(dump, "aoc")
    for title in sorted(os.listdir(aoc)) if os.path.isdir(aoc) else ():
        other = os.path.join(aoc, title, "romfs")
        if os.path.isdir(other) and os.listdir(other):
            return other
    return own


DUMP = _dump_root()
EXEFS = os.environ.get("INHALE_EXEFS") or os.environ.get("OOT_EXEFS") or (os.path.join(DUMP, "exefs") if DUMP else None)
ROMFS = os.environ.get("INHALE_ROMFS") or os.environ.get("OOT_ROMFS") or (data_romfs(DUMP) if DUMP else None)


def need_exefs():
    if not EXEFS or not os.path.isdir(EXEFS):
        raise SystemExit("no exefs: set INHALE_DUMP (the folder with exefs/ and romfs/) or INHALE_EXEFS, or write the dump "
                         "folder into %s" % os.path.join(WORK, "dump.txt"))
    return EXEFS


def game_modules(exefs=None):
    """The exefs's code modules in rtld's load order (rtld, main, subsdk0..9, sdk) that exist, without rtld"""
    exefs = exefs or need_exefs()
    order = ["main"] + ["subsdk%d" % i for i in range(10)] + ["sdk"]
    return [m for m in order if os.path.exists(os.path.join(exefs, m))]


# Other sessions' benchmarks need a quiet machine: they hold this file for the few minutes a timing run takes.
# Heavy jobs (builds, test runs, the full emit) wait while it exists; a job already running may finish.
BENCH_LOCK = os.path.join(os.path.dirname(ROOT), ".bench-lock")


def wait_for_quiet(what="this job"):
    import time
    waited = 0
    while os.path.exists(BENCH_LOCK):
        if not waited:
            print("waiting for %s to go (a benchmark is running) before %s" % (BENCH_LOCK, what), flush=True)
        time.sleep(60)
        waited += 1
    if waited:
        print("benchmark lock gone after ~%d min" % waited, flush=True)
