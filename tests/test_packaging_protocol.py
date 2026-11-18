"""The builder window's parser of nx2/make_game.py's output (packaging/gui/protocol.py): every @@ form and the plain "shaders
were not prepared" line become the right event, and the @@ forms make_game.py's docstring lists are exactly the ones the
parser knows, so a change of the protocol upstream fails here instead of showing as log lines in the window.

    python -I -B tests/test_packaging_protocol.py
"""
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "packaging" / "gui"))
import protocol  # noqa: E402

CASES = [
    ("@@stage lift Translating the code", ("stage", ("lift", "Translating the code"))),
    ("@@progress 0.25", ("progress", 0.25)),
    ("@@progress 1.7", ("progress", 1.0)),
    ("@@plan 12 340", ("plan", (12, 340))),
    ("@@file lifted_0012.c 41.5 new", ("file", ("lifted_0012.c", 41.5, "new"))),
    ("@@eta 610", ("eta", 610.0)),
    ("@@times 2400 1800 2500", ("times", (2400.0, 1800.0, 2500.0))),
    ("@@times 2400 1800 -1", ("times", (2400.0, 1800.0, None))),
    ("@@check ok Kirby, version 1.0.0 (395fc326)", ("check", (True, "Kirby, version 1.0.0 (395fc326)"))),
    ("@@check bad This is not the right game", ("check", (False, "This is not the right game"))),
    ("@@done /home/p/Games/Inhale", ("done", "/home/p/Games/Inhale")),
    ("@@error The disk is full.\n", ("error", "The disk is full.")),
    ("the shaders were not prepared now (no GPU): the game prepares them at its first start",
     ("not_prepared", "the shaders were not prepared now (no GPU): the game prepares them at its first start")),
    ("compiling 3 of 40", ("log", "compiling 3 of 40")),
    ("@@whatever 1", ("log", "@@whatever 1")),
]


def main():
    failures = []
    for line, want in CASES:
        got = protocol.parse(line)
        if got != want:
            failures.append("parse(%r) = %r, expected %r" % (line, got, want))
    doc = (ROOT / "nx2" / "make_game.py").read_text(encoding="utf-8").split('"""')[1]
    listed = tuple(re.findall(r"^\s+@@(\w+) ", doc, re.M))
    if listed != protocol.KINDS:
        failures.append("make_game.py's docstring lists %s; protocol.KINDS is %s: teach packaging/gui/protocol.py the change"
                        % (listed, protocol.KINDS))
    src = (ROOT / "nx2" / "make_game.py").read_text(encoding="utf-8")
    m = re.search(r'^NOT_PREPARED = "([^"]+)"', src, re.M)
    if not m or m.group(1) != protocol.NOT_PREPARED:
        failures.append("make_game.py's NOT_PREPARED is %r, protocol.NOT_PREPARED %r" % (m and m.group(1), protocol.NOT_PREPARED))
    for f in failures:
        print("FAIL:", f)
    print("%d cases, %d failures" % (len(CASES), len(failures)))
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
