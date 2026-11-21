"""A pipeline is drawn only with the program object it was built for (gpu/vk/vk_draw.cpp graphics_pipeline; HeyListen
1ae91a2d, after Hookshot 65e2cb91, GPL-3.0).

A pipeline's key names its program by code and variant hash, and two program objects can share both: one the precompile
built a noted pipeline for, and one a later draw picks. The draw then ran one program's shaders under the other's layout,
descriptors and constants (HeyListen: a light loop read garbage for its count, the device lost). The actual
graphics_pipeline is compiled with stand-ins for what it calls (RX_VK_SYNC_PIPELINES=1, so a new entry is built at once)
and checked:

- the first object gets an entry, noted under the key, built for it;
- a second object of the same key gets an entry of its own, built for it, not noted;
- each object asked again gets its own entry back, and no more builds;
- an entry the precompile made for an object (PipeEntry::prog, set in precompile_run) is given to that object, and a
  second object of its key gets its own.

python -I -B tests/test_pipe_by_program.py --headers <folder holding vulkan/vulkan.h> [--cxx clang++]
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

RUN_ALL_ARGS = ["--cxx", "{cxx}", "--headers", "{vulkan_headers}"]
ROOT = Path(__file__).resolve().parents[1]

FIXTURE = r"""
#include <atomic>
#include <cstdarg>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <functional>
#include <memory>
#include <mutex>
#include <unordered_map>
#include "draw_key.h"
#include "flat_map.h"
#include "compat/inhale_env.h"
using namespace mkwvk;
struct Program { uint64_t key = 0, variant = 0; bool fallback = false; };
struct NvnState {
    uint32_t vattr[16]{};
    struct { uint32_t divisor = 0; } vstream[16];
    uint64_t blend[8]{};
    struct { uint32_t blend_en = 0; } color;
    struct { uint32_t mask = 0; } chmask;
    struct { uint32_t mode = 0; } poly;
    struct { bool a2c = false; } ms;
    bool depth_clamp = false;
    int nvattr = 0;
};
struct Targets { int n = 0, samples = 1; VkFormat color_format[8]{}; VkFormat depth_format{}; };
static void logf(const char*, ...) {}
#define FINE_X(c, n) ((void)0)
#define FINE_N(c, n) ((void)0)
#define PROF_EXACT() ((void)0)
struct ParLock {};
static void pcache_init() {}
@ENTRY@
std::unordered_map<uint64_t, std::unique_ptr<PipeEntry>> pipelines;
std::mutex kept_ready_mu;
std::unordered_map<uint64_t, VkPipeline> kept_ready;
std::atomic<size_t> kept_ready_n{0};
struct { std::atomic<int> pipes_taken{0}, load_pipes_cold{0}, play_pipes_new{0}; } census;
struct { std::atomic<int> pipes_new{0}; int made_how = 0; } use_counters;
static struct { struct { bool pipelineCreationCacheControl = false; } vk13; } dev;
static bool ask_start_first;
namespace quick_pipe { struct Raise { explicit Raise(bool&) {} }; }
static bool slow_full_build;
static int builds;
static const Program* built_for[16];
static VkPipeline build_graphics(const Program& p, const NvnState&, const Targets&, VkPrimitiveTopology, int = -1, bool* = nullptr) {
    built_for[builds] = &p;
    return (VkPipeline)(uintptr_t)(0x1000 + ++builds);
}
static uint64_t pipeline_key(const Program& p, const NvnState&, const Targets&, VkPrimitiveTopology) { return p.key * 31 + p.variant; }
static int notes;
static uint64_t noted_key;
static bool pipeline_note(uint64_t key, const Program&, const NvnState&, const Targets&, VkPrimitiveTopology, const uint8_t*) {
    notes++, noted_key = key;
    return true;
}
static bool predicted_key(uint64_t) { return false; }
static void predicted_use(int) {}
static bool program_cache_complete_graphics(const Program&) { return true; }
static bool gpl_wanted() { return false; }
static VkPipeline gpl_link(const Program&, const NvnState&, const Targets&, VkPrimitiveTopology, uint64_t*) { return VK_NULL_HANDLE; }
static void gpl_build_cold(const Program&, const NvnState&, const Targets&, VkPrimitiveTopology, int, uint64_t) {}
static std::atomic<long long> st_link_us{0}, st_links{0};
static void jobs_push(std::function<void()> fn, bool = false, const std::atomic<bool>* = nullptr, std::function<void()> = {}) { fn(); }
@FAST@
@PIPE@

