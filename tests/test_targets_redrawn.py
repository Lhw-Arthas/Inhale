"""A draw whose pipeline is not ready is left out only where the next frame draws its targets again
(gpu/vk/redrawn_inhale.h, gpu/vk/vk_draw.cpp targets_redrawn and draw; HeyListen 05378921, GPL-3.0).

A draw into targets that kept an earlier frame's picture was left out when no pipeline could be had, on the grounds
that the next frame draws it again. That holds for the scene, not for a piece the game draws once into a target it keeps
(a tile, a decal, a cached shadow): left out, it was never drawn again. The actual targets_redrawn is compiled with the
header and stand-in targets, and checked:

- a whole-target draw into targets rendered into last frame: redrawn (may be left out);
- a target last rendered into two frames ago, or never: not;
- a viewport or a scissor under nine tenths of the target: not; a scissor of 0 (none): as the viewport says;
- the depth target counts as a colour one does.

And draw()'s pipeline path asks it before a draw may be left out.

python -I -B tests/test_targets_redrawn.py [--cxx clang++]
"""
import argparse
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
sys.path.insert(0, str(Path(__file__).resolve().parent))   # (tests/srccut.py: python -I leaves this folder off the path)
from srccut import block, find   # noqa: E402

RUN_ALL_ARGS = ["--cxx", "{cxx}"]
ROOT = Path(__file__).resolve().parents[1]

FIXTURE = r"""
#include <cstdint>
#include <cstdio>
#include "redrawn_inhale.h"
struct Texture { uint64_t owned_frame = 0; };
struct Targets { Texture* color[8]{}; Texture* depth = nullptr; int n = 0; uint32_t width = 0, height = 0; };
struct NvnState { float viewport[16][4]{}; int32_t scissor[4]{0, 0, 0, 0}; };
static uint64_t frame = 100;
static uint64_t texture_frame_no() { return frame; }
@REDRAWN@
static int bad;
static void check(bool ok, const char* what) { if (!ok) { std::printf("FAIL: %s\n", what); bad = 1; } }
int main() {
    Texture c0, d;
    Targets at;
    at.color[0] = &c0, at.n = 1, at.depth = &d, at.width = 1920, at.height = 1080;
    NvnState s;
    s.viewport[0][2] = 1920, s.viewport[0][3] = 1080;
    c0.owned_frame = d.owned_frame = 99;
    check(targets_redrawn(at, s), "a whole-target draw into targets rendered last frame: redrawn");
    c0.owned_frame = 100;
    check(targets_redrawn(at, s), "rendered this frame already: redrawn");
    c0.owned_frame = 98;
    check(!targets_redrawn(at, s), "a colour target last rendered two frames ago: not redrawn");
    c0.owned_frame = 0;
    check(!targets_redrawn(at, s), "a colour target never rendered into: not redrawn");
    c0.owned_frame = 99, d.owned_frame = 90;
    check(!targets_redrawn(at, s), "a depth target last rendered long ago: not redrawn");
    d.owned_frame = 99;
    s.viewport[0][2] = 256, s.viewport[0][3] = 256;
    check(!targets_redrawn(at, s), "a viewport over a piece of the target (a tile): not redrawn");
    s.viewport[0][2] = 1920, s.viewport[0][3] = -1080;
    check(targets_redrawn(at, s), "a flipped whole viewport: redrawn");
    s.scissor[2] = 512, s.scissor[3] = 512;
    check(!targets_redrawn(at, s), "a scissor over a piece of the target (a decal): not redrawn");
    s.scissor[2] = 1920, s.scissor[3] = 1080;
    check(targets_redrawn(at, s), "a whole-target scissor: redrawn");
    at.width = 0;
    check(!targets_redrawn(at, s), "targets of no size: not redrawn");
    if (!bad) std::puts("ok");
    return bad;
}
"""


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cxx", default="clang++")
    args = parser.parse_args()
    draw = (ROOT / "gpu/vk/vk_draw.cpp").read_text(encoding="utf-8")
    redrawn = block(draw, "bool targets_redrawn(const Targets& at, const NvnState& s) {")
    pipe_path = block(draw, "if (!pe->ready.load(std::memory_order_acquire)) {")
    find(pipe_path, "const bool may_skip = !always_wait && targets_persistent(at) && targets_redrawn(at, s) && !writes_memory(p);")
    compiler = shutil.which(args.cxx)
    if not compiler:
        raise SystemExit("C++ compiler not found: " + args.cxx)
    with tempfile.TemporaryDirectory(prefix="targets-redrawn-") as temporary:
        folder = Path(temporary)
        (folder / "fixture.cpp").write_text(FIXTURE.replace("@REDRAWN@", redrawn), encoding="utf-8")
        exe = folder / ("fixture.exe" if os.name == "nt" else "fixture")
        subprocess.run([compiler, "-std=c++17", "-Wall", "-Wextra", "-Werror", "-I", str(ROOT / "gpu/vk"),
                        str(folder / "fixture.cpp"), "-o", str(exe)], check=True, timeout=120)
        result = subprocess.run([str(exe)], capture_output=True, text=True, timeout=30)
        print(result.stdout, end="")
        if result.returncode or "ok" not in result.stdout:
            raise SystemExit("a draw past its pipeline may be left out of a target the next frame does not draw again")
    print("PASS: a draw is left out only where the next frame redraws its targets")


if __name__ == "__main__":
    main()
