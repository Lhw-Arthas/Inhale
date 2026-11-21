"""nn::audio's delay effect (host/nn_audio.c: AddDelay, its setters, RemoveDelay; HeyListen 924e08a9, GPL-3.0).

Kirby adds a delay on a sub mix and sets every parameter of it; these were unimplemented imports, and the mix stayed dry.
The actual delay section, effects_frame and the delay's SDK calls are compiled with stand-ins for the rest of the mixer and
driven with an impulse, no game or device:

- added and enabled, 10 ms, in gain 1, feedback 0.5, dry 1: the impulse at once (dry), its echo 480 samples later, the
  echo's echo at half after 960, the other channel silent;
- channel spread 1: the feedback goes to the pair channel;
- not enabled: the mix untouched;
- RemoveDelay gives the work buffer back, and the mix is untouched after; a later AddDelay takes the slot again;
- a delay added after an I3DL2 reverb on the same mix runs after it (the effects' order across their kinds).

python -I -B tests/test_audio_delay.py [--cc clang]
"""
import argparse
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
sys.path.insert(0, str(Path(__file__).resolve().parent))   # (tests/srccut.py: python -I leaves this folder off the path)
from srccut import block, between   # noqa: E402

RUN_ALL_ARGS = ["--cc", "gcc"]

ROOT = Path(__file__).resolve().parents[1]

