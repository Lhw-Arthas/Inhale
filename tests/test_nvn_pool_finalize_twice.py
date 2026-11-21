"""A memory pool object finalized twice untracks its range once only (host/nvn_native.c nvnMemoryPoolFinalize).

The change tracking counts the native pools by range (host/nvdrv.c hos_gpu_track), so a pool made over the same memory
as an earlier one shares its entry. A pool object finalized again (its magic gone with the first Finalize) untracked its
range a second time: the counted entry of a newer live pool made there since. That pool's CPU writes then reached the
renderer no more. HeyListen bbc95f03 (GPL-3.0): the second Finalize leaves the range alone, and says so.

The actual nvnMemoryPoolFinalize is compiled with stand-ins that count hos_gpu_track's on and off per range and the
prompts' pool-gone calls, and checks:

- a pool finalized: its range untracked once, the prompts told;
- the same object finalized again, while a newer pool lives over that memory: nothing untracked, the prompts not told
  (the memory is the newer pool's), a log line;
- a call with no pool: nothing.

python -I -B tests/test_nvn_pool_finalize_twice.py [--cc clang]
"""
import argparse
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
sys.path.insert(0, str(Path(__file__).resolve().parent))   # (tests/srccut.py: python -I leaves this folder off the path)
from srccut import block   # noqa: E402

RUN_ALL_ARGS = ["--cc", "clang"]

ROOT = Path(__file__).resolve().parents[1]

HARNESS = r"""
#include <stdint.h>
#include <stdio.h>
#include <string.h>
typedef long LONG;
typedef struct { uint64_t x[32]; } Ctx;
typedef struct {
    uint32_t magic, flags;
    uint64_t mem, size, gpu;
} nvn_pool;
#define P(i) ((void *)(uintptr_t)c->x[i])
#define NV(name) static void n_##name(Ctx *c, void *u_)
#define NVN_MAGIC(a, b, c, d) ((uint32_t)(a) | (uint32_t)(b) << 8 | (uint32_t)(c) << 16 | (uint32_t)(d) << 24)
static int logs;
static void hos_log(const char *fmt, ...) { (void)fmt; logs++; }
static long InterlockedIncrement(volatile long *v) { return ++*v; }
static int no_pool(Ctx *c, const char *what) { (void)what; return !c->x[0]; }
/* (a pool that is not virtual: the virtual pools' branch is not this check's) */
struct nvn_vmap { uint64_t gpu, size; uint64_t *page; struct nvn_vmap *next; };
static struct nvn_vmap *vmaps, *dead_vmaps;
static volatile LONG vmap_gen;
#define VPAGE 0x10000
static struct nvn_vmap *pool_vmap(const nvn_pool *o) { (void)o; return NULL; }
static void rx_nvn_vmap_changing(uint64_t a, uint64_t b) { (void)a, (void)b; }
#define AcquireSRWLockExclusive(l) ((void)0)
#define ReleaseSRWLockExclusive(l) ((void)0)

/* hos_gpu_track's count for the one range this check uses */
static int tracked, untracks;
void hos_gpu_track(uint64_t guest, uint64_t size, int on) {
    (void)guest, (void)size;
    if (on) tracked++;
    else tracked--, untracks++;
}
static int gone;
void hos_prompts_pool_gone(uint64_t mem) { (void)mem; gone++; }

@FINALIZE@

static int bad;
static void check(int ok, const char *what) { if (!ok) { printf("FAIL: %s\n", what); bad = 1; } }
static void finalize(nvn_pool *o) {
    Ctx c;
    memset(&c, 0, sizeof c);
    c.x[0] = (uint64_t)(uintptr_t)o;
    untracks = gone = logs = 0;
    n_nvnMemoryPoolFinalize(&c, NULL);
}
int main(void) {
    static uint8_t memory[0x2000];
    nvn_pool a, b;
    memset(&a, 0, sizeof a);
    a.magic = NVN_MAGIC('P', 'O', 'O', 'L'), a.mem = (uint64_t)(uintptr_t)memory, a.size = sizeof memory, a.gpu = 0x10000000;
    b = a;
    tracked = 1;   /* (a, made) */
    finalize(&a);
    check(untracks == 1 && tracked == 0, "a live pool finalized: its range untracked once");
    check(gone == 1, "a live pool finalized: the prompts told");
    check(a.magic == 0, "a finalized pool's magic is cleared");

    tracked = 1;   /* (b, made over the same memory) */
    finalize(&a);
    check(untracks == 0 && tracked == 1, "a pool finalized again untracks nothing (the newer pool's entry stays)");
    check(gone == 0, "a pool finalized again does not tell the prompts (the memory is the newer pool's)");
    check(logs == 1, "a pool finalized again is logged");

    finalize(&b);
    check(untracks == 1 && tracked == 0, "the newer pool's own Finalize untracks its range");

    Ctx c;
    memset(&c, 0, sizeof c);
    untracks = gone = 0;
    n_nvnMemoryPoolFinalize(&c, NULL);
    check(untracks == 0 && gone == 0, "no pool: nothing");
    (void)vmaps, (void)dead_vmaps, (void)vmap_gen;
    if (!bad) puts("ok");
    return bad;
}
"""


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cc", default="clang")
    parser.add_argument("--source", type=Path, default=ROOT / "host/nvn_native.c")
    args = parser.parse_args()
    src = args.source.read_text(encoding="utf-8")
    fixture = HARNESS.replace("@FINALIZE@", block(src, "NV(nvnMemoryPoolFinalize) {"))
    compiler = shutil.which(args.cc)
    if not compiler:
        raise SystemExit("C compiler not found: " + args.cc)
    with tempfile.TemporaryDirectory(prefix="nvn-pool-finalize-") as temporary:
        folder = Path(temporary)
        (folder / "fixture.c").write_text(fixture, encoding="utf-8")
        exe = folder / ("fixture.exe" if os.name == "nt" else "fixture")
        subprocess.run([compiler, "-std=c11", "-O1", "-w", str(folder / "fixture.c"), "-o", str(exe)], check=True,
                       timeout=120)
        result = subprocess.run([str(exe)], capture_output=True, text=True, timeout=30)
        print(result.stdout, end="")
        if result.returncode or "ok" not in result.stdout:
            raise SystemExit("nvnMemoryPoolFinalize untracks a pool's range again when the pool is finalized twice")


if __name__ == "__main__":
    main()
