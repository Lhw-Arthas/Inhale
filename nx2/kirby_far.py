"""Far animated objects at the frame rate, not at half or a quarter of it (Kirby and the Forgotten Land, Switch 2 Edition).

Every frame the game sorts each animated object into an update level by its squared distance to the camera
(main+0x8e2064 and on; the object's +0x84, +0x88 and +0x8c hold three distance steps, cumulative). Level 0 updates
every frame, level 1 only every second one (the dispatch at main+0x8e2350 tests the low bit of the frame counter plus the
object's index), level 2 one frame in four, level 3 sets a flag at +2 of the object's controller. Past the first step an
object is level 1 (level 2 when its bounding sphere is outside the view), past the second step level 2. At 60 presents a
second, scenery past the first step moves at 30 and past the second at 15: in the first stage's village the Maxim tomato
sign and the Waddle Dees around it update every fourth present (measured with a shot of each present, 59 pairs: a change
every fourth pair), and every present with the levels switched off.

The Switch 1 game's 60 fps patch skips the first step: its edit at main+0x7f0d1c there turns the far test's conditional branch
into an unconditional one, so such an object is judged as if it were near. (The patch file declares an offset_shift of 0x100, but the
code is at the listed offset of the decompressed module: the words there are a b.eq, a mul and a b.pl.) That alone leaves the tomato at one update in
four here, so this build skips the second step too. The first step's compare is written twice (the compiler repeats it
for an object with and without a second step), so three branches change; the third step (level 3) stays the game's:

  main+0x8e21a0  b.mi 0x8e20ec  (past step 1, no step 2: level 1)   becomes  nop  (near)
  main+0x8e21f4  b.pl 0x8e2228  (not past step 1: near)            becomes  b 0x8e2228  (always near)
  main+0x8e2180  b.pl 0x8e21e0  (not past step 2: go on to step 1) becomes  b 0x8e21e0  (never past step 2)

An object outside the view keeps its level 2, as the Switch 1 game's: the visibility test the near path ends with is not changed.
The Switch 1 patch's other two edits (0x5330d8, 0x533110) force the main loop's wait to one vertical sync, which is the
frame pacing. That already runs at 60 here, so they are not carried over.

The words are changed in the lifter's copy of the image only (after image.bin is written), so the lifted C has the
edit and the image the guest reads stays the game's. Each site's original word is checked: another build leaves them
out, and says so.
"""

BUILD_ID = "395fc326c2e5b1651d937074f8cfd75de63184d9"
NOP = 0xd503201f
# (offset in main, the game's word, the word that replaces it)
SITES = (
    (0x8e21a0, 0x54fffa64, NOP),          # b.mi #0x8e20ec
    (0x8e21f4, 0x540001a5, 0x1400000d),   # b.pl #0x8e2228, then b #+0x34 (0x8e2228 - 0x8e21f4 = 0x34 = 13 words)
    (0x8e2180, 0x54000305, 0x14000018),   # b.pl #0x8e21e0, then b #+0x60 (24 words)
)


def install(img, main_base, build_id):
    """Change the sites of the lifter's image; returns how many (0 when this is another build or code)"""
    if build_id != BUILD_ID or any(img.word(main_base + off) != old for off, old, _ in SITES):
        print("far objects: unsupported distance code, left out")
        return 0
    for off, _, new in SITES:
        at = main_base + off - img._base   # (EdenImage's base: its words are a view of mem, which this writes in place)
        img.mem[at:at + 4] = new.to_bytes(4, "little")
    print("far objects: the first two distance steps skipped (%d branches)" % len(SITES))
    return len(SITES)
