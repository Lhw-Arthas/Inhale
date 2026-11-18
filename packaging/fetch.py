"""The release packages' downloads, by packaging/pins.txt: each fetched once into the cache, checked by its SHA-256 on every
use, and unpacked where a script asks.

    python3 -I packaging/fetch.py path <name> <os>              the checked download's path (fetched when missing)
    python3 -I packaging/fetch.py version <name> <os>           its version, as pins.txt gives it
    python3 -I packaging/fetch.py unpack <name> <os> <folder> [--strip N]
                                                                its files into <folder> (a .tar.* or .zip), the first N
                                                                folders of each path dropped

os: linux or windows; a line for "any" serves both. The cache is $INHALE_PKG_DL, else work/pkg/dl. Runs on the build
image's Python (3.10) as well as on the bundled one: the standard library only.
"""
import hashlib
import os
import shutil
import sys
import tarfile
import time
import urllib.request
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
PINS = os.path.join(HERE, "pins.txt")
CACHE = os.environ.get("INHALE_PKG_DL") or os.path.join(os.path.dirname(HERE), "work", "pkg", "dl")


def read_pins(path=PINS):
    """[(name, version, os, url, sha256)] in the file's order"""
    pins = []
    with open(path, encoding="utf-8") as f:
        for n, line in enumerate(f, 1):
            line = line.split("#", 1)[0].strip()
            if not line:
                continue
            words = line.split()
            if len(words) != 5:
                raise SystemExit("%s:%d: expected <name> <version> <os> <url> <sha256>, got %r" % (path, n, line))
            pins.append(tuple(words))
    return pins


def pin(name, system, pins=None):
    found = [p for p in (pins or read_pins()) if p[0] == name and p[2] in (system, "any")]
    if len(found) != 1:
        raise SystemExit("pins.txt: %d lines for %s on %s (expected one)" % (len(found), name, system))
    return found[0]


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def download(url, out):
    """url to out, retried: a GitHub release link answers 5xx now and then"""
    for attempt in range(5):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "inhale-packaging"})
            with urllib.request.urlopen(req, timeout=120) as r, open(out + ".part", "wb") as f:
                shutil.copyfileobj(r, f, 1 << 20)
            os.replace(out + ".part", out)
            return
        except OSError as e:
            print("fetch: %s: %s (attempt %d of 5)" % (url, e, attempt + 1), file=sys.stderr, flush=True)
            time.sleep(5 * (attempt + 1))
    raise SystemExit("fetch: %s could not be downloaded" % url)


def path(name, system):
    _, version, _, url, want = pin(name, system)
    os.makedirs(CACHE, exist_ok=True)
    out = os.path.join(CACHE, "%s-%s-%s" % (want[:12], name, os.path.basename(url).replace("%2B", "+")))
    if not os.path.isfile(out):
        print("fetch: %s %s from %s" % (name, version, url), file=sys.stderr, flush=True)
        download(url, out)
    got = sha256(out)
    if got != want:
        os.remove(out)
        raise SystemExit("fetch: %s is not the pinned file (SHA-256 %s, pins.txt has %s)" % (url, got, want))
    return out


def unpack(name, system, dest, strip=0):
    src = path(name, system)
    os.makedirs(dest, exist_ok=True)
    root = os.path.realpath(dest)

    def target(member):
        parts = [p for p in member.replace("\\", "/").split("/") if p and p != "."][strip:]
        if not parts:
            return None
        out = os.path.realpath(os.path.join(dest, *parts))
        if out != root and not out.startswith(root + os.sep):
            raise SystemExit("fetch: %s: %s points outside the folder" % (src, member))
        return out

    if src.endswith(".zip"):
        with zipfile.ZipFile(src) as z:
            for info in z.infolist():
                out = target(info.filename)
                if out is None or info.is_dir():
                    continue
                os.makedirs(os.path.dirname(out), exist_ok=True)
                with z.open(info) as r, open(out, "wb") as w:
                    shutil.copyfileobj(r, w)
                mode = info.external_attr >> 16
                if mode & 0o111:
                    os.chmod(out, 0o755)
        return
    with tarfile.open(src) as t:
        for m in t.getmembers():
            out = target(m.name)
            if out is None:
                continue
            if m.isdir():
                os.makedirs(out, exist_ok=True)
            elif m.issym():
                if os.path.isabs(m.linkname) or not os.path.realpath(
                        os.path.join(os.path.dirname(out), m.linkname)).startswith(root + os.sep):
                    raise SystemExit("fetch: %s: the link %s leaves the folder" % (src, m.name))
                os.makedirs(os.path.dirname(out), exist_ok=True)
                if os.path.lexists(out):
                    os.remove(out)
                os.symlink(m.linkname, out)
            elif m.islnk():
                link = target(m.linkname)
                os.makedirs(os.path.dirname(out), exist_ok=True)
                shutil.copyfile(link, out)
                os.chmod(out, m.mode & 0o755)
            elif m.isfile():
                os.makedirs(os.path.dirname(out), exist_ok=True)
                with t.extractfile(m) as r, open(out, "wb") as w:
                    shutil.copyfileobj(r, w, 1 << 20)
                os.chmod(out, m.mode & 0o755)


def main(argv):
    if len(argv) >= 3 and argv[0] == "path":
        print(path(argv[1], argv[2]))
    elif len(argv) >= 3 and argv[0] == "version":
        print(pin(argv[1], argv[2])[1])
    elif len(argv) >= 4 and argv[0] == "unpack":
        strip = int(argv[argv.index("--strip") + 1]) if "--strip" in argv else 0
        unpack(argv[1], argv[2], argv[3], strip)
    else:
        raise SystemExit(__doc__)


if __name__ == "__main__":
    main(sys.argv[1:])
