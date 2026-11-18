"""What must never be tracked, and the punctuation rule (CONTRIBUTING.md):

  - no tracked file has a game file's type (a package, a module, an archive, a movie, a sound, a save, a key file);
  - no tracked text file outside third_party/ has an en dash (U+2013) or an em dash (U+2014). The in-game menu's texts
    are the exception: they are shown to players, in thirteen languages, and ranges and some languages use them.

    python -I -B tests/test_hygiene.py

It reads git's list of tracked files, so a file not added yet is not checked: run it after `git add`.
"""
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# (the types .gitignore keeps out, and the ones a console package or its contents have)
GAME_TYPES = {
    ".nup", ".nsp", ".nsz", ".xci", ".xcz", ".nca", ".ncz", ".nso", ".nro", ".npdm", ".keys", ".tik", ".cert", ".sav",
    ".bin", ".cmp", ".cmpbin", ".webm", ".bfsha", ".bfsar", ".bfstm", ".bfres", ".bntx", ".bfwav", ".bars", ".opus",
    ".sarc", ".szs", ".zs", ".byml", ".msbt",
}
EN_DASH, EM_DASH = chr(0x2013), chr(0x2014)   # (by number, so that this file has neither)
DASHES = (EN_DASH.encode("utf-8"), EM_DASH.encode("utf-8"))
DASH_SKIP_DIRS = ("third_party/",)
DASH_ALLOWED = {"gpu/vk/menu_i18n.h", "gpu/vk/menu_i18n_inhale.h", "gpu/vk/vk_menu.cpp"}


def tracked():
    out = subprocess.run(["git", "ls-files", "-z"], cwd=ROOT, stdout=subprocess.PIPE, check=True).stdout
    return [p for p in out.decode("utf-8").split("\0") if p]


def game_files(paths):
    return sorted(p for p in paths if os.path.splitext(p)[1].lower() in GAME_TYPES)


def dash_lines(data):
    """(line number, the line) for each line of a UTF-8 text with a dash; none for a binary file"""
    if not any(d in data for d in DASHES):
        return []
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        return []
    return [(n, line) for n, line in enumerate(text.splitlines(), 1) if EN_DASH in line or EM_DASH in line]


def main():
    # the rules themselves
    assert game_files(["a/b.NUP", "c.py", "romfs/x.bfsha", "d.cmp", "e.webm"]) == ["a/b.NUP", "d.cmp", "e.webm", "romfs/x.bfsha"]
    assert dash_lines(("a\nb %s c\n" % EM_DASH).encode("utf-8")) == [(2, "b %s c" % EM_DASH)]
    assert dash_lines(("1%s2\n" % EN_DASH).encode("utf-8")) == [(1, "1%s2" % EN_DASH)]
    assert dash_lines(b"a - b\n") == []
    assert dash_lines(b"\xff" + DASHES[1]) == []   # (not UTF-8: a binary file)

    paths = tracked()
    if not paths:
        sys.exit("hygiene: git lists no tracked files (not a clone, or nothing added yet)")
    bad = ["%s: a game file's type is tracked" % p for p in game_files(paths)]
    for p in paths:
        if p.startswith(DASH_SKIP_DIRS) or p in DASH_ALLOWED:
            continue
        full = os.path.join(ROOT, p)
        if not os.path.isfile(full):   # (deleted in the work tree, or a link)
            continue
        with open(full, "rb") as f:
            data = f.read()
        for n, line in dash_lines(data):
            bad.append("%s:%d: en or em dash: %s" % (p, n, line.strip()[:100]))
    if bad:
        sys.exit("hygiene:\n  " + "\n  ".join(bad))
    print("hygiene: %d tracked files, no game file types, no en or em dashes" % len(paths))


if __name__ == "__main__":
    main()
