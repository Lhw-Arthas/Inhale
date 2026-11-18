"""The microphone rows are the other game's (the ocarina's input streams, host/nn_audio_in.c): this game imports the
SDK's input-stream API but no game code calls it, so the menu hides them and keeps them for upstream sync.

Reads gpu/vk/vk_menu.cpp only; nothing runs.

    python -I -B tests/test_mic_rows_hidden.py
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def function(text, marker):
    start = text.index(marker)
    depth = 0
    for at in range(text.index("{", start), len(text)):
        depth += text[at] == "{"
        depth -= text[at] == "}"
        if depth == 0:
            return text[start:at + 1]
    raise SystemExit("FAIL: unterminated: " + marker)


def main():
    menu = (ROOT / "gpu" / "vk" / "vk_menu.cpp").read_text(encoding="utf-8")
    is_oot = function(menu, "bool is_oot_row(const Row& r) {")
    rows = (
        ("Microphone", "v == &opts.mic" in is_oot),
        ("Microphone gain", "v == &opts.microphone_gain" in is_oot),
        ("Test microphone", 'r.tab == TAB_AUDIO && !v && !strcmp(r.name, "Test microphone")' in is_oot),
    )
    missing = [name for name, hidden in rows if not hidden]
    if missing:
        raise SystemExit("FAIL: the menu shows for this game: " + ", ".join(missing))
    if "oot_rows() || !is_oot_row(rows[i])" not in function(menu, "bool row_shown(int i) {"):
        raise SystemExit("FAIL: row_shown no longer hides is_oot_row's rows")
    print("mic rows: hidden for this game")


if __name__ == "__main__":
    raise SystemExit(main())
