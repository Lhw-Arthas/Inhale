"""The release packages' scripts: each shell script parses (bash -n; AppRun with sh -n), and what the installer
(packaging/windows/inhale.nsi) removes or points at is something packaging/windows/build.sh stages: a name build.sh does
not make would leave the uninstaller deleting nothing, or a shortcut pointing nowhere.

    python -I -B tests/test_packaging_scripts.py
"""
from pathlib import Path
import re
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
RUN_ALL_SKIP = {"windows": "needs bash and sh: the scripts run on Linux"}


def staged_names(build_sh):
    """The names build.sh puts at the top of the stage folder $S"""
    names = set()
    m = re.search(r"git ls-files -z -- ([^|]+)\|", build_sh)
    if m:
        names |= set(m.group(1).split())
    names |= set(re.findall(r'"\$S/([\w.-]+)', build_sh))   # (cp ... "$S/gui/", mkdir -p "$S/third_party/sdl2" ...)
    for line in re.findall(r'^cp -a ((?:"\$DEPS/[\w-]+" )+)"\$S/"', build_sh, re.M):
        names |= set(re.findall(r'\$DEPS/([\w-]+)', line))
    return names


def main():
    failures = []
    apprun = ROOT / "packaging" / "linux" / "AppRun"
    for script in sorted((ROOT / "packaging").rglob("*.sh")) + [apprun]:
        if not script.stat().st_mode & 0o100:   # (docker.sh and the release workflow start them by their path)
            failures.append("%s is not executable" % script.relative_to(ROOT))
        if script == apprun:
            continue
        r = subprocess.run(["bash", "-n", str(script)], capture_output=True, text=True)
        if r.returncode:
            failures.append("bash -n %s: %s" % (script.relative_to(ROOT), r.stderr.strip()))
    r = subprocess.run([shutil.which("sh") or "sh", "-n", str(apprun)], capture_output=True, text=True)
    if r.returncode:
        failures.append("sh -n packaging/linux/AppRun: %s" % r.stderr.strip())
    build_sh = (ROOT / "packaging" / "windows" / "build.sh").read_text(encoding="utf-8")
    nsi = (ROOT / "packaging" / "windows" / "inhale.nsi").read_text(encoding="utf-8")
    staged = staged_names(build_sh)
    if not {"nx2", "llvm-mingw", "python", "cpm", "gui"} <= staged:
        failures.append("build.sh's stage, as read here, is %s: the check no longer reads it" % sorted(staged))
    removed = re.findall(r'(?:RMDir /r|Delete) "\$INSTDIR\\([\w.-]+)"', nsi)
    for name in removed:
        if name not in staged and name != "uninstall.exe":
            failures.append("inhale.nsi removes $INSTDIR\\%s, which build.sh does not stage" % name)
    for name in staged - set(removed):
        failures.append("build.sh stages %s, which inhale.nsi's RemoveOurs leaves behind" % name)
    for path in set(re.findall(r'(?:\$INSTDIR|\$\{STAGE\})\\([\w.-]+\\[\w.\\-]+)', nsi)):
        top, rest = path.split("\\", 1)
        if top not in staged:
            failures.append("inhale.nsi names %s, not under a folder build.sh stages" % path)
        elif top == "gui" and not (ROOT / "packaging" / ("icons" if rest.endswith((".ico", ".png")) else "gui") / rest).is_file():
            failures.append("inhale.nsi names gui\\%s, which packaging/ does not have" % rest)
        elif top == "python" and rest not in ("pythonw.exe", "python.exe"):
            failures.append("inhale.nsi names python\\%s" % rest)
    # (the hot list every package carries: function names only, f_<guest address>, as nx2/lift.py reads A64_HOT_FUNCS)
    hot = ROOT / "packaging" / "profiles" / "hot_funcs.txt"
    lines = hot.read_text(encoding="utf-8").split() if hot.is_file() else []
    if not lines or any(not re.fullmatch(r"f_[0-9a-f]{8}", l) for l in lines):
        failures.append("packaging/profiles/hot_funcs.txt is missing, empty or holds more than f_<address> names")
    for script, var in (("packaging/linux/appimage.sh", "T"), ("packaging/windows/build.sh", "S")):
        if 'cp packaging/profiles/hot_funcs.txt "$%s/work/hot_funcs.txt"' % var not in (ROOT / script).read_text(encoding="utf-8"):
            failures.append("%s does not put the hot list in the package's work/" % script)
    for f in failures:
        print("FAIL:", f)
    print("%d names staged, %d failures" % (len(staged), len(failures)))
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
