"""Game-free test of the depth mode the host answers before the game has set one (host/nvn_native.c,
nvn_depth_minus_w): docs/design.md, "the picture that stays wrong until cache/ is deleted".

The renderer asks the host for the mode whenever it translates a vertex stage (gpu/vk/vk_shader.cpp,
convert_depth_mode) and for the program cache's stamp. A shader preparation runs with no game, or before the game makes
its device, so it translates every program of the shader list for the mode the host starts with. That was 1 (near = -w),
upstream's game's mode, for every game: this game asks for near = 0, so each prepared vertex stage converted a depth
that needed none (z' = (z + w) / 2) and the scene's depth came out in 0.5..1.

Checked on the functions cut from the source, with the game stood in for by hos_game_is_oot():
- this game: near = 0 before any nvnDeviceSetDepthMode, and the game's own call then finds the prepared shaders right
  (no "not the one the prepared shaders were made for" line);
- upstream's game: near = -w before the call, as upstream has it, and no such line either;
- a game that sets the other mode than the one it started with still gets the line, and the new mode;
- a call made before anything asked (nothing was prepared for a mode) answers the same.

    python -I tests/test_depth_mode_start.py [--cc clang]
"""
import argparse
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

RUN_ALL_ARGS = ["--cc", "clang"]

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))   # (python -I leaves the check's own folder off the path)
from srccut import block, between

FIXTURE_HEAD = r'''#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

typedef long LONG;
typedef struct { uint64_t x[32]; } Ctx;
typedef struct { uint32_t depth_mode; } nvn_dev;
enum { NVN_DEPTH_MODE_NEAR_IS_MINUS_W = 0, NVN_DEPTH_MODE_NEAR_IS_ZERO = 1 };   /* (gpu/render/nvn_api.h) */
#define InterlockedExchange(p, v) __sync_lock_test_and_set((p), (v))
#define InterlockedCompareExchange(p, x, c) __sync_val_compare_and_swap((p), (c), (x))
#define P(i) ((void *)(uintptr_t)c->x[i])
#define U32(i) ((uint32_t)c->x[i])
#define NV(name) static void n_##name(Ctx *c)
static int oot, wrong_lines;
int hos_game_is_oot(void) { return oot; }
static void hos_log(const char *fmt, ...) { wrong_lines += strstr(fmt, "prepared shaders") != NULL; }
'''

FIXTURE_TAIL = r'''
static void set_mode(uint32_t mode) {
    nvn_dev dev = {0};
    Ctx c;
    memset(&c, 0, sizeof c);
    c.x[0] = (uint64_t)(uintptr_t)&dev, c.x[1] = mode;
    n_nvnDeviceSetDepthMode(&c);
}
#define CHECK(what, cond) do { if (!(cond)) { printf("FAIL: %s\n", what); return 1; } } while (0)

/* argv[1]: 1 when the game is upstream's; argv[2]: the case */
int main(int argc, char **argv) {
    if (argc != 3) return 2;
    oot = atoi(argv[1]);
    const int own = oot ? NVN_DEPTH_MODE_NEAR_IS_MINUS_W : NVN_DEPTH_MODE_NEAR_IS_ZERO;
    switch (atoi(argv[2])) {
    case 0:   /* the mode a preparation translates for, then the game's own call */
        CHECK("the mode before the game sets one is not the game's", nvn_depth_minus_w() == oot);
        set_mode((uint32_t)own);
        CHECK("the game's own mode changed the answer", nvn_depth_minus_w() == oot);
        CHECK("the game's own mode was reported as not the prepared shaders'", wrong_lines == 0);
        break;
    case 1:   /* the other mode after shaders were made for the first: said, and taken */
        (void)nvn_depth_minus_w();
        set_mode((uint32_t)!own);
        CHECK("the other mode was not taken", nvn_depth_minus_w() == !oot);
        CHECK("the other mode was not reported", wrong_lines == 1);
        break;
    case 2:   /* the game's call before anything asked */
        set_mode((uint32_t)own);
        CHECK("the game's own mode, set first, is not the answer", nvn_depth_minus_w() == oot);
        CHECK("the game's own mode, set first, was reported as not the prepared shaders'", wrong_lines == 0);
        break;
    default: return 2;
    }
    return 0;
}
'''


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--cc", default="clang", help="C compiler (clang or gcc)")
    a = p.parse_args()
    cc = shutil.which(a.cc)
    if not cc:
        raise SystemExit("test_depth_mode_start: no C compiler %r (pass --cc)" % a.cc)
    source = (ROOT / "host" / "nvn_native.c").read_text(encoding="utf-8")
    cut = "\n".join([
        # (the variable and whatever stands between it and its reader)
        between(source, "static volatile LONG depth_minus_w", "int nvn_depth_minus_w(void)"),
        block(source, "int nvn_depth_minus_w(void)"),
        block(source, "NV(nvnDeviceSetDepthMode)"),
    ])
    with tempfile.TemporaryDirectory(prefix="depth-mode-start-") as temp:
        d = Path(temp)
        (d / "fixture.c").write_text(FIXTURE_HEAD + cut + FIXTURE_TAIL, encoding="utf-8")
        exe = d / "fixture.exe"
        subprocess.run([cc, "-std=c11", "-O2", "-Wall", "-Wextra", "-Werror", "-Wno-unused-parameter",
                        str(d / "fixture.c"), "-o", str(exe)], check=True)
        failed = 0
        for game, oot in (("this game", 0), ("upstream's game", 1)):
            for case in range(3):
                r = subprocess.run([str(exe), str(oot), str(case)], capture_output=True, text=True)
                if r.returncode:
                    failed += 1
                    print("%s, case %d: %s" % (game, case, r.stdout.strip() or "exit %d" % r.returncode))
        if failed:
            raise SystemExit("test_depth_mode_start: %d of 6 cases failed" % failed)
    print("PASS: the depth mode before the game sets one is the game's (this game near = 0, upstream's near = -w), "
          "and another mode is still reported")


if __name__ == "__main__":
    main()
