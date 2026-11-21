"""(inhale) scripts/frame_hitches.py on a made-up frame trace, game-free.

300 steady frames of 16.67 ms (game 5, render 1.5, pace 10), with slow frames put in: a pipeline wait, a translation, an
upload, a memory sync, the GPU behind, the game's own code, the pacing's wait overshooting, one where no column grew, and one
with a short frame after it. Each must get its cause; the steady parts must not count (every slow frame would be "pace", the
largest steady part, without the medians taken off); the frames outside --from/--to are left out, and a line cut short is
skipped. Its broken variant (no median taken off) must fail.

    python -I -B tests/test_frame_hitches.py
"""
import importlib.util
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
HEADER = ("frame,ms,pipe_waits,pipe_wait_ms,left_out,translate_ms,uploads,upload_mb,textures,memsync_ms,pipelines_ms,uploads_ms,"
          "programs_ms,slot_wait_ms,gpu_behind_ms,draw_ms,desc_ms,cmds_ms,tex_lookup_ms,textures_gone,late_wait_ms,"
          "readback_wait_ms,tex_frame_ms,game_ms,render_ms,gpu_wait_ms,pace_ms,wait_render_ms,wait_gpu_ms,wait_main_ms,"
          "main_cpu_ms,main_blocked_ms,main_vcore_ms,shown_ms,shown_at_ns,at_ns,ab_side")
COLS = HEADER.split(",")
STEADY = {"ms": 16.67, "game_ms": 5.0, "render_ms": 1.5, "pace_ms": 10.0, "draw_ms": 0.8, "main_cpu_ms": 5.0, "shown_ms": -1}
# (frame: (its values over the steady ones, the cause it must get))
SLOW = {
    120: ({"ms": 30.0, "pipe_waits": 3, "pipe_wait_ms": 12.0, "render_ms": 14.0}, "pipeline"),
    130: ({"ms": 24.0, "translate_ms": 7.0, "render_ms": 8.5}, "translate"),
    140: ({"ms": 25.0, "uploads_ms": 8.0, "render_ms": 9.5}, "upload"),
    150: ({"ms": 24.0, "memsync_ms": 4.0, "late_wait_ms": 3.0}, "memsync"),
    160: ({"ms": 26.0, "gpu_behind_ms": 9.0, "gpu_wait_ms": 9.0, "pace_ms": 10.0}, "gpu"),
    170: ({"ms": 27.0, "game_ms": 15.0, "main_cpu_ms": 15.0}, "game"),
    180: ({"ms": 25.0, "pace_ms": 18.5}, "pace"),
    190: ({"ms": 25.0}, "unexplained"),
    200: ({"ms": 33.3, "pace_ms": 26.5}, "pace"),
}
CAUGHT = 201   # (the frame after 200: short, the pacing catching up)


def load():
    spec = importlib.util.spec_from_file_location("frame_hitches", ROOT / "scripts" / "frame_hitches.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def trace(path):
    lines = [HEADER]
    for n in range(1, 301):
        v = dict(STEADY)
        if n in SLOW:
            v.update(SLOW[n][0])
        if n == CAUGHT:
            v.update({"ms": 8.0, "pace_ms": 1.5})
        if n == 250:   # (a loading screen, left out by --to)
            v.update({"ms": 400.0})
        lines.append(",".join(str(v.get(c, n if c == "frame" else 0)) for c in COLS))
    lines.append("301,16.6")   # (cut short)
    Path(path).write_text("\n".join(lines) + "\n", encoding="utf-8")


def check(m, path):
    failures = []
    a = m.analyse(m.read_rows(path, 2, 240))
    got = {h["frame"]: h["cause"] for h in a["hitches"]}
    want = {n: c for n, (_, c) in SLOW.items()}
    if got != want:
        failures.append("causes: got %s, want %s" % (got, want))
    if a["frames"] != 239:
        failures.append("frames kept: %d, want 239 (2..240, the cut-short line out)" % a["frames"])
    if a["caught_up"] != 1 or not [h for h in a["hitches"] if h["frame"] == 200 and h["caught_up"]]:
        failures.append("caught up: %d, want frame 200 alone" % a["caught_up"])
    if a["more_periods"] != 0 or a["one_period"] != len(SLOW):
        failures.append("periods: %d and %d" % (a["one_period"], a["more_periods"]))
    if abs(a["median_ms"] - 16.67) > 1e-9 or a["max_ms"] != 33.3:
        failures.append("median %.2f, max %.2f" % (a["median_ms"], a["max_ms"]))
    whole = m.analyse(m.read_rows(path))
    if whole["max_ms"] != 400.0:
        failures.append("without --to the loading frame must stay")
    return failures


def main():
    m = load()
    with tempfile.TemporaryDirectory() as d:
        path = str(Path(d) / "frames.csv")
        trace(path)
        failures = check(m, path)
        # (the broken variant: each column's growth counted from 0, not from its median)
        broken = load()
        broken.growth = lambda row, cols, base: sum(max(0.0, row.get(c, 0.0)) for c in cols)
        if not check(broken, path):
            failures.append("the variant without the medians taken off passed: the check does not see it")
    for f in failures:
        print("FAIL:", f)
    print("frame_hitches: %s" % ("FAIL" if failures else "ok"))
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
