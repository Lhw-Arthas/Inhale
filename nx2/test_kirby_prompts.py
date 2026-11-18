"""Game-free test of nx2/kirby_prompts.py: the .cmp wrapper, a BC5 label written and read back, the SARC lookup, and that a
face's redraw changes the labels' blocks and nothing else.

    python -I nx2/test_kirby_prompts.py      (Pillow, numpy, lz4, texture2ddecoder, fontTools)
"""
import os
import struct
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))   # (python -I leaves the script folder off)
import kirby_prompts as kp

try:
    import lz4.frame   # noqa: F401
    import numpy   # noqa: F401
    import texture2ddecoder   # noqa: F401
    from PIL import Image, ImageDraw
    HAVE = True
except ImportError:
    Image = ImageDraw = None
    HAVE = False

W = H = 128


def bntx(names):
    """a minimal BNTX holding these 128x128 BC5 textures, block-linear with 16 GOBs high blocks: the fields prompt_assets
    .bntx_textures reads"""
    size = 0x200000
    b = bytearray(size)
    struct.pack_into("<I", b, 0x24, len(names))
    struct.pack_into("<Q", b, 0x28, 0x100)
    data = 0x10000
    for i, name in enumerate(names):
        brti, nm, mips = 0x8000 + 0x200 * i, 0x4000 + 0x40 * i, 0x6000 + 0x10 * i
        struct.pack_into("<Q", b, 0x100 + 8 * i, brti)
        struct.pack_into("<Q", b, brti + 0x60, nm)
        struct.pack_into("<H", b, nm, len(name))
        b[nm + 2:nm + 2 + len(name)] = name.encode()
        struct.pack_into("<I", b, brti + 0x1C, kp.BC5 << 8 | 1)
        struct.pack_into("<II", b, brti + 0x24, W, H)
        struct.pack_into("<I", b, brti + 0x34, 4)   # (16 GOBs)
        struct.pack_into("<Q", b, brti + 0x70, mips)
        struct.pack_into("<Q", b, mips, data + i * 0x20000)
    return b


def sarc(name, payload):
    """a SARC of one file at the data offset 0x60"""
    b = bytearray(0x60)
    b[0:4] = b"SARC"
    struct.pack_into("<HHII", b, 4, 0x14, 0xFEFF, 0x60 + len(payload), 0x60)
    b[0x14:0x18] = b"SFAT"
    struct.pack_into("<HHI", b, 0x18, 0xC, 1, 0x65)
    struct.pack_into("<IIII", b, 0x20, 0, 0x01000000, 0, len(payload))
    b[0x30:0x34] = b"SFNT"
    struct.pack_into("<HH", b, 0x34, 8, 0)
    b[0x38:0x38 + len(name) + 1] = name.encode() + b"\0"
    return bytes(b) + payload


