"""Game-free test of nx2/kirby_shaders.py: the programs it finds in made-up files where this game keeps its shaders (a model's
.bfres.cmp, a layout's SARC, a .bfsha, this game's NDSR, the executable's image), each stage paired with its program's other stage,
the list as gpu/vk/vk_shader.cpp seed_open reads it, the gate on main's build id, and make_game.py's calls.

    python -I nx2/test_kirby_shaders.py
"""
import os
import struct
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))   # (python -I leaves the script folder off)
import kirby_shaders  # noqa: E402

CONTROL = 0xd8


def control(stage, end, salt=0):
    c = bytearray(CONTROL)
    c[0:4] = b"\x34\x12\x76\x98"
    struct.pack_into("<I", c, 0x38, end)   # (the code's length)
    struct.pack_into("<II", c, 0x40, end, end)   # (the constants' offset, the code area's end)
    struct.pack_into("<H", c, 0x56, stage)
    c[0x20] = salt   # (where a real control section has its hash)
    return bytes(c)


def code(seed, end):
    return bytes((seed * 7 + i) & 0xff for i in range(end))


def bnsh(programs):
    """A BNSH whose variations are the programs, each [(slot, stage, seed)]: the layout shader_census.py bnsh_programs reads"""
    count = len(programs)
    variations = 0x100
    progs = variations + 64 * count
    records = progs + 80 * count
    stages = [s for p in programs for s in p]
    blobs = records + 32 * len(stages)
    data = bytearray(blobs + len(stages) * (CONTROL + 0x100))
    data[0:4] = b"BNSH"
    data[12:14] = b"\xff\xfe"
    data[96:100] = b"grsc"
    struct.pack_into("<IQ", data, 124, count, variations)
    k = 0
    for i, p in enumerate(programs):
        struct.pack_into("<Q", data, variations + 64 * i + 16, progs + 80 * i)
        for slot, stage, seed in p:
            rec, ctl = records + 32 * k, blobs + (CONTROL + 0x100) * k
            struct.pack_into("<Q", data, progs + 80 * i + slot, rec)
            struct.pack_into("<QQII", data, rec + 8, ctl, ctl + CONTROL, 0x100, CONTROL)
            data[ctl:ctl + CONTROL] = control(stage, 0x100, seed)
            data[ctl + CONTROL:ctl + CONTROL + 0x100] = code(seed, 0x100)
            k += 1
    struct.pack_into("<I", data, 28, len(data))
    return bytes(data)


def cmp(data):
    import lz4.frame
    return struct.pack("<I", len(data)) + lz4.frame.compress(data)


def sarc(files):
    """A SARC of the files' bytes (the header shader_census.py sarc_files reads)"""
    start = 0x20 + 16 * len(files)
    head = bytearray(start)
    head[0:4] = b"SARC"
    struct.pack_into("<I", head, 0x0c, start)
    struct.pack_into("<H", head, 0x1a, len(files))
    body, at = b"", 0
    for k, f in enumerate(files):
        struct.pack_into("<IIII", head, 0x20 + 16 * k, 0, 0, at, at + len(f))
        body += f
        at += len(f)
    return bytes(head) + body


def ndsr():
    """This game's NDSR: u16 +0x0e the item count, the items from +0x10; a vertex and fragment program, then a compute one, and
    an item of another type between them"""
    items = [(0x400, 0), (0x500, 1), (0x600, 3), (0x700, 4), (0x0, 9), (0x800, 6), (0x900, 7)]
    data = bytearray(0xa00)
    data[0:4] = b"NDSR"
    struct.pack_into("<H", data, 0x0e, len(items))
    for i, (off, t) in enumerate(items):
        struct.pack_into("<II", data, 0x10 + 8 * i, off, (CONTROL if t in (0, 3, 6) else 0x100) << 4 | t)
    for off, stage, seed in ((0x400, 0, 40), (0x600, 1, 41), (0x800, 5, 42)):
        data[off:off + CONTROL] = control(stage, 0x100, seed)
        data[off + 0x100:off + 0x200] = code(seed, 0x100)
    return bytes(data)


VS_FS = [(8, 0, 1), (40, 1, 2)]   # (one program: a vertex stage in slot 8, a fragment stage in slot 40)


def romfs(d):
    """A data romfs: a model (two programs, one of them the bfsha's too), a layout SARC with a compressed file, a .bfsha, the
    NDSR, and a stream that holds a BNSH but is not a file the census reads"""
    files = {
        "gfx/Actor/a.bfres.cmp": cmp(b"FRES" + bytes(60) + bnsh([VS_FS, [(8, 0, 3), (40, 1, 4)]])),
        "lyt/Menu/Parts.arc.cmp": cmp(sarc([b"timg", cmp(bnsh([[(8, 0, 5), (40, 1, 6)]]))])),
        "shader/Copy/Copy.bfsha": b"FSHA" + bytes(0xffc) + bnsh([VS_FS, [(48, 5, 7)]]),
        "ndsr/lower_left.ndsr": ndsr(),
        "snd/a.bfstm": bnsh([[(8, 0, 8), (40, 1, 9)]]),
    }
    for name, data in files.items():
        os.makedirs(os.path.dirname(os.path.join(d, name)), exist_ok=True)
        with open(os.path.join(d, name), "wb") as f:
            f.write(data)
    image = os.path.join(d, "image.bin")
    with open(image, "wb") as f:
        f.write(bytes(0x1000) + bnsh([[(8, 0, 10), (40, 1, 11)]]) + bytes(0x100))
    return image


