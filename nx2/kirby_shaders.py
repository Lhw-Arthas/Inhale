"""Every shader program of the game, for the precompile before the first start (Kirby and the Forgotten Land, Switch 2 Edition).

    python -I nx2/kirby_shaders.py <data romfs> --exefs <exefs> --image <image.bin> --out <inhale_shaders.bin>

The list nx2/shader_census.py makes for upstream's game, from where this game keeps its shaders. Its code title's romfs is empty, and
its files are a data title of their own (aoc/<title id>/romfs, make_game.py data_romfs). Each .cmp there is a u32 size, then an LZ4
frame (kirby_prompts.py unwrap). The stages are found in:

    gfx/**/*.bfres.cmp      the models: their materials' shaders, a BNSH each (about 44500 programs)
    ptcl/**/*.ptcl.cmp      the particle sets, BNSHs inside (about 8600)
    lyt/**/*.arc.cmp        the layouts: SARCs, a BNSH in some of their files (about 1000)
    shader/**/*.bfsha       the screen passes: an FSHA, a BNSH inside (46)
    ndsr/*.ndsr             a network (NDSR) in another layout than upstream's: ndsr_programs below (3 graphics, 30 compute)
    image.bin               the executable's own three BNSHs: the layouts' common programs (58), which no file holds

Each BNSH, wherever it is, is read by shader_census.py's walk (bnsh_all): the layout is the same as upstream's game's, a control
section (magic 34 12 76 98, 0xd8 bytes) and the code area it sizes, one program a variation (slot 8 vertex, slot 40 fragment, slot
48 compute). The output is shader_census.py's HKSEED01, which gpu/vk/vk_shader.cpp seed_open reads; nothing here goes into the
repository: the file is made from the player's own game.

Only for main's build 395fc326 (as kirby_far.py): another build is left out, and says so.
"""
import argparse
import collections
import os
import re
import struct
import sys
import time
if os.path.dirname(os.path.abspath(__file__)) not in sys.path:   # (python -I leaves the script folder off)
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import shader_census  # noqa: E402

BUILD_ID = "395fc326c2e5b1651d937074f8cfd75de63184d9"
READS = ("gfx", "lyt", "ptcl", "shader", "ndsr")   # (the data romfs's folders it walks: make_game.py CENSUS_READS too)
LZ4 = b"\x04\x22\x4d\x18"
SUFFIXES = (".bfres.cmp", ".ptcl.cmp", ".arc.cmp", ".bfsha", ".ndsr")


def build_id(exefs):
    """main's module id (an NSO header's +0x40, plain or compressed: the same; 32 bytes, the build id's 20 and zeros)"""
    with open(os.path.join(exefs, "main"), "rb") as f:
        head = f.read(0x60)
    return head[0x40:0x60].hex() if head[:4] == b"NSO0" else ""


def unwrap(data):
    """a .cmp's bytes (a u32 size, then an LZ4 frame), or the data as it is"""
    if data[4:8] != LZ4:
        return data
    import lz4.frame
    out = lz4.frame.decompress(data[4:])
    if len(out) != struct.unpack_from("<I", data)[0]:
        raise ValueError("a .cmp of %d bytes, its size says %d" % (len(out), struct.unpack_from("<I", data)[0]))
    return out


def blobs(data):
    """The data itself, or each file when it is a SARC (a file of it may be a .cmp too)"""
    if data[:4] == b"SARC":
        for inner in shader_census.sarc_files(data):
            yield from blobs(unwrap(inner))
    else:
        yield data


def ndsr_programs(data):
    """This game's NDSR: u16 +0x0e the item count, the items from +0x10 (upstream's: u32 +0x0c, from +0x14), each {u32 offset from
    the NDSR, u32 bytes << 4 | type}, typed as upstream's: 0 / 3 / 6 a vertex / fragment / compute control section, the item after
    each (1 / 4 / 7) its code; a vertex and the fragment after it are a program, a compute stage is one alone"""
    n = struct.unpack_from("<H", data, 0x0e)[0]
    if 0x10 + 8 * n > len(data):
        raise ValueError("NDSR of %d items in %d bytes" % (n, len(data)))
    items = [struct.unpack_from("<II", data, 0x10 + 8 * i) for i in range(n)]
    graphics = []
    for (c, ct), (x, xt) in zip(items, items[1:]):
        if ct & 15 not in (0, 3, 6) or xt & 15 != (ct & 15) + 1:
            continue
        control, end = shader_census.control_at(data, c)
        if control is None or x + end > len(data):
            continue
        s = shader_census.stage(control, data[x:x + end])
        if ct & 15 == 6:
            yield [s]
        elif ct & 15 == 0:
            if graphics:
                yield graphics
            graphics = [s]
        elif graphics:
            graphics.append(s)
    if graphics:
        yield graphics