@unittest.skipUnless(HAVE, "needs the build's Python packages")
class LabelTests(unittest.TestCase):
    def test_cmp_round_trip_and_size(self):
        data = os.urandom(300) + bytes(200000) + os.urandom(100)
        blob = kp.wrap(data)
        self.assertEqual(struct.unpack_from("<I", blob)[0], len(data))
        self.assertEqual(blob[4:8], b"\x04\x22\x4d\x18")   # (the LZ4 frame's magic)
        self.assertEqual(kp.unwrap(blob), data)

    def test_stored_cmp_round_trips_and_places_bytes(self):
        data = os.urandom(150000)
        blob = kp.wrap(data, True)
        self.assertEqual(kp.unwrap(blob), data)
        for d in (0, 65535, 65536, 149999):   # (where host/prompts.c finds data's byte d: kp.STORED_HEAD, a block's 4 bytes)
            at = kp.STORED_HEAD + (d >> 16) * (kp.BLOCK + 4) + 4 + (d & 0xFFFF)
            self.assertEqual(blob[at], data[d])

    def test_cmp_size_mismatch_stops(self):
        blob = bytearray(kp.wrap(b"x" * 100))
        blob[0] = 99
        with self.assertRaises(SystemExit):
            kp.unwrap(bytes(blob))

    def test_sarc_file_finds_its_bytes(self):
        arc = sarc(kp.BNTX, b"payload")
        s, e = kp.sarc_file(arc, kp.BNTX)
        self.assertEqual(arc[s:e], b"payload")
        with self.assertRaises(SystemExit):
            kp.sarc_file(arc, "nothing")

    def test_bc5_label_reads_back_and_the_other_texture_stays(self):
        b = bntx(["one^t", "two^t"])
        tex = kp.pa.bntx_textures(b)
        before = bytes(b[0x10000 + 0x20000:0x10000 + 0x40000])
        red, green = Image.new("L", (W, H), 255), Image.new("L", (W, H), 0)
        ImageDraw.Draw(green).ellipse((24, 24, 104, 104), fill=255)
        ImageDraw.Draw(red).ellipse((24, 24, 104, 104), fill=0)
        kp.encode(b, tex["one^t"], red, green)
        self.assertEqual(bytes(b[0x10000 + 0x20000:0x10000 + 0x40000]), before)   # (the second texture's blocks)
        r2, g2 = kp.decode(b, tex["one^t"])
        for got, want in ((r2, red), (g2, green)):
            diff = sum(abs(x - y) for x, y in zip(got.tobytes(), want.tobytes())) / (W * H)
            self.assertLess(diff, 2)   # (a flat ellipse: BC4 holds it to a level or two at the rim)

    def test_redraw_changes_only_the_label_blocks(self):
        names = list(kp.LABELS) + ["BtnIconBase^t"]
        b = bntx(names)
        tex = kp.pa.bntx_textures(b)
        green = Image.new("L", (W, H), 0)
        ImageDraw.Draw(green).ellipse((36, 36, 92, 92), outline=255, width=4)
        for name in names:
            kp.encode(b, tex[name], Image.new("L", (W, H), 255), green)
        arc = sarc(kp.BNTX, bytes(b))
        out, var = kp.redraw(arc, "xbox")
        self.assertEqual(len(out), len(arc))
        s, e = kp.sarc_file(arc, kp.BNTX)
        base = s + 0x10000 + 0x20000 * len(kp.LABELS)   # (BtnIconBase's blocks: not a label)
        changed = [i for i in range(len(arc)) if arc[i] != out[i]]
        self.assertTrue(changed)
        self.assertTrue(all(s + 0x10000 <= i < base for i in changed))
        nb = bytearray(out[s:e])
        r, g = kp.decode(nb, kp.pa.bntx_textures(nb)["BtnIconA^t"])
        box = g.point(lambda v: 255 if v > 127 else 0).getbbox()
        self.assertTrue(box and box[2] - box[0] > 40)   # (the new icon is drawn, about the old one's size)
        self.assertEqual(r.getpixel((0, 0)), 255)   # (R is 255 outside the label)

        self.check_variants(out, var, s)

    def check_variants(self, out, var, s):
        """the variants file: a table per label, the default selector's texture bytes the ones in the SARC, one place per blob"""
        self.assertEqual(var[:4], kp.VAR_MAGIC)
        n, nsel = struct.unpack_from("<II", var, 4)
        self.assertEqual((n, nsel), (len(kp.LABELS), len(kp.pa.PADS)))
        seen = set()
        for i in range(n):
            sw, off, span, tab, default = struct.unpack_from("<IIIII", var, 12 + 20 * i)
            seen.add((sw, off))
            at, = struct.unpack_from("<I", var, tab + 4 * default)
            self.assertEqual(var[at:at + span], out[off:off + span])
            for sel in range(nsel):
                at, = struct.unpack_from("<I", var, tab + 4 * sel)
                self.assertTrue(at == 0 or at + span <= len(var))
        self.assertEqual(len(seen), n)   # (each label's texture once)

    def test_keyboard_face_has_a_key_for_each_code(self):
        icons, sels, defaults = kp.face_icons("keyboard")
        self.assertEqual(set(sels), set(range(1, 256)))
        self.assertTrue(all(defaults[sw] in sels for sw in kp.pa.SW))
        self.assertNotEqual(icons.code[0x45], icons.code[0x46])   # (E and F)

    def test_font_cells_redrawn_and_the_rest_kept(self):
        """a BFFNT of one BC4 sheet (upside down, cells 123x118): the A and X buttons' cells (codes F000, F002) take the face's icon,
        the header stays and nothing else is drawn"""
        size = kp.FONT_BNTX + 0x1000 + 0x80000 + 0x1000
        font = bytearray(size)
        b = bytearray(0x1000 + 0x80000)
        b[0:4] = b"BNTX"
        struct.pack_into("<I", b, 0x24, 1)
        struct.pack_into("<Q", b, 0x28, 0x100)
        struct.pack_into("<Q", b, 0x100, 0x800)
        struct.pack_into("<Q", b, 0x800 + 0x60, 0x400)
        struct.pack_into("<H", b, 0x400, 1)
        b[0x402] = ord("0")
        struct.pack_into("<I", b, 0x800 + 0x1C, 0x1D01)
        struct.pack_into("<II", b, 0x800 + 0x24, 1024, 1024)
        struct.pack_into("<I", b, 0x800 + 0x34, 4)
        struct.pack_into("<Q", b, 0x800 + 0x70, 0x600)
        struct.pack_into("<Q", b, 0x600, 0x1000)
        tex = kp.pa.bntx_textures(bytes(b))["0"]
        sheet = Image.new("L", (1024, 1024), 0)
        for g in (2, 3):   # (cells 2 and 3: a ring each, in the flipped sheet)
            x, y = g % 8 * 123, g // 8 * 118
            ImageDraw.Draw(sheet).ellipse((x + 10, y + 10, x + 100, y + 100), outline=255, width=8)
        for off, data in kp.pa.runs(tex, sheet.transpose(Image.FLIP_TOP_BOTTOM)):
            b[off:off + len(data)] = data
        font[kp.FONT_BNTX:kp.FONT_BNTX + len(b)] = b
        cmap = b"CMAP" + struct.pack("<I", 0x28) + struct.pack("<IIHHI", 0, 0xFFFF, 2, 0, 0) + struct.pack("<I", 2)
        cmap += struct.pack("<IIII", 0xF000, 2, 0xF002, 3)
        font[0x100:0x100 + len(cmap)] = cmap
        self.assertEqual(kp.font_cells(bytes(font)), {0xF000: 2, 0xF002: 3})
        out, var = kp.redraw_font(bytes(font), "xbox")
        self.assertEqual(len(out), len(font))
        self.assertEqual(out[:kp.FONT_BNTX], bytes(font[:kp.FONT_BNTX]))   # (the header: as it was)
        nb = out[kp.FONT_BNTX:]
        from PIL import ImageOps
        got = ImageOps.flip(kp.pa.decode(nb, kp.pa.bntx_textures(nb)["0"]))
        x, y = 2 * 123, 0
        self.assertNotEqual(got.crop((x, y, x + 123, y + 118)).tobytes(), sheet.crop((x, y, x + 123, y + 118)).tobytes())   # (A: drawn)
        self.assertEqual(var[:4], kp.VAR_MAGIC)
        self.assertEqual(struct.unpack_from("<II", var, 4), (2, len(kp.pa.PADS)))   # (a cell each for A and X)
        sw, off, span, tab, default = struct.unpack_from("<IIIII", var, 12)
        self.assertEqual((off & 0xFFFF, off >> 16), (2 * 123 // 4, (1024 - 118) // 4))   # (cell 2's first block, in the sheet as stored)
        at, = struct.unpack_from("<I", var, tab + 4 * default)
        self.assertTrue(at and (span & 0xFFFF) * (span >> 16) * 8 + at <= len(var))
        self.assertEqual(got.crop((4 * 123, 0, 1024, 118)).getbbox(), None)   # (nothing past the two cells)


if __name__ == "__main__":
    unittest.main()