def exefs(d, build):
    os.makedirs(d)
    with open(os.path.join(d, "main"), "wb") as f:
        f.write(b"NSO0" + bytes(0x3c) + bytes.fromhex(build).ljust(0x20, b"\0") + bytes(0x100))
    return d


def read_seed(path):
    """HKSEED01 as seed_open reads it: [(stage, control, code)], [[stage index]]"""
    with open(path, "rb") as f:
        b = f.read()
    assert b[:8] == b"HKSEED01"
    nprog, nst = struct.unpack_from("<II", b, 8)
    at, stages, programs = 16, [], []
    for _ in range(nst):
        _, st, cs, bs = struct.unpack_from("<QIII", b, at)
        stages.append((st, b[at + 20:at + 20 + cs], b[at + 20 + cs:at + 20 + cs + bs]))
        at += 20 + cs + bs
    for _ in range(nprog):
        n = struct.unpack_from("<I", b, at)[0]
        programs.append(list(struct.unpack_from("<%dI" % n, b, at + 4)))
        at += 4 + 4 * n
    assert at == len(b)
    return stages, programs


class KirbyShadersTests(unittest.TestCase):
    def test_the_programs_of_every_file_it_reads(self):
        with tempfile.TemporaryDirectory() as d:
            c, made, _ = kirby_shaders.census(d, romfs(d))
        # (the bfsha's vertex and fragment program is the model's first: one program; the bfstm is not read)
        self.assertEqual(dict(made), {"bfres": 2, "arc": 1, "bfsha": 1, "ndsr": 2, "image": 1})
        self.assertEqual(len(c.programs), 7)
        seeds = sorted(tuple(sorted((c.stages[i][0], c.stages[i][1][0x20]) for i in p)) for p in c.programs)
        self.assertEqual(seeds, [((0, 1), (1, 2)), ((0, 3), (1, 4)), ((0, 5), (1, 6)), ((0, 10), (1, 11)), ((0, 40), (1, 41)),
                                 ((5, 7),), ((5, 42),)])

    def test_each_stage_is_the_bytes_the_game_hands_the_gpu(self):
        with tempfile.TemporaryDirectory() as d:
            c, _, _ = kirby_shaders.census(d, romfs(d))
        for st, ctl, cd in c.stages:
            self.assertEqual(len(ctl), CONTROL)
            self.assertEqual(ctl[:4], b"\x34\x12\x76\x98")
            self.assertEqual(st, struct.unpack_from("<H", ctl, 0x56)[0])
            self.assertEqual(cd, code(ctl[0x20], 0x100))

    def test_the_list_reads_back_and_the_gate_holds(self):
        with tempfile.TemporaryDirectory() as d:
            image = romfs(d)
            out = os.path.join(d, "inhale_shaders.bin")
            other = exefs(os.path.join(d, "other"), "0123456789abcdef0123456789abcdef01234567")
            self.assertEqual(kirby_shaders.main([d, "--exefs", other, "--image", image, "--out", out]), 1)
            self.assertFalse(os.path.exists(out))
            this = exefs(os.path.join(d, "this"), kirby_shaders.BUILD_ID)
            self.assertEqual(kirby_shaders.main([d, "--exefs", this, "--image", image, "--out", out]), 0)
            stages, programs = read_seed(out)
            self.assertFalse(os.path.exists(out + ".part"))
        self.assertEqual(len(programs), 7)
        self.assertEqual(len(stages), 12)
        for p in programs:
            kinds = sorted(stages[i][0] for i in p)
            self.assertIn(kinds, ([0, 1], [5]))

    def test_make_game_runs_it_and_keys_on_what_it_reads(self):
        import importlib.util
        here = os.path.dirname(os.path.abspath(__file__))
        spec = importlib.util.spec_from_file_location("make_game_under_test", os.path.join(here, "make_game.py"))
        make_game = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(make_game)
        for top in kirby_shaders.READS:
            self.assertIn(top, make_game.CENSUS_READS)
        cmd = make_game.kirby_shaders_cmd("r", "e", "i.bin", "o.bin")
        self.assertEqual(cmd[:5], make_game.PY)
        self.assertTrue(cmd[5].endswith("kirby_shaders.py"))
        self.assertEqual(cmd[6:], [make_game.long_path("r"), "--exefs", "e", "--image", "i.bin", "--out", "o.bin"])
        with open(os.path.join(here, "make_game.py"), encoding="utf-8") as f:
            body = f.read()
        main = body[body.index("def main("):]
        self.assertIn("census_romfs = data_romfs(romfs, aoc)", main)
        self.assertIn("kirby_shaders_cmd(census_romfs, exefs, ", main)
        self.assertIn("shader_list_current(work, census_romfs, ", main)
        self.assertIn("note_shader_list(work, census_romfs, ", main)
        with tempfile.TemporaryDirectory() as d:   # (a change to this census makes the list again)
            for n in ("shader_census.py", "kirby_shaders.py"):
                with open(os.path.join(here, n), "rb") as f, open(os.path.join(d, n), "wb") as g:
                    g.write(f.read())
            make_game.HERE = d
            key = make_game.shader_list_key(d)
            with open(os.path.join(d, "kirby_shaders.py"), "ab") as g:
                g.write(b"# another census\n")
            self.assertNotEqual(key, make_game.shader_list_key(d))


if __name__ == "__main__":
    unittest.main()
