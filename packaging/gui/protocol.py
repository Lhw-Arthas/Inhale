"""One line of nx2/make_game.py's output as an event for the builder's window: the @@ lines its docstring lists, and the plain
"the shaders were not prepared now" line. Anything else is a log line. Pure: no window, no process.

    parse("@@progress 0.5") -> ("progress", 0.5)
"""

# (the forms of make_game.py's docstring, in its order: tests/test_packaging_protocol.py checks the two lists agree)
KINDS = ("stage", "progress", "plan", "file", "eta", "times", "check", "done", "error")
NOT_PREPARED = "the shaders were not prepared now"   # (make_game.py NOT_PREPARED)


def _num(word, default=0.0):
    try:
        return float(word)
    except ValueError:
        return default


def parse(line):
    """(kind, value) for one line, without its line end:

    stage       (id, text)                 progress  fraction 0..1
    plan        (changed, total)           file      (name, seconds, new|cached|again)
    eta         seconds                    times     (total, compile, previous or None)
    check       (ok, text)                 done      folder
    error       text                       not_prepared  the line
    log         the line (anything else, an @@ form this parser does not know too)
    """
    line = line.rstrip("\r\n")
    if line.startswith(NOT_PREPARED):
        return ("not_prepared", line)
    if not line.startswith("@@"):
        return ("log", line)
    kind, _, rest = line[2:].partition(" ")
    words = rest.split()
    if kind == "stage" and words:
        return ("stage", (words[0], rest[len(words[0]):].strip()))
    if kind == "progress" and words:
        return ("progress", min(1.0, max(0.0, _num(words[0]))))
    if kind == "plan" and len(words) >= 2:
        return ("plan", (int(_num(words[0])), int(_num(words[1]))))
    if kind == "file" and len(words) >= 3:
        return ("file", (" ".join(words[:-2]), _num(words[-2]), words[-1]))
    if kind == "eta" and words:
        return ("eta", _num(words[0]))
    if kind == "times" and len(words) >= 3:
        previous = _num(words[2], -1.0)
        return ("times", (_num(words[0]), _num(words[1]), None if previous < 0 else previous))
    if kind == "check" and words:
        return ("check", (words[0] == "ok", rest[len(words[0]):].strip()))
    if kind == "done":
        return ("done", rest.strip())
    if kind == "error":
        return ("error", rest.strip())
    return ("log", line)


def eta_text(seconds):
    """A short "about N minutes left" for the window"""
    seconds = int(seconds)
    if seconds < 60:
        return "less than a minute left"
    minutes = (seconds + 30) // 60
    if minutes < 90:
        return "about %d minute%s left" % (minutes, "" if minutes == 1 else "s")
    return "about %.1f hours left" % (minutes / 60)