def programs_in(data, stats):
    if data[:4] == b"NDSR":
        return ndsr_programs(data)
    return shader_census.bnsh_all(data, stats)


def files(romfs):
    """The files that hold shaders (READS, SUFFIXES), in a fixed order"""
    for folder in READS:
        for top, dirs, names in os.walk(os.path.join(romfs, folder)):
            dirs.sort()
            for name in sorted(names):
                if name.endswith(SUFFIXES):
                    yield os.path.join(top, name)


class Census:
    """Stages each once (by the control section and the code area it sizes: what the back end keys by), programs each once"""

    def __init__(self):
        self.stage_index, self.stages, self.programs, self.seen = {}, [], [], set()

    def add(self, stages):
        ids = []
        for st, control, code in stages:
            end = struct.unpack_from("<I", control, 0x44)[0]
            control, code = bytes(control[:0xd8]), bytes(code[:end] if end <= len(code) else code)
            key = control + code
            if key not in self.stage_index:
                self.stage_index[key] = len(self.stages)
                self.stages.append((st, control, code))
            ids.append(self.stage_index[key])
        ids = tuple(sorted(set(ids)))
        if ids in self.seen:
            return 0
        self.seen.add(ids)
        self.programs.append(ids)
        return 1

    def walk(self, name, data, stats):
        """The programs of one file's bytes, counted under name; a container this does not read is told and skipped"""
        made = 0
        for k, blob in enumerate(blobs(data)):
            try:
                for stages in programs_in(blob, stats):
                    made += self.add(stages)
            except (ValueError, struct.error) as e:
                print("%s: container %d skipped: %s" % (name, k, e), flush=True)
        return made

    def write(self, out):
        """shader_census.py's HKSEED01 (its docstring)"""
        import hashlib
        with open(out + ".part", "wb") as f:
            f.write(b"HKSEED01" + struct.pack("<II", len(self.programs), len(self.stages)))
            for st, control, code in self.stages:
                key = int.from_bytes(hashlib.sha1(control + code, usedforsecurity=False).digest()[:8], "little")
                f.write(struct.pack("<QIII", key, st, len(control), len(code)) + control + code)
            for ids in self.programs:
                f.write(struct.pack("<I%dI" % len(ids), len(ids), *ids))
        os.replace(out + ".part", out)   # (a stopped build leaves no half list for the game to read)


def census(romfs, image=None):
    """The Census of a data romfs (and the executable's image), and its counts by kind"""
    c, stats, made = Census(), collections.Counter(), collections.Counter()
    for path in files(romfs):
        with open(path, "rb") as f:
            data = f.read()
        try:
            data = unwrap(data)
        except (ValueError, RuntimeError) as e:   # (lz4.frame's errors are RuntimeError)
            print("%s skipped: %s" % (os.path.relpath(path, romfs), e), flush=True)
            continue
        made[next(s for s in SUFFIXES if path.endswith(s)).split(".")[1]] +=c.walk(os.path.relpath(path, romfs), data, stats)
    if image:
        with open(image, "rb") as f:
            made["image"] += c.walk("image.bin", f.read(), stats)
    return c, made, stats


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("romfs")
    p.add_argument("--exefs", required=True)
    p.add_argument("--image")
    p.add_argument("--out")
    a = p.parse_args(argv)
    bid = build_id(a.exefs)
    if not bid.startswith(BUILD_ID):
        print("shaders: build %s, not %s: no shader list" % (bid[:8] or "unknown", BUILD_ID[:8]), flush=True)
        return 1
    started = time.time()
    c, made, stats = census(a.romfs, a.image)
    for k, n in sorted(made.items()):
        print("%-8s %6d programs" % (k, n))
    print("%d programs from %d stages, %.0f s" % (len(c.programs), len(c.stages), time.time() - started))
    print("slots:", sorted(stats.items()))
    if a.out:
        c.write(a.out)
        print("wrote", a.out, os.path.getsize(a.out) >> 20, "MB")
    return 0


if __name__ == "__main__":
    sys.exit(main())
