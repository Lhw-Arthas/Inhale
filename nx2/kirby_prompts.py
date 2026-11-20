"""Kirby's button icons redrawn for a controller face (the Xbox, PlayStation or Steam Deck labels instead of the Switch's).

The game draws its on-screen button prompts (lyt/Cmn/BtnIcon) from one label texture per Switch button, BtnIconA^t and so on,
in the SARC lyt/Cmn/BtnIcon/Parts.arc.cmp (a u32 size, then an LZ4 frame) in its timg/__Combined.bntx: 128x128 BC5 (192x192 for
the Large ones), R the label's silhouette seen from outside (255 outside, 0 over the whole label, its letter too), G its ink.
This writes the face's icon of the pad input a Switch button is bound to (nx2/prompt_faces.py, the default controls: nx2/
prompt_assets.py DEFAULT) over each of those, in the same place and size, so the SARC's size does not change.

    python -I nx2/kirby_prompts.py <romfs> <face> <out folder> [--dump <folder>]

writes <out>/<archive> for each of ARCHIVES the romfs holds, its variants beside it (.var for .cmp), and the text font's (--dump:
the labels, before and after, as PNG; in a folder per face for "all"). The face "all" writes each one's into <out>/<face>/, as
the game reads them (host/prompts.c: <game folder>/prompts/<face>/). It needs nx2/prompt_requirements.txt's packages.

Not lyt/Cmn/BtnIcon alone: four more archives hold a copy of BtnIconA^t of their own (the same bytes), which their layouts find
before the common one's, so each is redrawn too (issue #14: the world map's DLC stage bubble showed the Switch's A).
"""
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))   # (python -I leaves the script folder off)
import prompt_assets as pa

PARTS = "lyt/Cmn/BtnIcon/Parts.arc.cmp"
# every archive holding a label (the others: BtnIconA^t only), the common one first; host/prompts.c icon_archives serves them
ARCHIVES = [PARTS, "lyt/Wmap/MarkerDlcStage/Body.arc.cmp", "lyt/Arena/Entry/Parts.arc.cmp", "lyt/Cmn/HeroPanel/Parts.arc.cmp",
            "lyt/MgameBall/Game/Parts.arc.cmp"]
BNTX = "timg/__Combined.bntx"
# the label textures this redraws and the Switch button (prompt_assets.SW) each shows. Not here: the Joy-Con's SL and SR, the
# sticks and the plus-shaped d-pad: no pad input has an icon for them
LABELS = {"BtnIconA^t": "a", "BtnIconB^t": "b", "BtnIconX^t": "x", "BtnIconY^t": "y", "BtnIconL^t": "l", "BtnIconR^t": "r",
          "BtnIconZL^t": "zl", "BtnIconZR^t": "zr", "BtnIconPlus^t": "plus", "BtnIconMinus^t": "minus",
          "BtnIconLargeA^t": "a", "BtnIconLargeB^t": "b", "BtnIconLargeX^t": "x", "BtnIconLargeY^t": "y"}
BC5 = 0x1E   # (a texture's format, from its high byte)
BLOCK = 65536
STORED_HEAD = 4 + 7   # (a stored .cmp: its size, then the frame's 7 header bytes; each block then has 4 more before its data)
VAR_MAGIC = b"KBIV"
# the inline text icons: the font the messages draw them from (an MSBT tag's U+F0xx), a BFFNT whose sheets are a BNTX at FONT_BNTX
# (1024x1024 BC4, upside down, cells FONT_PITCH (x, y) apart, 8 to a row), and the code points of the Switch buttons' icons in them
FONT = "font/Region/STD/Ext-Operation.bffnt.cmp"   # (not its -OLM sibling: that one is RGBA8, 7x7 cells of 139x134, other icons)
FONT_BNTX = 0x1000
FONT_PITCH = (123, 118)
FONT_CELLS = {0xF000: "a", 0xF001: "b", 0xF002: "x", 0xF003: "y", 0xF010: "a", 0xF011: "b", 0xF012: "x", 0xF013: "y",
              0xF020: "a", 0xF021: "b", 0xF022: "x", 0xF023: "y", 0xF060: "l", 0xF061: "r", 0xF062: "zl", 0xF063: "zr",
              0xF094: "plus", 0xF095: "minus"}
