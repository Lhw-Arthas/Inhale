"""(inhale) The slow frames of a frame trace, each given its likely cause: what microstutter is made of.

    python -I scripts/frame_hitches.py <frames.csv> [--from N] [--to N] [--slow 1.25] [--top 15] [--json]

<frames.csv> is the frame trace of a run with RX_VK_FRAME_TRACE=1: logs/inhale_frames.csv in the game folder (frames.csv in the
profile folder with HOS_PROFILE_DIR or HOS_PROFILE=1). --from and --to keep the frames numbered from N and up to N (leave a
loading screen out).

A frame is slow when its present-to-present time is --slow times the median or more. Its excess is the time over the median. Each
column is taken less its own median, so the steady cost of a part is not counted, and the frame's cause is:
- the specific group (pipeline, translate, upload, memsync, gpu) whose growth is the largest, when it is half the excess or more;
- else the broad part of the FPS counter's Breakdown (game, render, pace, wait_main, wait_render) that grew the most, by the same
  rule; pace is the frame pacing's wait (nn_vi.c), the game's sleeps and vsync;
- else unexplained: the time went where no column looks (the thread off the CPU, the display, the timer).
A slow frame that has a short one after it (under 0.75 of the median) is a frame the pacing then caught up: the screen shows that
as a judder even when the mean frame rate is right, and it is counted apart.

What this cannot see: a frame that left the game on time but reached the screen late (the compositor, a 60 fps game on a display
of another refresh rate without VRR). shown_ms (FIFO and RX_VK_PRESENT_THREAD=1) or PresentMon's DisplayedTime show that.
"""
import argparse
import csv
import json
import statistics
import sys

# (the frame trace's columns, gpu/vk/vk_replay.cpp's status_tick; a group's growth is the sum of its columns' growth)
SPECIFIC = {
    "pipeline": ("pipe_wait_ms", "pipelines_ms"),
    "translate": ("translate_ms",),
    "upload": ("uploads_ms", "tex_frame_ms"),
    "memsync": ("memsync_ms", "late_wait_ms", "readback_wait_ms"),
    "gpu": ("gpu_behind_ms", "gpu_wait_ms", "wait_gpu_ms"),
}
BROAD = {
    "game": ("game_ms",),
    "render": ("render_ms",),
    "pace": ("pace_ms",),
    "wait_main": ("wait_main_ms",),
    "wait_render": ("wait_render_ms",),
}
SHOWN = ("pipe_waits", "translate_ms", "uploads_ms", "memsync_ms", "gpu_behind_ms", "game_ms", "render_ms", "pace_ms",
         "wait_main_ms", "main_cpu_ms", "main_blocked_ms")
SHORT = 0.75   # (a frame under this share of the median after a slow one: the pacing catching up)


def read_rows(path, first=None, last=None):
    """[{column: float}] of the trace, in order; a line cut short (the run ended while writing it) left out"""
    out = []
    with open(path, newline="", encoding="utf-8", errors="replace") as f:
        rows = csv.DictReader(f)
        if not rows.fieldnames or "ms" not in rows.fieldnames or "frame" not in rows.fieldnames:
            raise SystemExit("%s: no frame and ms columns: not a frame trace (RX_VK_FRAME_TRACE=1)" % path)
        for r in rows:
            try:
                row = {k: float(v) for k, v in r.items() if k is not None and v not in (None, "")}
            except ValueError:
                continue
            if "ms" not in row or "frame" not in row:
                continue
            if (first is not None and row["frame"] < first) or (last is not None and row["frame"] > last):
                continue
            out.append(row)
    return out


def pct(sorted_ms, p):
    """The p-th percentile (nearest rank) of a sorted list"""
    i = min(len(sorted_ms) - 1, max(0, int(round(p / 100.0 * len(sorted_ms) + 0.5)) - 1))
    return sorted_ms[i]


def growth(row, cols, base):
    return sum(max(0.0, row.get(c, 0.0) - base.get(c, 0.0)) for c in cols)


