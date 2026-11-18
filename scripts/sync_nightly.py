"""The nightly sync with upstream, with nobody at the keyboard: a timer runs this, and this runs the agent.

    python -I scripts/sync_nightly.py [--no-land]

What needs no judgement is done here, and what does is left to Claude (the sync-upstream skill, its section 8):

  1. upstream's clone is fetched (scripts/sync_upstream.py, UPSTREAM); the target is its origin/main;
  2. a clone of this repository under work/sync/tree is put on a branch `sync/upstream` at this repository's main.
     The work is done there, so the tree a person works in is never in its way, nor it in theirs;
  3. `claude -p` runs in that clone: scripts/sync_upstream.py, the conflicts, the stand-in, the checks, one commit;
  4. the gate: that commit lands on main only when the clone is clean and one commit past main, PROVENANCE.md
     names the target, the rename, third_party and every game-free check pass, and the game starts. The gate is run
     here, not by the agent, so a tree that fails it cannot reach main whatever the agent reports;
  5. main takes the commit by fast-forward, or not at all, and is pushed to origin.

The game's part of the gate, when this repository has the game's files (nx2/kit.py, DUMP): the clone's lift, its
build, and SECONDS of the game with no window, sound or movies. It passes when the game is still running at the end
and has presented FRAMES frames (half of 60 a second; 3301 in 60 s were measured). It has a work folder of its own,
work/sync/game, so the lift and the build a person works with stay theirs, and a user folder of its own, so no save
is touched. No hot list and no profiles: it asks whether the game starts, not how fast. Without the game's files that
part is left out, and the log says so.

A night that stops leaves the clone as it is and is never discarded: uncommitted work there stops every later run
until a person settles it, and a commit that did not land goes through the gate again on the next run, with nothing
new synced that night. --no-land stops before step 5, so the next run is the one that lands.

Every run that did something ends with a desktop notification (notify-send), and a stop exits 1. The agent's output
and the gate's are in work/sync/log-<date>.txt, the agent's own account in work/sync/tree/work/report.md. Standard
library and git only; the agent needs `claude` on PATH.

INHALE_SYNC_MODEL and INHALE_SYNC_EFFORT name the agent's model and effort (`claude --model`, `--effort`) for a PC
that wants others than the ones below: set them where the timer's service is defined.
"""
import argparse
import datetime
import fcntl
import os
import re
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sync_upstream  # noqa: E402
from sync_upstream import ROOT, git  # noqa: E402
sys.path.insert(0, os.path.join(ROOT, "nx2"))
import kit  # noqa: E402

WORK = os.path.join(ROOT, "work", "sync")
TREE = os.path.join(WORK, "tree")
GAME = os.path.join(WORK, "game")
SECONDS, FRAMES = 60, 1800
REPORT = os.path.join(TREE, "work", "report.md")
BRANCH = "sync/upstream"
BUDGET = "50"   # (dollars: where a night's agent stops whatever it is doing)
TOOLS = "Bash,Read,Edit,Write,Glob,Grep,Skill"
# (the most able model: nobody reads the merge before main takes it, and the gate sees only what breaks a check or
# the game's start)
MODEL = os.environ.get("INHALE_SYNC_MODEL") or "fable"
EFFORT = os.environ.get("INHALE_SYNC_EFFORT") or "high"
PROMPT = """Sync this clone with upstream to revision %(rev)s. Nobody is here to answer: follow the sync-upstream
skill and its section 8 (the nightly run). Upstream's clone is %(upstream)s: pass it as --upstream.
Run every Python command with `%(python)s -I`."""
ZERO = "0 places in 0 files, 0 files renamed"


def base_of(tree):
    with open(os.path.join(tree, "PROVENANCE.md"), encoding="utf-8") as f:
        return sync_upstream.read_base(f.read())


def gate(tree, target, checks):
    """checks: [(name, function -> whether it passed)], run in order and only when the tree itself is as it must be.
    -> why the commit of `tree` must not land, or None"""
    if git(tree, "status", "--porcelain").stdout.strip():
        return "the clone has uncommitted changes"
    ahead = int(git(tree, "rev-list", "--count", "origin/main..HEAD").stdout)
    if ahead != 1:
        return "the clone is %d commits past main, not one" % ahead
    base = base_of(tree)
    if base != target:
        return "upstream-base is %s, not %s" % (base[:8], target[:8])
    for name, passed in checks:
        if not passed():
            return "%s failed" % name
    return None