FACES = list(pa.FACES) + ["keyboard"]   # (host/prompts.c: HOS_PROMPT_*, after the Switch's)


def unwrap(blob):
    """a .cmp's bytes: its u32 size, then an LZ4 frame"""
    import lz4.frame
    n, = struct.unpack_from("<I", blob)
    data = lz4.frame.decompress(blob[4:])
    if len(data) != n:
        raise SystemExit(f"kirby_prompts: a .cmp of {len(data)} bytes, its size says {n}")
    return data


def wrap(data, stored=False):
    """the game's .cmp of these bytes: 64 KiB independent blocks, no checksum and no size in the frame, as its own. stored: every
    block as it is (LZ4's raw-block flag), so a byte of data is at a place the host can work out (STORED_HEAD, STORED_BLOCK) and
    write over, at the game's start, with the icons for the controls the player set (host/prompts.c)"""
    import lz4.frame
    frame = lz4.frame.compress(
        data if not stored else b"", block_size=lz4.frame.BLOCKSIZE_MAX64KB, block_linked=False, content_checksum=False,
        block_checksum=False, store_size=False, compression_level=lz4.frame.COMPRESSIONLEVEL_MAX)
    if stored:
        frame = frame[:STORED_HEAD - 4]   # (the magic, the two flag bytes and their checksum: the same whatever the data)
        for i in range(0, len(data), BLOCK):
            frame += struct.pack("<I", min(BLOCK, len(data) - i) | 0x80000000) + data[i:i + BLOCK]
        frame += bytes(4)   # (the end mark)
    return struct.pack("<I", len(data)) + frame


def sarc_file(u, name):
    """(start, end) of a file in a SARC"""
    _, _, _, data = struct.unpack_from("<HHII", u, 4)
    count, = struct.unpack_from("<H", u, 0x1A)
    names = 0x20 + 16 * count + 8
    for i in range(count):
        _, no, start, end = struct.unpack_from("<IIII", u, 0x20 + 16 * i)
        at = names + (no & 0xFFFFFF) * 4
        if u[at:u.index(b"\0", at)].decode() == name:
            return data + start, data + end
    raise SystemExit(f"kirby_prompts: no {name} in the archive")


def decode(b, t):
    """a BC5 texture as (R, G), two PIL L images"""
    import texture2ddecoder
    from PIL import Image
    _, fmt, w, h, gobs, data = t
    if fmt >> 8 != BC5:
        raise SystemExit(f"kirby_prompts: texture format {fmt:#x}, not BC5")
    bw, bh = (w + 3) // 4, (h + 3) // 4
    pitch = (bw * 16 + 63) // 64
    lin = b"".join(b[data + o:data + o + 16] for o in (pa.gob_offset(x * 16, y, gobs, pitch) for y in range(bh) for x in range(bw)))
    rgba = Image.frombytes("RGBA", (bw * 4, bh * 4), texture2ddecoder.decode_bc5(lin, bw * 4, bh * 4), "raw", "BGRA")
    return rgba.getchannel(0), rgba.getchannel(1)


def encode(b, t, red, green):
    """red and green (L images of the texture's size) written over its blocks, in b (a bytearray)"""
    import numpy as np
    _, _, w, h, gobs, data = t
    bw, bh = w // 4, h // 4
    pitch = (bw * 16 + 63) // 64
    blocks = np.concatenate([np.frombuffer(pa.encode_bc4(red), np.uint8).reshape(-1, 8),
                             np.frombuffer(pa.encode_bc4(green), np.uint8).reshape(-1, 8)], axis=1)
    for n, o in enumerate(pa.gob_offset(x * 16, y, gobs, pitch) for y in range(bh) for x in range(bw)):
        b[data + o:data + o + 16] = blocks[n].tobytes()


