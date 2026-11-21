"""(inhale) Every renderer source that loads Vulkan through gpu/vk/vk_loader.h reaches it before any other way into
<vulkan/vulkan.h>: on Windows vk_loader.h defines VK_USE_PLATFORM_WIN32_KHR first, and vulkan.h declares the Win32 surface
(PFN_vkCreateWin32SurfaceKHR, which vk_loader.h's function table names) only when that is defined at its first
inclusion. A header that includes vulkan.h itself, included ahead of vk_loader.h, built on Linux and broke the Windows
renderer (vk_shader.cpp: "unknown type name 'PFN_vkCreateWin32SurfaceKHR'"); CI builds Linux only, so this check stands
for the Windows compile.

Each gpu/vk/*.cpp is walked as the preprocessor reads it: its #include lines in order, the quoted ones followed into the
files they name (beside the includer, then gpu/vk/), each header once (they are all #pragma once). A source that reaches
vk_loader.h must not meet <vulkan/vulkan.h> or <vk_mem_alloc.h> (which includes it) before. <vulkan/vulkan_core.h> is
allowed: it declares no platform's types. Conditional includes are followed as if their condition held.

python -I -B tests/test_vk_win32_include_order.py
"""
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
VK = ROOT / "gpu" / "vk"
LOADER = (VK / "vk_loader.h").resolve()
INCLUDE = re.compile(r'^\s*#\s*include\s*([<"])([^>"]+)[>"]', re.M)
PULLS_VULKAN_H = {"vulkan/vulkan.h", "vk_mem_alloc.h"}


def walk(path, seen, chain, events):
    """Records, in reading order, ("loader", chain) at vk_loader.h and ("vulkan", chain) at another way into vulkan.h"""
    path = path.resolve()
    if path in seen:
        return
    seen.add(path)
    if path == LOADER:
        events.append(("loader", chain))
        return   # (it defines the macro before its own vulkan.h)
    text = re.sub(r"/\*.*?\*/", "", path.read_text(encoding="utf-8", errors="replace"), flags=re.S)
    text = re.sub(r"//[^\n]*", "", text)
    for kind, name in INCLUDE.findall(text):
        if kind == "<" or not ((path.parent / name).is_file() or (VK / name).is_file()):
            if name in PULLS_VULKAN_H:
                events.append(("vulkan", chain + [f"<{name}>"]))
            continue
        nxt = path.parent / name if (path.parent / name).is_file() else VK / name
        walk(nxt, seen, chain + [name], events)


def main():
    bad, checked = [], 0
    for src in sorted(VK.glob("*.cpp")):
        events = []
        walk(src, set(), [src.name], events)
        kinds = [k for k, _ in events]
        if "loader" not in kinds:
            continue
        checked += 1
        first_loader = kinds.index("loader")
        for kind, chain in events[:first_loader]:
            if kind == "vulkan":
                bad.append(f"{src.relative_to(ROOT)}: vulkan.h before vk_loader.h, through " + " -> ".join(chain) +
                           "; vk_loader.h reached through " + " -> ".join(events[first_loader][1]))
    if checked < 20:
        print(f"FAIL: only {checked} sources reach vk_loader.h: the walk lost its way")
        return 1
    for line in bad:
        print("FAIL:", line)
    if bad:
        return 1
    print(f"ok: {checked} renderer sources reach vk_loader.h before any other vulkan.h")
    return 0


if __name__ == "__main__":
    sys.exit(main())
