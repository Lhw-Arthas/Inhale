"""Game-free test of nx2/kirby_far.py: the two branches it changes, the checks that leave another build or code alone.

    python -I nx2/test_kirby_far.py
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))   # (python -I leaves the script folder off)
import kirby_far

BASE = 0x80100000   # (main's base in a lifter image: any 4-aligned address)


class Image:
    """The lifter's image as EdenImage keeps it: mem from _base, words read from it"""
    _base = 0x80000000

    def __init__(self, words=None):
        self.mem = bytearray(0x900000 + (BASE - self._base))
        for off, old, _ in kirby_far.SITES:
            self.put(BASE + off, old if words is None else words[off])

    def put(self, a, w):
        self.mem[a - self._base:a - self._base + 4] = w.to_bytes(4, "little")

    def word(self, a):
        return int.from_bytes(self.mem[a - self._base:a - self._base + 4], "little")


class InstallTests(unittest.TestCase):
    def test_both_branches_change_and_nothing_else(self):
        img = Image()
        before = bytes(img.mem)
        self.assertEqual(kirby_far.install(img, BASE, kirby_far.BUILD_ID), 3)
        self.assertEqual(img.word(BASE + 0x8e21a0), 0xd503201f)   # nop
        self.assertEqual(img.word(BASE + 0x8e21f4), 0x1400000d)   # b #+0x34
        self.assertEqual(img.word(BASE + 0x8e2180), 0x14000018)   # b #+0x60
        changed = [i for i in range(len(before)) if before[i] != img.mem[i]]
        self.assertTrue(all(any(BASE - img._base + o <= i < BASE - img._base + o + 4 for o, _, _ in kirby_far.SITES) for i in changed))

    def test_unconditional_branch_reaches_the_near_path(self):
        for (off, _, word), target in zip(kirby_far.SITES[1:], (0x8e2228, 0x8e21e0)):
            self.assertEqual(word >> 26, 0b000101)                 # B
            self.assertEqual(off + 4 * (word & 0x3ffffff), target)

    def test_original_words_are_the_branches(self):
        # b.mi #0x8e20ec at 0x8e21a0, b.pl #0x8e2228 at 0x8e21f4, b.pl #0x8e21e0 at 0x8e2180: imm19 = (target - pc) / 4,
        # cond 4 (mi) and 5 (pl)
        for (off, old, _), target, cond in zip(kirby_far.SITES, (0x8e20ec, 0x8e2228, 0x8e21e0), (4, 5, 5)):
            self.assertEqual(old >> 24, 0x54)
            self.assertEqual(old & 0xf, cond)
            imm = (old >> 5) & 0x7ffff
            imm -= (imm & 0x40000) << 1
            self.assertEqual(off + 4 * imm, target)

    def test_another_build_is_left_alone(self):
        img = Image()
        before = bytes(img.mem)
        self.assertEqual(kirby_far.install(img, BASE, "another build"), 0)
        self.assertEqual(bytes(img.mem), before)

    def test_each_changed_word_is_left_alone(self):
        for off, old, _ in kirby_far.SITES:
            words = {o: w for o, w, _ in kirby_far.SITES}
            words[off] = old ^ 0x20
            img = Image(words)
            before = bytes(img.mem)
            self.assertEqual(kirby_far.install(img, BASE, kirby_far.BUILD_ID), 0)
            self.assertEqual(bytes(img.mem), before, "no site changes when one does not match")

    def test_lift_calls_it_for_the_standalone_build(self):
        lift = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "lift.py"), encoding="utf-8").read()
        self.assertLess(lift.index("kirby_far.install("), lift.index("discover.discover(L, "))


if __name__ == "__main__":
    unittest.main()