def redrawn(icons, pad, green):
    """a label's new (R, G): the pad input's icon, as large as the old ink's box and in its place"""
    from PIL import Image, ImageChops
    box = green.point(lambda v: 255 if v > 127 else 0).getbbox()
    w, h = green.size
    icon, shape, _ = icons.masks(pad, max(box[2] - box[0], box[3] - box[1]))
    at = ((box[0] + box[2] - icon.width) // 2, (box[1] + box[3] - icon.height) // 2)
    ink = Image.new("L", (w, h), 0)
    ink.paste(icon, at)
    body = Image.new("L", (w, h), 0)
    body.paste(shape, at)
    return ImageChops.invert(body), ink


class KeyIcons(pa.Icons):
    """the keyboard face's icon for each key code (a Windows virtual key, 1 to 255), Kenney's, a key it has none for as its "ANY" key"""

    def __init__(self):
        from fontTools.ttLib import TTFont
        import prompt_keys
        self.path = os.path.join(pa.KENNEY_KEYBOARD, prompt_keys.FONT)
        rev = {n: c for c, n in TTFont(self.path).getBestCmap().items()}
        self.code = {k: rev[prompt_keys.kenney_name(k)] for k in range(1, 256) if prompt_keys.kenney_name(k) in rev}


def face_icons(face):
    """(the face's icons, its selectors, the default one of each Switch button): a selector is what the controls choose by, the
    pad input's place in prompt_assets.PADS (HOS_PAD_*) or a key code; each maps to the key of icons.code"""
    if face == "keyboard":
        import prompt_keys
        icons = KeyIcons()
        return icons, {k: k for k in icons.code}, {sw: prompt_keys.DEFAULT[pa.SW[sw]] for sw in pa.SW}
    icons = pa.Icons(face, None)
    return (icons, {i: p for i, p in enumerate(pa.PADS) if p in icons.code},
            {sw: pa.PADS.index(pa.DEFAULT[pa.SW[sw]]) for sw in pa.SW})


def pack_var(entries, nsel):
    """the variants file's bytes (redraw's format) for entries of (Switch button, offset, length, default selector, {selector:
    bytes}); the texture bytes after the tables, each different one once"""
    head = 12 + 20 * len(entries)
    tables = head
    place = head + 4 * nsel * len(entries)   # (the texture bytes after the tables, each different one once)
    var, body, seen = bytearray(VAR_MAGIC + struct.pack("<II", len(entries), nsel)), bytearray(), {}
    tabs = bytearray()
    for sw, off, span, default, blobs in entries:
        var += struct.pack("<IIIII", pa.SW[sw], off, span, tables + len(tabs), default)
        for sel in range(nsel):
            blob = blobs.get(sel)
            if blob is None:
                tabs += bytes(4)
                continue
            if blob not in seen:
                seen[blob] = place + len(body)
                body += blob
            tabs += struct.pack("<I", seen[blob])
    return bytes(var + tabs + body)


def redraw(parts, face, dump=None):
    """(a Parts.arc.cmp's bytes (the SARC, unwrapped) with the face's icons in its labels, on the default controls; and the
    variants: each label's texture bytes with the icon of every selector, for host/prompts.c to write over the first for the
    controls the player set)

    the variants file (little-endian): "KBIV", u32 labels, u32 selectors (17 pad inputs, HOS_PAD_*; 256 key codes), then per label
    u32 Switch button (HOS_SW_*), its texture's offset in the SARC, its length, the place in this file of its table and its default
    selector; each table is a u32 place in this file for each selector, of that selector's texture bytes, 0 where it has none"""
    u = bytearray(parts)
    start, end = sarc_file(u, BNTX)
    b = bytearray(u[start:end])
    tex = pa.bntx_textures(b)
    icons, sels, defaults = face_icons(face)
    nsel = 256 if face == "keyboard" else len(pa.PADS)
    entries = []
    for name, sw in LABELS.items():
        default = defaults[sw]
        if default not in sels or name not in tex:   # (an archive other than the common one holds only some labels)
            continue
        t = tex[name]
        red, green = decode(b, t)
        _, _, w, h, gobs, data = t
        pitch = (w // 4 * 16 + 63) // 64
        span = max(pa.gob_offset(x * 16, y, gobs, pitch) for y in range(h // 4) for x in range(w // 4)) + 16
        blobs, by_icon = {}, {}   # (a selector's bytes; the keys that share an icon draw it once)
        for sel, key in sels.items():
            if icons.code[key] not in by_icon:
                new = redrawn(icons, key, green)
                scratch = bytearray(span)
                encode(scratch, t[:5] + (0,), *new)
                by_icon[icons.code[key]] = (bytes(scratch), new)
            blobs[sel] = by_icon[icons.code[key]]
        if dump:
            from PIL import Image
            both = Image.new("L", (red.width * 4, red.height))
            for i, im in enumerate((red, green) + blobs[default][1]):
                both.paste(im, (i * red.width, 0))
            both.save(os.path.join(dump, name[:-2] + ".png"))
        encode(b, t, *blobs[default][1])
        entries.append((sw, start + data, span, default, {sel: v[0] for sel, v in blobs.items()}))
    u[start:end] = b
    return bytes(u), pack_var(entries, nsel)


def font_cells(font):
    """{code point: glyph index} from a BFFNT's CMAP sections (the scan kind: a count, then a code and a glyph index each)"""
    at = font.find(b"CMAP")
    cells = {}
    while at >= 0:
        first, last, kind, _, nxt = struct.unpack_from("<IIHHI", font, at + 8)
        if kind == 2:
            count, = struct.unpack_from("<I", font, at + 0x18)
            for i in range(count):
                code, glyph = struct.unpack_from("<II", font, at + 0x1C + 8 * i)
                cells[code] = glyph
        at = nxt - 8 if nxt else -1
    return cells


def redraw_font(raw, face):
    """(a text font's bytes (a BFFNT, unwrapped) with the face's icons in the cells of the Switch buttons (FONT_CELLS), on the
    default controls: each as large as the old ink's box and in its place, the rest of the file as it is; and the variants, in
    redraw's format but per cell: the offset is the cell's first block's column | its row << 16 and the length its blocks' width |
    height << 16 (in the sheet as stored, upside down), and each selector's texture bytes are those blocks, row by row)"""
    from PIL import Image, ImageOps
    if raw[FONT_BNTX:FONT_BNTX + 4] != b"BNTX":
        raise SystemExit("kirby_prompts: no BNTX at the font's sheets")
    font = bytearray(raw)
    b = bytes(font[FONT_BNTX:])
    t = pa.bntx_textures(b)["0"]
    sheet = ImageOps.flip(pa.decode(b, t))
    cells = font_cells(raw)
    icons, sels, defaults = face_icons(face)
    pw, ph = FONT_PITCH
    drawn = []   # (the Switch button, the cell's place, its ink's box)

    def icon_in(key, box, cell):
        """key's icon as large as the old ink's box, in its place and inside the cell"""
        icon, _, _ = icons.masks(key, max(box[2] - box[0], box[3] - box[1]))
        new = Image.new("L", cell, 0)
        at = ((box[0] + box[2] - icon.width) // 2, (box[1] + box[3] - icon.height) // 2)
        new.paste(icon, (min(max(at[0], 0), cell[0] - icon.width), min(max(at[1], 0), cell[1] - icon.height)))   # (inside its cell)
        return new

    for code, sw in FONT_CELLS.items():
        glyph = cells.get(code)
        if glyph is None or glyph >= 64 or defaults[sw] not in sels:
            continue
        x, y = glyph % 8 * pw, glyph // 8 * ph
        box = sheet.crop((x, y, x + pw, y + ph)).point(lambda v: 255 if v > 127 else 0).getbbox()
        if box:
            drawn.append((sw, (x, y), box))
    for sw, (x, y), box in drawn:
        sheet.paste(icon_in(sels[defaults[sw]], box, (pw, ph)), (x, y))
    stored = ImageOps.flip(sheet)
    mask = Image.new("L", sheet.size, 0)
    entries = []
    for sw, (x, y), box in drawn:
        mask.paste(255, (x, y, x + pw, y + ph))
        sy = sheet.height - y - ph   # (the cell's rows as stored)
        bx0, by0, bx1, by1 = x // 4, sy // 4, (x + pw + 3) // 4, (sy + ph + 3) // 4
        blobs, by_icon = {}, {}
        for sel, key in sels.items():
            if icons.code[key] not in by_icon:   # (the same cell with this icon, over the rest as it is: a block holds the cells' edges)
                other = sheet.copy()
                other.paste(icon_in(key, box, (pw, ph)), (x, y))
                part = ImageOps.flip(other).crop((bx0 * 4, by0 * 4, bx1 * 4, by1 * 4))
                by_icon[icons.code[key]] = pa.encode_bc4(part)
            blobs[sel] = by_icon[icons.code[key]]
        entries.append((sw, by0 << 16 | bx0, (by1 - by0) << 16 | (bx1 - bx0), defaults[sw], blobs))
    for off, data in pa.runs(t, stored, mask=ImageOps.flip(mask)):
        font[FONT_BNTX + off:FONT_BNTX + off + len(data)] = data
    return bytes(font), pack_var(entries, 256 if face == "keyboard" else len(pa.PADS))


def main(argv):
    args = [a for a in argv if not a.startswith("--")]
    dump = argv[argv.index("--dump") + 1] if "--dump" in argv else None
    if dump:
        args.remove(dump)
    if len(args) != 3 or args[1] not in FACES + ["all"]:
        raise SystemExit(__doc__)
    romfs, face, out = args
    archives = {}
    for rel in ARCHIVES:
        if rel == PARTS or os.path.exists(os.path.join(romfs, rel)):   # (another one the romfs lacks: not written)
            with open(os.path.join(romfs, rel), "rb") as f:
                archives[rel] = unwrap(f.read())
    for one in FACES if face == "all" else [face]:
        shown = os.path.join(dump, one) if dump and face == "all" else dump
        if shown:
            os.makedirs(shown, exist_ok=True)
        src = os.path.join(romfs, FONT)
        if os.path.exists(src):
            with open(src, "rb") as f:
                new, fvar = redraw_font(unwrap(f.read()), one)
            dst = os.path.join(out, one, FONT) if face == "all" else os.path.join(out, FONT)
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            for name, data in ((dst, wrap(new, True)), (dst[:-len(".cmp")] + ".var", fvar)):
                with open(name + ".part", "wb") as f:
                    f.write(data)
                os.replace(name + ".part", name)
        for rel, parts in archives.items():
            path = os.path.join(out, one, rel) if face == "all" else os.path.join(out, rel)
            os.makedirs(os.path.dirname(path), exist_ok=True)
            seen = os.path.join(shown, os.path.dirname(rel)) if shown and rel != PARTS else shown
            if seen:
                os.makedirs(seen, exist_ok=True)
            parts_one, var = redraw(parts, one, seen)
            for name, data in ((path, wrap(parts_one, True)), (path[:-len(".cmp")] + ".var", var)):
                with open(name + ".part", "wb") as f:   # (a stopped build leaves no half file for the game to read)
                    f.write(data)
                os.replace(name + ".part", name)


if __name__ == "__main__":
    main(sys.argv[1:])
