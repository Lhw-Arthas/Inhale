"""A texture's or a program's release gives the thread's virtual core up only while the back end would wait, and a memory
pool's creation always does (host/rx_backend.c; HeyListen 3cefe030 and 7534b45c, GPL-3.0).

With the replay not asynchronous a release takes the replay's lock, held through a whole submission being replayed:
seconds behind slow pipeline compiles, with the game thread holding its core and every thread allowed on that core waiting.
The actual wrappers are compiled with stand-ins and the back end's hint (nvn_release_may_wait) decides:
- the hint says it would wait: the core is given up around the call and taken once after it;
- the hint says the locks are free: the core is kept, none taken (thousands of releases a load);
- no hint in the table: the core is given up;
- a thread without a core takes none; a release before the back end started is kept for later, the core kept;
- a pool made: the call without the core, the core back after.
And gpu/vk/vk_replay.cpp's hint is compiled with stand-in locks: free in an asynchronous replay; with either lock held,
it would wait; with both free, not, and both free again after the look.

python -I -B tests/test_vcore_release.py [--cxx clang++]
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

RUN_ALL_ARGS = ["--cxx", "{cxx}"]
ROOT = Path(__file__).resolve().parents[1]

HOST = r"""
#include <stdint.h>
#include <stdio.h>
#include <string.h>
typedef struct { int x; } nvn_tex;
typedef struct { int x; } nvn_prog;
typedef struct { int kind, n; nvn_tex t; } early_call;
static int started = 1, kept;
static int keep_early(early_call *c) { (void)c; kept++; return 1; }
static int held, takes, calls, calls_with_core, hint_value = 1;
int hos_vcore_away(void) { if (!held) return 0; held = 0; return 1; }
void hos_vcore_back(void) { if (!held) held = 1, takes++; }
static int hint(void) { return hint_value; }
static void rel_tex(const nvn_tex *t) { (void)t; calls++, calls_with_core += held; }
static void rel_prog(const nvn_prog *p) { (void)p; calls++, calls_with_core += held; }
static void pool_made(uint64_t gpu, uint64_t size) { (void)gpu, (void)size; calls++, calls_with_core += held; }
static struct {
    void (*nvn_texture_released)(const nvn_tex *);
    void (*nvn_program_released)(const nvn_prog *);
    void (*nvn_pool_created)(uint64_t, uint64_t);
    int (*nvn_release_may_wait)(void);
} table = {rel_tex, rel_prog, pool_made, hint}, *vk = &table;
#define wgr_nvn_texture_released rel_tex
#define wgr_nvn_program_released rel_prog

@WRAPPERS@

static int bad;
static void check(int ok, const char *what) { if (!ok) { printf("FAIL: %s\n", what); bad = 1; } }
static void reset(int core) { held = core, takes = calls = calls_with_core = 0; }
int main(void) {
    nvn_tex t = {1};
    nvn_prog p = {1};
    reset(1), hint_value = 1;
    rx_nvn_texture_released(&t);
    check(calls == 1 && calls_with_core == 0 && takes == 1 && held == 1, "would wait: the texture release without the core, taken back once");
    reset(1);
    rx_nvn_program_released(&p);
    check(calls == 1 && calls_with_core == 0 && takes == 1 && held == 1, "would wait: the program release without the core, taken back once");
    reset(1), hint_value = 0;
    rx_nvn_texture_released(&t);
    rx_nvn_program_released(&p);
    check(calls == 2 && calls_with_core == 2 && takes == 0 && held == 1, "locks free: the core kept, none taken");
    reset(0), hint_value = 1;
    rx_nvn_texture_released(&t);
    check(calls == 1 && takes == 0 && held == 0, "no core held: none taken");
    reset(1), table.nvn_release_may_wait = 0;
    rx_nvn_texture_released(&t);
    check(calls == 1 && calls_with_core == 0 && takes == 1, "no hint in the table: the core given up");
    table.nvn_release_may_wait = hint;
    started = 0, reset(1);
    rx_nvn_texture_released(&t);
    check(kept == 1 && calls == 0 && held == 1 && takes == 0, "before the back end started: kept for later, the core kept");
    started = 1;
    reset(1);
    rx_nvn_pool_created(0x1000, 0x1000);
    check(calls == 1 && calls_with_core == 0 && takes == 1 && held == 1, "a pool made: without the core, taken back once");
    if (!bad) puts("ok");
    return bad;
}
"""

HINT = r"""
#include <cstdio>
#include <mutex>
struct DrainingMutex { std::mutex m; void lock() {} bool try_lock() { std::puts("FAIL: replay_mu's try_lock (a replay boundary)"); return true; } void unlock() {} };
static DrainingMutex replay_mu;
static std::mutex sync_order_mu;
static bool async = false;
static bool async_on() { return async; }

@HINT@

static int bad;
static void check(bool ok, const char *what) { if (!ok) { std::printf("FAIL: %s\n", what); bad = 1; } }
static bool free_now(std::mutex &m) { if (!m.try_lock()) return false; m.unlock(); return true; }
int main() {
    check(release_may_wait() == 0, "both locks free: no wait");
    check(free_now(sync_order_mu) && free_now(replay_mu.m), "both locks free after the look");
    replay_mu.m.lock();
    check(release_may_wait() == 1, "the replay's lock held: it would wait");
    async = true;
    check(release_may_wait() == 0, "an asynchronous replay: no wait whatever is held");
    async = false;
    replay_mu.m.unlock();
    sync_order_mu.lock();
    check(release_may_wait() == 1, "the order lock held: it would wait");
    sync_order_mu.unlock();
    check(free_now(sync_order_mu) && free_now(replay_mu.m), "both locks free at the end");
    if (!bad) std::puts("ok");
    return bad;
}
"""


def run(compiler, folder, name, text):
    (folder / (name + ".cpp")).write_text(text, encoding="utf-8")
    exe = folder / (name + (".exe" if os.name == "nt" else ""))
    subprocess.run([compiler, "-std=c++17", "-O1", "-w", str(folder / (name + ".cpp")), "-o", str(exe), "-pthread"],
                   check=True, timeout=120)
    result = subprocess.run([str(exe)], capture_output=True, text=True, timeout=30)
    print(result.stdout, end="")
    return result.returncode == 0 and "ok" in result.stdout and "FAIL" not in result.stdout


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cxx", default="clang++")
    args = parser.parse_args()
    host = (ROOT / "host/rx_backend.c").read_text(encoding="utf-8")
    wrappers = "\n\n".join(block(host, m) for m in ("static int release_gives_core(void) {",
                                                     "void rx_nvn_texture_released(const nvn_tex *t) {",
                                                     "void rx_nvn_program_released(const nvn_prog *p) {",
                                                     "void rx_nvn_pool_created(uint64_t gpu, uint64_t size) {"))
    replay = (ROOT / "gpu/vk/vk_replay.cpp").read_text(encoding="utf-8")
    hint = block(replay, "static int release_may_wait() {")
    compiler = shutil.which(args.cxx)
    if not compiler:
        raise SystemExit("C++ compiler not found: " + args.cxx)
    with tempfile.TemporaryDirectory(prefix="vcore-release-") as temporary:
        folder = Path(temporary)
        ok = run(compiler, folder, "host", HOST.replace("@WRAPPERS@", wrappers))
        ok = run(compiler, folder, "hint", HINT.replace("@HINT@", hint)) and ok
    if not ok:
        raise SystemExit("a release or a pool's creation holds the virtual core while the back end waits, or gives it up for nothing")
    print("PASS: releases give the core up only while the replay's locks are held; a pool's creation always")


if __name__ == "__main__":
    main()