def cause_of(row, base, excess):
    """(cause, {group: growth ms}) of a slow frame"""
    grown = {g: growth(row, cols, base) for g, cols in list(SPECIFIC.items()) + list(BROAD.items())}
    for groups in (SPECIFIC, BROAD):
        g = max(groups, key=lambda k: grown[k])
        if grown[g] >= 0.5 * excess:
            return g, grown
    return "unexplained", grown


def analyse(rows, slow=1.25):
    if not rows:
        raise SystemExit("no frames in the range")
    ms = [r["ms"] for r in rows]
    s = sorted(ms)
    median = statistics.median(ms)
    cols = set().union(*rows)
    base = {c: statistics.median(r.get(c, 0.0) for r in rows) for c in cols}
    hitches, causes, caught_up = [], {}, 0
    for i, r in enumerate(rows):
        if r["ms"] < slow * median:
            continue
        excess = r["ms"] - median
        cause, grown = cause_of(r, base, excess)
        after = rows[i + 1]["ms"] if i + 1 < len(rows) else None
        caught = after is not None and after < SHORT * median
        caught_up += caught
        causes[cause] = causes.get(cause, 0) + 1
        hitches.append({"frame": int(r["frame"]), "ms": r["ms"], "excess_ms": excess, "cause": cause, "caught_up": caught,
                        "grown": {k: round(v, 2) for k, v in grown.items() if v >= 0.05},
                        "row": {c: r[c] for c in SHOWN if c in r}})
    return {
        "frames": len(ms), "median_ms": median, "p95_ms": pct(s, 95), "p99_ms": pct(s, 99), "max_ms": s[-1],
        "slow_at_ms": slow * median, "slow": len(hitches),
        # (by how many display periods of the median the frame ran over: one missed vsync or more)
        "one_period": sum(1 for h in hitches if h["ms"] < 2.5 * median),
        "more_periods": sum(1 for h in hitches if h["ms"] >= 2.5 * median),
        "caught_up": caught_up, "causes": dict(sorted(causes.items(), key=lambda kv: -kv[1])), "hitches": hitches,
    }


def report(a, top):
    print("%d frames: median %.2f ms, p95 %.2f, p99 %.2f, max %.2f" % (a["frames"], a["median_ms"], a["p95_ms"], a["p99_ms"],
                                                                       a["max_ms"]))
    print("slow (%.2f ms or more): %d, %d by under 2.5 medians, %d by more; %d with a short frame after (caught up)"
          % (a["slow_at_ms"], a["slow"], a["one_period"], a["more_periods"], a["caught_up"]))
    if not a["hitches"]:
        return
    print("causes: " + ", ".join("%s %d" % kv for kv in a["causes"].items()))
    print("the slowest:")
    for h in sorted(a["hitches"], key=lambda h: -h["ms"])[:top]:
        grown = " ".join("%s+%.1f" % kv for kv in sorted(h["grown"].items(), key=lambda kv: -kv[1])[:4])
        print("  frame %d: %.2f ms (+%.2f) %s%s  [%s]" % (h["frame"], h["ms"], h["excess_ms"], h["cause"],
                                                      ", caught up" if h["caught_up"] else "", grown or "nothing grew"))


def main(argv=None):
    ap = argparse.ArgumentParser(description=(__doc__ or "").split("\n")[0])
    ap.add_argument("frames", help="the frame trace (logs/inhale_frames.csv)")
    ap.add_argument("--from", dest="first", type=int, help="the first frame kept")
    ap.add_argument("--to", dest="last", type=int, help="the last frame kept")
    ap.add_argument("--slow", type=float, default=1.25, help="a slow frame: this many medians or more (default 1.25)")
    ap.add_argument("--top", type=int, default=15, help="how many of the slowest frames to show (default 15)")
    ap.add_argument("--json", action="store_true", help="the numbers as JSON")
    a = ap.parse_args(argv)
    res = analyse(read_rows(a.frames, a.first, a.last), a.slow)
    if a.json:
        json.dump(res, sys.stdout, indent=1)
        print()
    else:
        report(res, a.top)


if __name__ == "__main__":
    main()