def checks(tree, log):
    def run(*args, env=None):
        r = subprocess.run([sys.executable, "-I"] + list(args), cwd=tree, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        log.write(r.stdout)
        log.flush()
        return r

    def game():
        env = dict(os.environ, INHALE_WORK=GAME, INHALE_DUMP=kit.DUMP, HOS_HEADLESS="1", HOS_AUDIO="0", HOS_NO_MOVIES="1")
        if (run("nx2/lift.py", "--standalone", "--write", env=env).returncode
                or run("nx2/build.py", "--standalone", "--jobs", str(os.cpu_count()), env=env).returncode):
            return False
        sa, user = os.path.join(GAME, "sa"), os.path.join(GAME, "user")
        os.makedirs(user, exist_ok=True)
        try:
            r = subprocess.run([os.path.join(sa, "build", "inhale"), os.path.join(sa, "image", "image.bin"),
                                "--romfs", os.path.join(kit.DUMP, "romfs"), "--aoc", os.path.join(kit.DUMP, "aoc"),
                                "--user", user],
                               cwd=GAME, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=SECONDS)
        except subprocess.TimeoutExpired as running:
            out = running.stdout or b""
            log.write(out)
            frames = re.findall(rb"vi: (\d+) frames presented", out)
            return bool(frames) and int(frames[-1]) >= FRAMES
        log.write(r.stdout + b"the game ended by itself, exit %d\n" % r.returncode)
        return False

    them = [("scripts/rename_full.py", lambda: run("scripts/rename_full.py").stdout.decode("utf-8", "replace").rstrip().endswith(ZERO)),
            ("scripts/check_third_party.py", lambda: run("scripts/check_third_party.py").returncode == 0),
            ("tests/run_all.py", lambda: run("-B", "tests/run_all.py").returncode == 0)]
    if kit.DUMP and os.path.isdir(kit.DUMP):
        them.append(("the game (lift, build, %d s with no window)" % SECONDS, game))
    else:
        log.write(b"the game's files are not here: the gate has no run of the game\n")
    return them


def notify(text):
    try:
        subprocess.run(["notify-send", "Inhale sync", text])
    except OSError:
        pass   # (no notifier on this PC: the exit status and the log say it)


def land(target, log, no_land):
    why = gate(TREE, target, checks(TREE, log))
    if why:
        told = ""
        if os.path.exists(REPORT):
            with open(REPORT, encoding="utf-8") as f:
                told = " The agent: %s (%s)." % (f.readline().strip(), REPORT)
        sys.exit("the sync to upstream %s did not land: %s.%s Log: %s" % (target[:8], why, told, log.name))
    if no_land:
        print("the sync to upstream %s passed the gate; not landed (--no-land)" % target[:8])
        return
    # (merge works on the branch that is checked out, whatever it is)
    if git(ROOT, "symbolic-ref", "--short", "-q", "HEAD", check=False).stdout.decode().strip() != "main":
        sys.exit("the sync to upstream %s passed the gate, and %s is not on main: it waits in %s" % (target[:8], ROOT, TREE))
    git(ROOT, "fetch", TREE, BRANCH)
    r = git(ROOT, "merge", "--ff-only", "FETCH_HEAD", check=False)
    if r.returncode:
        sys.exit("the sync to upstream %s passed the gate, and main did not take it; it waits in %s:\n%s"
                 % (target[:8], TREE, r.stderr.decode("utf-8", "replace")))
    r = git(ROOT, "push", "origin", "main", check=False)
    if r.returncode:
        sys.exit("main is at upstream %s here, and the push to origin failed; push it by hand:\n%s"
                 % (target[:8], r.stderr.decode("utf-8", "replace")))
    notify("main is at upstream %s, pushed" % target[:8])
    print("main is at upstream %s, pushed" % target[:8])


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--no-land", action="store_true", help="stop after the gate: main is not moved")
    a = p.parse_args()

    os.makedirs(WORK, exist_ok=True)
    lock = open(os.path.join(WORK, "lock"), "w")
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        sys.exit("another run of scripts/sync_nightly.py holds %s" % lock.name)

    upstream = os.path.abspath(sync_upstream.UPSTREAM)
    git(upstream, "fetch", "origin")
    target = git(upstream, "rev-parse", "--verify", "origin/main^{commit}").stdout.decode().strip()
    if not os.path.isdir(TREE):
        git(ROOT, "clone", ROOT, TREE)
    git(TREE, "fetch", "origin", "main")
    if git(TREE, "status", "--porcelain").stdout.strip():
        sys.exit("an earlier night's sync waits for you in %s: it has uncommitted changes" % TREE)

    with open(os.path.join(WORK, "log-%s.txt" % datetime.date.today().isoformat()), "ab") as log:
        if int(git(TREE, "rev-list", "--count", "origin/main..HEAD").stdout):
            land(base_of(TREE), log, a.no_land)   # (a commit that did not land: its gate again, and nothing new)
            return
        git(TREE, "checkout", "-B", BRANCH, "origin/main")
        if base_of(TREE) == target:
            print("already at upstream %s: nothing to do" % target[:8])
            return
        if os.path.exists(REPORT):
            os.remove(REPORT)
        prompt = PROMPT % {"rev": target, "upstream": upstream, "python": sys.executable}
        # (its exit status is not asked: the gate judges what it left)
        subprocess.run(["claude", "-p", prompt, "--model", MODEL, "--effort", EFFORT, "--permission-mode", "acceptEdits",
                        "--allowedTools", TOOLS, "--max-budget-usd", BUDGET],
                       cwd=TREE, stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT)
        land(target, log, a.no_land)


if __name__ == "__main__":
    try:
        main()
    except SystemExit as stop:
        if isinstance(stop.code, str):   # (every stop here, and a git command that failed)
            notify(stop.code)
        raise
