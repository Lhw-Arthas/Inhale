"""A freed address region's discard runs with the calling thread's virtual core given up (host/hos_mem.c).

nn::os::FreeAddressRegion (hos_region_free) discards the freed region's pages with a kernel call (DiscardVirtualMemory
on Windows, MADV_REMOVE on Linux). For the regions a change of area frees it runs for milliseconds at a time, and the
thread made it holding its virtual core, while the workers that run on that core only waited: 55 to 140 ms frames in
HeyListen (dc25c9c6, GPL-3.0). The call touches no guest state, so the core is given up for it, as for a file read
(tests/test_vcore_fs_open.py), after the region is out of the list and the list's lock let go.

The actual hos_region_free is compiled with stand-ins that record whether the thread holds its core and the lock in
discard_pages, and checks:

- a region freed: discarded without the core and without the lock, the core held again after, taken once;
- an address that is no region: nothing discarded, the core never given up;
- a thread that holds no core takes none.

python -I -B tests/test_vcore_region_free.py [--cxx clang++]
"""
import argparse
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))   # (tests/srccut.py: python -I leaves this folder off the path)
from srccut import block   # noqa: E402

RUN_ALL_ARGS = ["--cxx", "{cxx}"]

ROOT = Path(__file__).resolve().parents[1]

HARNESS = r"""
#include <stdint.h>
#include <stdio.h>
#include <string.h>
typedef struct { uint64_t addr, size; } Range;
static Range regions[4];
static int nregions;
static int locked;
#define LOCK() (locked = 1)
#define UNLOCK() (locked = 0)
static void pages_mark_used_locked(uint64_t addr, uint64_t size) { (void)addr, (void)size; }

/* the thread's virtual core, as hos_vcore_away / hos_vcore_back keep it (host/hos_thread.c) */
static int held, takes, aways;
int hos_vcore_away(void) { if (!held) return 0; held = 0; aways++; return 1; }
void hos_vcore_back(void) { if (!held) held = 1, takes++; }

static int discards, held_in_discard, locked_in_discard;
static uint64_t discarded;
static void discard_pages(uint64_t addr, uint64_t size) {
    discards++, discarded = addr, held_in_discard = held, locked_in_discard = locked;
    (void)size;
}

@FREE@

static int bad;
static void check(int ok, const char *what) { if (!ok) { printf("FAIL: %s\n", what); bad = 1; } }
static void free_region(uint64_t addr, int core) {
    held = core, takes = aways = discards = 0, held_in_discard = locked_in_discard = -1;
    hos_region_free(addr);
}
int main(void) {
    regions[0].addr = 0x10000, regions[0].size = 0x4000;
    regions[1].addr = 0x20000, regions[1].size = 0x8000;
    nregions = 2;
    free_region(0x10000, 1);
    check(discards == 1 && discarded == 0x10000, "the freed region is discarded");
    check(nregions == 1 && regions[0].addr == 0x20000, "the region is out of the list");
    check(held_in_discard == 0, "the discard runs without the virtual core");
    check(locked_in_discard == 0, "the discard runs with the regions' lock let go");
    check(held == 1 && takes == 1, "the core is held again after hos_region_free, taken once");

    free_region(0x30000, 1);
    check(discards == 0 && aways == 0 && held == 1, "no region at that address: nothing discarded, the core kept");

    free_region(0x20000, 0);
    check(discards == 1 && held_in_discard == 0 && held == 0 && takes == 0, "a thread that held no core takes none");
    if (!bad) puts("ok");
    return bad;
}
"""


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cxx", default="clang++")
    parser.add_argument("--source", type=Path, default=ROOT / "host/hos_mem.c")
    args = parser.parse_args()
    src = args.source.read_text(encoding="utf-8")
    fixture = HARNESS.replace("@FREE@", block(src, "void hos_region_free(uint64_t addr) {"))
    compiler = shutil.which(args.cxx)
    if not compiler:
        raise SystemExit("C++ compiler not found: " + args.cxx)
    with tempfile.TemporaryDirectory(prefix="vcore-region-free-") as temporary:
        folder = Path(temporary)
        (folder / "fixture.cpp").write_text(fixture, encoding="utf-8")
        exe = folder / ("fixture.exe" if os.name == "nt" else "fixture")
        subprocess.run([compiler, "-std=c++17", "-O1", "-w", str(folder / "fixture.cpp"), "-o", str(exe)], check=True,
                       timeout=120)
        result = subprocess.run([str(exe)], capture_output=True, text=True, timeout=30)
        print(result.stdout, end="")
        if result.returncode or "ok" not in result.stdout:
            raise SystemExit("hos_region_free holds its virtual core through the discard")


if __name__ == "__main__":
    main()
