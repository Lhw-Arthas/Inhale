"""The gate of the nightly sync (scripts/sync_nightly.py): what stands between the agent's commit and main. On
repositories made here: no clone of upstream, no agent, no game.

  - one commit past main on a clean tree, with PROVENANCE.md at the target and every check passing, may land;
  - uncommitted changes, an untracked file, no commit, two commits, or a base that is not the target: refused, each
    with its reason, and no check is started (they take minutes, and they run what the tree holds);
  - a check that fails is named, and the ones after it are not run.

    python -I -B tests/test_sync_nightly.py
"""
import os
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import sync_nightly  # noqa: E402
from sync_upstream import git  # noqa: E402

RUN_ALL_SKIP = {"windows": "the nightly sync runs under a systemd timer, and its lock is fcntl's"}

BASE, TARGET = "a" * 40, "b" * 40
NOTES = "# Provenance\n\n    upstream-base:  %s\n"


def commit(repo, name, text, message):
    with open(os.path.join(repo, name), "w", encoding="utf-8", newline="\n") as f:
        f.write(text)
    git(repo, "add", name)
    git(repo, "commit", "-q", "-m", message)


def clone(folder, name, base):
    """A clone of the main repository whose branch is one commit past main, with `base` in PROVENANCE.md"""
    tree = os.path.join(folder, name)
    git(folder, "clone", "-q", os.path.join(folder, "main"), tree)
    commit(tree, "PROVENANCE.md", NOTES % base, "sync")
    return tree


def never():
    raise AssertionError("a check was started on a tree that must not land")


def main():
    # (this PC's git settings stay out of it: a signing key, a hook, a template)
    os.environ.update(GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_NOSYSTEM="1", GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@t.invalid",
                      GIT_COMMITTER_NAME="t", GIT_COMMITTER_EMAIL="t@t.invalid")
    ran = []
    passing = [("first", lambda: ran.append("first") or True), ("second", lambda: ran.append("second") or True)]
    with tempfile.TemporaryDirectory(prefix="inhale-sync-nightly-") as folder:
        main_repo = os.path.join(folder, "main")
        git(folder, "init", "-q", "-b", "main", main_repo)
        commit(main_repo, "PROVENANCE.md", NOTES % BASE, "import")

        good = clone(folder, "good", TARGET)
        why = sync_nightly.gate(good, TARGET, passing)
        assert why is None, why
        assert ran == ["first", "second"], ran

        why = sync_nightly.gate(good, TARGET, [("first", lambda: False), ("second", never)])
        assert why == "first failed", why

        with open(os.path.join(good, "left.txt"), "w") as f:
            f.write("left by the agent\n")
        why = sync_nightly.gate(good, TARGET, [("check", never)])
        assert why == "the clone has uncommitted changes", why
        os.remove(os.path.join(good, "left.txt"))
        with open(os.path.join(good, "PROVENANCE.md"), "a") as f:
            f.write("a conflict not settled\n")
        why = sync_nightly.gate(good, TARGET, [("check", never)])
        assert why == "the clone has uncommitted changes", why

        none = os.path.join(folder, "none")
        git(folder, "clone", "-q", main_repo, none)
        why = sync_nightly.gate(none, BASE, [("check", never)])
        assert why == "the clone is 0 commits past main, not one", why

        two = clone(folder, "two", "d" * 40)
        commit(two, "PROVENANCE.md", NOTES % TARGET, "and one more")
        why = sync_nightly.gate(two, TARGET, [("check", never)])
        assert why == "the clone is 2 commits past main, not one", why

        stale = clone(folder, "stale", "c" * 40)
        why = sync_nightly.gate(stale, TARGET, [("check", never)])
        assert why == "upstream-base is cccccccc, not bbbbbbbb", why
    print("ok")


if __name__ == "__main__":
    main()