static int bad;
static void check(bool ok, const char* what) { if (!ok) { std::printf("FAIL: %s\n", what); bad = 1; } }
int main() {
    NvnState s;
    Targets at;
    const uint8_t ct[8]{};
    const VkPrimitiveTopology tri = VK_PRIMITIVE_TOPOLOGY_TRIANGLE_LIST;
    Program a, b, c, d;
    a.key = b.key = 0xA, a.variant = b.variant = 1;
    c.key = d.key = 0xC, c.variant = d.variant = 2;
    PipeEntry* ea = graphics_pipeline(a, s, at, tri, ct);
    check(ea && builds == 1 && built_for[0] == &a, "the first object: an entry built for it");
    check(notes == 1 && noted_key == pipeline_key(a, s, at, tri), "the first object's pipeline noted under the key");
    PipeEntry* eb = graphics_pipeline(b, s, at, tri, ct);
    check(eb && eb != ea, "a second object of the same key: an entry of its own");
    check(builds == 2 && built_for[1] == &b, "the second object's pipeline built for it");
    check(notes == 1, "the second object's own key is not noted (it holds an address)");
    check(graphics_pipeline(a, s, at, tri, ct) == ea && graphics_pipeline(b, s, at, tri, ct) == eb && builds == 2,
          "each object asked again: its own entry, no more builds");

#ifdef ENTRY_HAS_PROG   // (an entry that keeps no object, the source before this fix: the part above shows it)
    auto pre = std::make_unique<PipeEntry>();   // (as precompile_run makes one for the object program_find gave it)
    PipeEntry* ec = pre.get();
    ec->pipeline = (VkPipeline)(uintptr_t)0x9000;
    ec->prog.store(&c);
    ec->ready.store(true);
    pipelines.emplace(pipeline_key(c, s, at, tri), std::move(pre));
    PipeEntry* ed = graphics_pipeline(d, s, at, tri, ct);
    check(ed && ed != ec && builds == 3 && built_for[2] == &d, "a precompiled entry of another object: this one gets its own");
    check(graphics_pipeline(c, s, at, tri, ct) == ec && builds == 3, "the precompiled entry given to its own object");
#endif
    if (!bad) std::puts("ok");
    return bad;
}
"""


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cxx", default="clang++")
    parser.add_argument("--headers", required=True, help="folder holding vulkan/vulkan.h")
    args = parser.parse_args()
    draw = (ROOT / "gpu/vk/vk_draw.cpp").read_text(encoding="utf-8")
    entry = block(draw, "struct PipeEntry {") + ";"
    fast = block(draw, "struct PipeFast {") + ";\nthread_local PipeFast pipe_fast[2];"
    pipe = block(draw, "PipeEntry* graphics_pipeline(const Program& p, const NvnState& s, const Targets& at, VkPrimitiveTopology topo, const uint8_t color_types[8]) {")
    precompile = block(draw, "void precompile_run(")
    has_prog = "std::atomic<const Program*> prog{nullptr};" in entry
    if has_prog:
        find(precompile, "e->prog.store(p, std::memory_order_release);")
    if has_prog and precompile.index("e->prog.store(p,") > precompile.index("pipelines.emplace(n.key, std::move(e));"):
        raise SystemExit("precompile_run: the entry's program object is stored after it is published")
    fixture = ("#define ENTRY_HAS_PROG\n" if has_prog else "") + FIXTURE.replace("@ENTRY@", entry).replace("@FAST@", fast).replace("@PIPE@", pipe)
    compiler = shutil.which(args.cxx)
    if not compiler:
        raise SystemExit("C++ compiler not found: " + args.cxx)
    with tempfile.TemporaryDirectory(prefix="pipe-by-program-") as temporary:
        folder = Path(temporary)
        (folder / "fixture.cpp").write_text(fixture, encoding="utf-8")
        exe = folder / ("fixture.exe" if os.name == "nt" else "fixture")
        subprocess.run([compiler, "-std=c++20", "-O1", "-w", "-I", str(ROOT / "gpu/vk"), "-I", str(ROOT / "gpu"), "-I", args.headers,
                        str(folder / "fixture.cpp"), "-o", str(exe)], check=True, timeout=120)
        env = dict(os.environ, RX_VK_SYNC_PIPELINES="1")
        result = subprocess.run([str(exe)], capture_output=True, text=True, timeout=30, env=env)
        print(result.stdout, end="")
        if result.returncode or "ok" not in result.stdout:
            raise SystemExit("a pipeline built for one program object is drawn with another of the same key")
    print("PASS: a pipeline belongs to the program object it was built for")


if __name__ == "__main__":
    main()
