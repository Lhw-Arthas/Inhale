"""The packages' build environment (packaging/gui/tools_env.py): the variables it sets for the bundled tools are ones
nx2/make_game.py, nx2/build.py or third_party/a64-kit/tools/toolchain.py read (by their source), the same ones
packaging/linux/AppRun exports, and the environment Play starts the game in has none of the AppImage's or the tools'.

    python -I -B tests/test_packaging_env.py
"""
import os
from pathlib import Path
import re
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "packaging" / "gui"))
import tools_env  # noqa: E402

READERS = ("nx2/make_game.py", "nx2/build.py", "third_party/a64-kit/tools/toolchain.py")


def touch(path):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"")


def main():
    failures = []
    src = "".join((ROOT / f).read_text(encoding="utf-8") for f in READERS)
    with tempfile.TemporaryDirectory() as d:
        appdir = Path(d) / "AppDir"
        root = appdir / "usr" / "share" / "inhale"
        (root / "nx2").mkdir(parents=True)
        touch(appdir / "usr" / "lib" / "inhale" / "llvm" / "upstream" / "bin" / "clang")
        linux = tools_env.linux_tools(str(root))
        inst = Path(d) / "Inhale"
        touch(inst / "llvm-mingw" / "bin" / "clang.exe")
        windows = tools_env.windows_tools(str(inst))
        env = tools_env.build_env({"INHALE_MSVC": "1", "HOME": "/h"}, str(inst), windows=True)
    if set(linux) != {"EMSDK", "INHALE_SYSROOT", "INHALE_FFMPEG", "INHALE_SDL2", "RX_CPM"}:
        failures.append("linux_tools gives %s" % sorted(linux))
    if set(windows) != {"LONGSHOT_MINGW", "RX_CPM"}:
        failures.append("windows_tools gives %s" % sorted(windows))
    if "INHALE_MSVC" in env or env.get("LONGSHOT_MINGW") != windows.get("LONGSHOT_MINGW"):
        failures.append("build_env with the bundled compiler keeps INHALE_MSVC or drops LONGSHOT_MINGW")
    for name in sorted(set(linux) | set(windows)):
        if not re.search(r"""["']%s["']""" % name, src):
            failures.append("%s: not read by %s" % (name, ", ".join(READERS)))
    if tools_env.linux_tools(str(ROOT)) or tools_env.windows_tools(str(ROOT)):
        failures.append("a checkout is taken for a package with bundled tools")
    apprun = (ROOT / "packaging" / "linux" / "AppRun").read_text(encoding="utf-8")
    # (where each tool sits under the AppDir: the same paths in AppRun, export NAME="$LIB/...", as in tools_env.linux_tools)
    lib = re.search(r'^LIB="\$HERE/([^"]+)"', apprun, re.M)
    exported = {n: os.path.join(lib.group(1), p) for n, p in re.findall(r'export (\w+)="\$LIB/([^"]+)"', apprun)} if lib else {}
    for name, path in linux.items():
        rel = os.path.relpath(path, str(appdir))
        if exported.get(name) != rel:
            failures.append("packaging/linux/AppRun sets %s to %s, tools_env to %s" % (name, exported.get(name), rel))
    dirty = {"APPDIR": "/a", "APPIMAGE": "/a.AppImage", "LD_LIBRARY_PATH": "/a/lib", "PYTHONHOME": "/p", "PYTHONUTF8": "1",
             "INHALE_SYSROOT": "/s", "RX_CPM": "/c", "EMSDK": "/e", "ARGV0": "x", "OWD": "/", "LONGSHOT_MINGW": "/m",
             "HOME": "/home/p", "DISPLAY": ":0", "PATH": "/usr/bin"}
    clean = tools_env.play_env(dirty)
    if clean != {"HOME": "/home/p", "DISPLAY": ":0", "PATH": "/usr/bin"}:
        failures.append("play_env keeps %s" % sorted(set(clean) - {"HOME", "DISPLAY", "PATH"}))
    # (make_game.py's own list is a subset: what it drops, Play drops too)
    m = re.search(r"^GAME_ENV_DROP = \(([^)]*)\)", (ROOT / "nx2" / "make_game.py").read_text(encoding="utf-8"), re.M)
    theirs = set(re.findall(r'"([^"]+)"', m.group(1))) if m else set()
    if not theirs or not theirs <= set(tools_env.PLAY_DROP):
        failures.append("make_game.GAME_ENV_DROP %s is not inside tools_env.PLAY_DROP" % sorted(theirs))
    for f in failures:
        print("FAIL:", f)
    print("%d failures" % len(failures))
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