HARNESS = r"""
#include <math.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
typedef struct { uint64_t x[32]; uint8_t vreg[32][16]; } Ctx;
#define HLE(sym) void imp_##sym(Ctx *c)
#define ARG(n) (c->x[n])
#define RET(v) (c->x[0] = (uint64_t)(v))
#define GP(a) ((void *)(uintptr_t)(a))
#define G64(a) (*(uint64_t *)GP(a))
#define AUT(...) ((void)0)
#define FRAME 240
#define RATE 48000
#define MAX_CH 8
#define MAX_BUF 24
#define MAX_MIXES 4
#define MAX_EFFECTS 16
#define AU_MAGIC 0x41554449u
enum { K_MIX = 2, K_EFFECT = 6, K_AUX = 8 };
typedef struct { int used, released, buffers; float buf[MAX_BUF][FRAME]; } Mix;
static Mix mixes[MAX_MIXES];
static int locked;
static void au_lock(void) { locked++; }
static void au_unlock(void) { locked--; }
@HANDLES@
static int mix_index(uint64_t obj) {
    const int i = get_handle(obj, K_MIX);
    return i >= 0 && i < MAX_MIXES && mixes[i].used ? i : -1;
}
static float farg(Ctx *c, int n) { float f; memcpy(&f, &c->vreg[n][0], 4); return f; }
/* the other kinds effects_frame orders the delays with: a call log */
typedef struct { int used, mix; uint64_t order; } Reverb;
typedef Reverb Aux;
static Reverb reverbs[MAX_EFFECTS];
static Aux auxes[MAX_EFFECTS];
static uint64_t effect_order;
static char calls[16];
@DELAY@
static int frees;   /* (the line's free at RemoveDelay, counted: the API below is compiled with this) */
#define free(p) (frees++, free(p))
static int pos_at_reverb = -1;   /* (where the delay's line stood when the reverb ran: moved on, the delay ran first) */
static void reverb_frame(Reverb *rv, Mix *m) { (void)rv, (void)m; strcat(calls, "R"); pos_at_reverb = delays[0].pos; }
static void aux_frame(Aux *a, Mix *m) { (void)a, (void)m; strcat(calls, "A"); }
@EFFECTS@
@API@

static int bad;
static void check(int ok, const char *what) { if (!ok) { printf("FAIL: %s\n", what); bad = 1; } }
static Ctx c;
static void call0(void) { memset(&c, 0, sizeof c); }
static void setf(void (*f)(Ctx *), uint64_t obj, float v) { call0(); c.x[0] = obj; memcpy(&c.vreg[0][0], &v, 4); f(&c); }
static void set1(void (*f)(Ctx *), uint64_t obj, uint64_t v) { call0(); c.x[0] = obj, c.x[1] = v; f(&c); }
static uint64_t mix_obj, delay_obj;
static uint8_t work[64];
static uint64_t add(int64_t max_ns, int channels) {
    call0();
    c.x[1] = (uint64_t)(uintptr_t)&delay_obj, c.x[2] = (uint64_t)(uintptr_t)work, c.x[3] = sizeof work;
    c.x[4] = (uint64_t)(uintptr_t)&mix_obj, c.x[5] = (uint64_t)max_ns, c.x[6] = (uint64_t)channels;
    imp__ZN2nn5audio8AddDelayEPNS0_19AudioRendererConfigEPNS0_9DelayTypeEPvmPNS0_10SubMixTypeENS_8TimeSpanEi(&c);
    return c.x[0];
}
static const uint64_t D = (uint64_t)(uintptr_t)&delay_obj;
static void fresh(void) {   /* (the delay removed and added again: a silent line) */
    call0(); c.x[1] = D; imp__ZN2nn5audio11RemoveDelayEPNS0_19AudioRendererConfigEPNS0_9DelayTypeEPNS0_10SubMixTypeE(&c);
    add(100000000, 2);
}
static void setup(float spread, int enabled) {
    setf(imp__ZN2nn5audio14SetDelayInGainEPNS0_9DelayTypeEf, D, 1.0f);
    setf(imp__ZN2nn5audio20SetDelayFeedbackGainEPNS0_9DelayTypeEf, D, 0.5f);
    setf(imp__ZN2nn5audio15SetDelayDryGainEPNS0_9DelayTypeEf, D, 1.0f);
    setf(imp__ZN2nn5audio21SetDelayChannelSpreadEPNS0_9DelayTypeEf, D, spread);
    setf(imp__ZN2nn5audio21SetDelayLowPassAmountEPNS0_9DelayTypeEf, D, 0.0f);
    set1(imp__ZN2nn5audio12SetDelayTimeEPNS0_9DelayTypeENS_8TimeSpanE, D, 10000000);   /* 10 ms: 480 samples */
    set1(imp__ZN2nn5audio15SetDelayEnabledEPNS0_9DelayTypeEb, D, (uint64_t)enabled);
}
/* 6 frames (1440 samples) with an impulse at sample 0 of buffer 0; what buffers 0 and 1 held */
static float out[2][6 * FRAME];
static void run(void) {
    for (int f = 0; f < 6; f++) {
        memset(mixes[0].buf, 0, sizeof mixes[0].buf);
        if (f == 0) mixes[0].buf[0][0] = 1.0f;
        calls[0] = 0;
        effects_frame(0);
        for (int b = 0; b < 2; b++) memcpy(&out[b][f * FRAME], mixes[0].buf[b], sizeof mixes[0].buf[b]);
    }
}
static int near(float a, float b) { return fabsf(a - b) < 1e-5f; }
static float energy(int b, int from) { float e = 0; for (int i = from; i < 6 * FRAME; i++) e += fabsf(out[b][i]); return e; }
int main(void) {
    mixes[0].used = 1, mixes[0].buffers = 2;
    put_handle((uint64_t)(uintptr_t)&mix_obj, K_MIX, 0);

    check(add(100000000, 2) == 0, "AddDelay on a mix succeeds");
    setup(0.0f, 1);
    run();
    check(near(out[0][0], 1.0f), "the dry impulse at once");
    check(near(out[0][480], 1.0f), "its echo 10 ms later");
    check(near(out[0][960], 0.5f), "the echo's echo at the feedback gain");
    check(energy(0, 1) - out[0][480] - out[0][960] < 1e-4f, "nothing else on the channel");
    check(energy(1, 0) < 1e-6f, "the other channel silent (no spread)");
    check(locked == 0, "the lock let go");

    call0(); c.x[1] = D; imp__ZN2nn5audio11RemoveDelayEPNS0_19AudioRendererConfigEPNS0_9DelayTypeEPNS0_10SubMixTypeE(&c);
    check(c.x[0] == (uint64_t)(uintptr_t)work, "RemoveDelay gives the work buffer back");
    check(frees == 1, "RemoveDelay frees the delay's line");
    run();
    check(energy(0, 1) < 1e-6f && near(out[0][0], 1.0f), "a removed delay leaves the mix untouched");

    check(add(100000000, 2) == 0, "AddDelay again after a remove");
    setup(1.0f, 1);
    run();
    check(near(out[0][480], 1.0f) && near(out[0][960], 0.0f), "spread 1: no feedback on the same channel");
    check(near(out[1][960], 0.5f), "spread 1: the feedback on the pair channel");

    setup(0.0f, 0);
    run();
    check(energy(0, 1) < 1e-6f && energy(1, 0) < 1e-6f, "a delay not enabled leaves the mix untouched");

    fresh();   /* (a new line: no tail of the runs above in it) */
    setup(0.0f, 1);
    setf(imp__ZN2nn5audio15SetDelayDryGainEPNS0_9DelayTypeEf, D, 0.5f);
    run();
    check(near(out[0][0], 0.5f) && near(out[0][480], 1.0f), "the dry gain on the input, not on the echo");

    fresh();
    {   /* (one channel, read from buffer 1 (silent) and written to buffer 0) */
        static int8_t in1[1] = {1}, out1[1] = {0};
        call0();
        c.x[0] = D, c.x[1] = (uint64_t)(uintptr_t)in1, c.x[2] = (uint64_t)(uintptr_t)out1, c.x[3] = 1;
        imp__ZN2nn5audio19SetDelayInputOutputEPNS0_9DelayTypeEPKaS4_i(&c);
    }
    setup(0.0f, 1);
    run();
    check(energy(0, 0) < 1e-6f, "SetDelayInputOutput: buffer 0 written from buffer 1 (silent), its impulse gone");
    check(energy(1, 0) < 1e-6f, "SetDelayInputOutput: buffer 1, only read, left as it was");

    reverbs[0].used = 1, reverbs[0].mix = 0, reverbs[0].order = ++effect_order;
    call0(); c.x[1] = D; imp__ZN2nn5audio11RemoveDelayEPNS0_19AudioRendererConfigEPNS0_9DelayTypeEPNS0_10SubMixTypeE(&c);
    check(add(100000000, 2) == 0, "AddDelay after a reverb");
    setup(0.0f, 1);
    calls[0] = 0;
    memset(mixes[0].buf, 0, sizeof mixes[0].buf);
    mixes[0].buf[0][0] = 1.0f;
    const int pos_before = delays[0].pos;
    effects_frame(0);
    check(!strcmp(calls, "R") && pos_at_reverb == pos_before && delays[0].pos != pos_before,
          "the reverb, then the delay: in the order added");
    if (!bad) puts("ok");
    return bad;
}
"""


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cc", default="gcc")
    parser.add_argument("--source", type=Path, default=ROOT / "host/nn_audio.c")
    args = parser.parse_args()
    src = args.source.read_text(encoding="utf-8")
    fixture = (HARNESS
               .replace("@HANDLES@", block(src, "static void put_handle(uint64_t obj, int kind, int index) {") + "\n"
                        + block(src, "static int get_handle(uint64_t obj, int kind) {"))
               .replace("@DELAY@", between(src, "/* ---- (inhale) delay (AddDelay:", "static void effects_frame(int mix) {"))
               .replace("@EFFECTS@", block(src, "static void effects_frame(int mix) {"))
               .replace("@API@", src[src.index("/* ---- (inhale) delay: AddDelay("):]))
    compiler = shutil.which(args.cc)
    if not compiler:
        raise SystemExit("C compiler not found: " + args.cc)
    with tempfile.TemporaryDirectory(prefix="audio-delay-") as temporary:
        folder = Path(temporary)
        (folder / "fixture.c").write_text(fixture, encoding="utf-8")
        exe = folder / ("fixture.exe" if os.name == "nt" else "fixture")
        subprocess.run([compiler, "-std=gnu11", "-O1", "-Wall", "-Wextra", "-Wno-unused-function", "-Werror",
                        str(folder / "fixture.c"), "-o", str(exe), "-lm"], check=True, timeout=120)
        result = subprocess.run([str(exe)], capture_output=True, text=True, timeout=30)
        print(result.stdout, end="")
        if result.returncode or "ok" not in result.stdout:
            raise SystemExit("nn::audio's delay does not echo, order or remove as it should")
    print("PASS: AddDelay echoes with its feedback and spread, keeps the effects' order, and RemoveDelay takes it away")


if __name__ == "__main__":
    main()
