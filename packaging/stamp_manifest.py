"""Writes packaging/recomplauncher.json to <out> with prepare.version set to <release> (the package's VERSION).

RecompLauncher runs the prepare step again for a player who already set up only when prepare.version changes ("not
even a new release" asks for it otherwise, its schema says), and this game's prepare step builds the game: so each
release's manifest carries its own name there, and an update rebuilds the game.

Usage: python3 -I packaging/stamp_manifest.py <out> <release>
"""
import json
from pathlib import Path
import sys

out, release = sys.argv[1:]
m = json.loads((Path(__file__).resolve().parent / "recomplauncher.json").read_text(encoding="utf-8"))
m["prepare"]["version"] = release
Path(out).write_text(json.dumps(m, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
