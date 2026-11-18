"""packaging/pins.txt, the release packages' downloads: every line has an https URL and a 64-hex SHA-256, one line per name
and system, and every name the packaging scripts fetch (packaging/fetch.py path|unpack|version) has its line.

    python -I -B tests/test_packaging_pins.py
"""
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "packaging"))
import fetch  # noqa: E402

# (each script's helpers: F <verb> <name> <os>, and ver <name> with the script's own system)
SCRIPTS = {"packaging/linux/deps.sh": "linux", "packaging/windows/deps.sh": "windows", "packaging/windows/build.sh": None,
           "packaging/linux/appimage.sh": "linux", "packaging/cpm.sh": None}


def wanted():
    """[(script, name, os)] the scripts fetch"""
    out = []
    for script, system in SCRIPTS.items():
        text = (ROOT / script).read_text(encoding="utf-8")
        for name, os_ in re.findall(r"\b(?:F|fetch\.py) (?:path|unpack|version) ([\w-]+) (linux|windows)\b", text):
            out.append((script, name, os_))
        if system:
            out += [(script, name, system) for name in re.findall(r"\bver ([\w-]+)", text)]
        for names in re.findall(r"^for n in ([\w -]+);", text, re.M):   # (cpm.sh: the headers, for both systems)
            out += [(script, n, s) for n in names.split() for s in ("linux", "windows")]
    return out


def main():
    failures = []
    pins = fetch.read_pins()
    seen = set()
    for name, version, system, url, sha in pins:
        if system not in ("linux", "windows", "any"):
            failures.append("%s: system %r is not linux, windows or any" % (name, system))
        if not url.startswith("https://"):
            failures.append("%s: %s is not https" % (name, url))
        if not re.fullmatch(r"[0-9a-f]{64}", sha):
            failures.append("%s: %r is not a SHA-256" % (name, sha))
        for s in (("linux", "windows") if system == "any" else (system,)):
            if (name, s) in seen:
                failures.append("%s: two lines for %s" % (name, s))
            seen.add((name, s))
    want = wanted()
    if len(want) < 10:
        failures.append("only %d fetches found in the scripts: the check no longer reads them" % len(want))
    for script, name, system in want:
        if (name, system) not in seen:
            failures.append("%s fetches %s for %s: no line in pins.txt" % (script, name, system))
    used = {(n, s) for _, n, s in want}
    for name, system in sorted(seen):
        if (name, system) not in used and not any(n == name for n, _ in used):
            failures.append("pins.txt: %s (%s) is fetched by no script" % (name, system))
    for f in failures:
        print("FAIL:", f)
    print("%d pins, %d fetches, %d failures" % (len(pins), len(want), len(failures)))
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
