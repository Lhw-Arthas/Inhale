"""Game-free test of host/kirby_res.c: the dynamic resolution's six docked frame sizes in basil/ScnCommon.bin, scaled to a
16:9 output between 2560 x 1440 and 3840 x 2160 as the file is read, and left alone for another output, another file, a
read that does not hold the whole table, or a table that is not the one known. HOS_DYNAMIC_RES=0's fixed size. The sizes
in the fixture are the game's level sizes (numbers, no game data). And nn_fs.c's read calls it before the bytes are
marked written.

    python -I tests/test_kirby_res.py --cxx clang++
"""
import argparse
import subprocess
import sys
import tempfile
from pathlib import Path

RUN_ALL_ARGS = ["--cxx", "{cxx}"]

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))   # (python -I leaves the check's own folder off the path)
from srccut import block

FIXTURE = r'''
#include <assert.h>
#include <stdarg.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>

void hos_log(const char *fmt, ...) { va_list ap; va_start(ap, fmt); vprintf(fmt, ap); va_end(ap); printf("\n"); }
uint32_t hos_output_size(int height) { return height ? 2160 : 3840; }
int kirby_scn_patch(const char *guest, int64_t off, uint8_t *buf, uint64_t n, uint32_t out_w, uint32_t out_h, int fixed);

static const uint32_t game[18] = {0, 2560, 1440, 1, 2240, 1260, 2, 1862, 1048, 3, 1536, 864, 4, 1280, 720, 5, 854, 480};
static uint8_t file[0x98000];
static const char *path = "aoc1:/basil/ScnCommon.bin";

static void fresh(void) { memset(file, 0xab, sizeof file); memcpy(file + 0x97ca0, game, sizeof game); }
static uint32_t at(int k) { uint32_t v; memcpy(&v, file + 0x97ca0 + 4 * k, 4); return v; }
static int same(void) { return !memcmp(file + 0x97ca0, game, sizeof game) && file[0x97ca0 - 1] == 0xab && file[0x97ca0 + sizeof game] == 0xab; }

int main(void) {
    /* 3840 x 2160: x1.5, each side even; the index words and the bytes around the table stay */
    fresh();
    assert(kirby_scn_patch(path, 0, file, sizeof file, 3840, 2160, 0) == 1);
    const uint32_t want[18] = {0, 3840, 2160, 1, 3360, 1890, 2, 2792, 1572, 3, 2304, 1296, 4, 1920, 1080, 5, 1280, 720};
    for (int k = 0; k < 18; k++) assert(at(k) == want[k]);
    assert(file[0x97ca0 - 1] == 0xab && file[0x97ca0 + sizeof game] == 0xab);
    /* a read from further on that holds the table: the same */
    fresh();
    assert(kirby_scn_patch(path, 0x90000, file + 0x90000, sizeof file - 0x90000, 3840, 2160, 0) == 1 && at(1) == 3840);
    /* 3200 x 1800 */
    fresh();
    assert(kirby_scn_patch(path, 0, file, sizeof file, 3200, 1800, 0) == 1 && at(1) == 3200 && at(2) == 1800 && at(16) == 1066);
    /* the game's 2560 x 1440, a smaller one, 21:9, 16:10, larger than 3840 x 2160, the game's own 2048 x 1152 (0 x 0): left */
    const uint32_t keep[][2] = {{2560, 1440}, {1920, 1080}, {3440, 1440}, {3840, 2400}, {5120, 2880}, {0, 0}};
    for (unsigned i = 0; i < sizeof keep / sizeof *keep; i++) {
        fresh();
        assert(kirby_scn_patch(path, 0, file, sizeof file, keep[i][0], keep[i][1], 0) == 0 && same());
    }
    /* another file; a read that ends inside the table; one that starts inside it: left */
    fresh();
    assert(kirby_scn_patch("aoc1:/basil/App.bin", 0, file, sizeof file, 3840, 2160, 0) == 0 && same());
    assert(kirby_scn_patch(path, 0, file, 0x97ca0 + 40, 3840, 2160, 0) == 0 && same());
    assert(kirby_scn_patch(path, 0x97ca4, file + 0x97ca4, 0x100, 3840, 2160, 0) == 0 && same());
    /* a table that is not the one known (another version of the file): left */
    fresh();
    file[0x97ca0 + 4 * 7] ^= 1;
    assert(kirby_scn_patch(path, 0, file, sizeof file, 3840, 2160, 0) == 0 && at(7) == (1862 ^ 1) && at(1) == 2560);
    /* HOS_DYNAMIC_RES=0: every level the first one's size, at the output's or at the game's */
    fresh();
    assert(kirby_scn_patch(path, 0, file, sizeof file, 3840, 2160, 1) == 1);
    for (int k = 0; k < 6; k++) assert(at(3 * k) == (uint32_t)k && at(3 * k + 1) == 3840 && at(3 * k + 2) == 2160);
    fresh();
    assert(kirby_scn_patch(path, 0, file, sizeof file, 1920, 1080, 1) == 1);
    for (int k = 0; k < 6; k++) assert(at(3 * k + 1) == 2560 && at(3 * k + 2) == 1440);
    puts("ok");
    return 0;
}
'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cxx", default="c++")
    args = parser.parse_args()

    # (nn_fs.c's read: the sizes rewritten in the bytes read, before they are marked written for the GPU)
    read_at = block((ROOT / "host/nn_fs.c").read_text(encoding="utf-8"), "static uint64_t read_at(")
    call, written = read_at.find("kirby_read_done(fh->path, off, (uint8_t *)GP(buf), done);"), read_at.find("HOS_WRITTEN(")
    assert 0 <= call < written, "nn_fs.c read_at: kirby_read_done must run on the bytes read, before HOS_WRITTEN"

    with tempfile.TemporaryDirectory() as tmp:
        test = Path(tmp) / "test.c"
        test.write_text(FIXTURE, encoding="utf-8")
        exe = Path(tmp) / "test"
        subprocess.run([args.cxx, "-x", "c", "-std=c11", "-Wall", "-Werror", str(ROOT / "host/kirby_res.c"), str(test),
                        "-o", str(exe)], check=True)
        out = subprocess.run([str(exe)], capture_output=True, text=True)
        sys.stdout.write(out.stdout)
        assert out.returncode == 0 and out.stdout.rstrip().endswith("ok"), out.stderr
    print("test_kirby_res: ok")


if __name__ == "__main__":
    main()
