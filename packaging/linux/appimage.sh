#!/bin/bash
# The Linux AppImage: Inhale Builder's window, its Python, Inhale's sources and every build tool (packaging/linux/deps.sh),
# so a player needs no compiler and nothing is downloaded. No game data and nothing made from it is in it. Adapted from
# upstream's scripts/linux/appimage.sh (9af4808f), whose image carries no tools and no window.
#
#   packaging/linux/deps.sh        (first, in the build image: packaging/linux/docker.sh runs both)
#   packaging/linux/appimage.sh    -> work/pkg/Inhale-x86_64.AppImage
set -euo pipefail
cd "$(dirname "$0")/../.."
ROOT=$PWD
B=$ROOT/work/pkg
DEPS=${DEPS:-$B/linux-deps}
APPDIR=$B/AppDir
VERSION=${INHALE_VERSION:-$(git describe --tags --long --always --match "v[0-9]*" 2>/dev/null || echo dev)}
PY=$DEPS/python/bin/python3
L=$APPDIR/usr/lib/inhale
T=$APPDIR/usr/share/inhale

rm -rf "$APPDIR"
mkdir -p "$L" "$T"
# ---- the build tools, where AppRun and packaging/gui/tools_env.py look ----
cp -a "$DEPS/llvm" "$DEPS/sysroot" "$DEPS/ffmpeg" "$DEPS/sdl2" "$DEPS/cpm" "$L/"
rm -f "$L/cpm/.pins"
export EMSDK=$L/llvm RX_CPM=$L/cpm INHALE_SYSROOT=$L/sysroot
CLANGXX=$EMSDK/upstream/bin/clang++

# ---- the sources a player's build compiles, and the scripts: the tracked files, as they are in this checkout ----
git ls-files -z -- nx2 host gpu scripts third_party requirements.txt LICENSE CREDITS.md README.md PROVENANCE.md |
    tar --null -T - -cf - | tar -xf - -C "$T"
printf '%s\n' "$VERSION" > "$T/VERSION"   # (no git history in here: nx2/version.py reads the release name from it)
mkdir -p "$T/packaging"
cp -a packaging/gui "$T/packaging/"
cp packaging/icons/inhale.png "$T/packaging/gui/inhale.png"
cp -a packaging/licenses "$T/licenses"
# (the hot list, packaging/profiles/hot_funcs.txt: the game's hottest functions by name, which make_game.py lifts together;
# CPU time 10% less, docs/design.md S6. Every package carries it, CI's too)
mkdir -p "$T/work"
cp packaging/profiles/hot_funcs.txt "$T/work/hot_funcs.txt"
# (the profiles, when this checkout has them: counts from playing, no game code. Not tracked: their gain is not shown)
if [ -d work ]; then
    mkdir -p "$T/work/image"
    for f in hot_order.txt inhale_pieces.prof inhale_vk.profdata; do [ -f "work/$f" ] && cp "work/$f" "$T/work/"; done
    [ -f work/image/chunks.txt ] && cp work/image/chunks.txt "$T/work/image/"
fi

# ---- the tools' native helpers, built now: the AppImage is read-only. a64emit with its C++ runtime inside, and the stamp
# build_emit.py checks, so it is not built again; zbic's library ----
E=$T/third_party/a64-kit/lift
"$CLANGXX" -std=c++20 -O2 -shared -fPIC -static-libstdc++ -static-libgcc -Wno-everything -o "$E/liba64emit.so" "$E/a64emit.cpp"
(cd "$T" && "$PY" -I -c "import hashlib; f = ['third_party/a64-kit/lift/a64emit.cpp', 'third_party/a64-kit/lift/suyu/arm64_to_c.h']; open('third_party/a64-kit/lift/liba64emit.so.sha1', 'w').write(hashlib.sha1(b''.join(open(x, 'rb').read() for x in f)).hexdigest())"
  "$PY" -I third_party/a64-kit/lift/build_emit.py
  "$PY" -I -c "import sys; sys.path.insert(0, 'nx2'); import zbic; zbic.lib()")

# ---- the third-party code's objects, compiled with the tools every player's build uses (nx2/third_party_objects.py) ----
(cd "$T" && "$PY" -I -B nx2/third_party_objects.py make "$T/third_party_objects" --jobs "${JOBS:-$(nproc)}")
find "$T" -name __pycache__ -prune -exec rm -rf {} +

# ---- check: the bundled compiler builds and links a program against the sysroot, and it runs ----
C=$(mktemp -d "$B/check.XXXXXX")
cat > "$C/t.c" <<'C'
#include <pthread.h>
#include <stdio.h>
#include <math.h>
static void *f(void *p) { return p; }
int main(void) { pthread_t t; pthread_create(&t, 0, f, 0); pthread_join(t, 0); printf("ok %g\n", sqrt(2.0)); return 0; }
C
"$EMSDK/upstream/bin/clang" --sysroot="$INHALE_SYSROOT" -fuse-ld=lld -O2 -march=x86-64-v3 "$C/t.c" -o "$C/t" -lpthread -lm
"$C/t"
cat > "$C/t.cpp" <<'C'
#include <format>
#include <string>
extern "C" int t_cpp(int v) { return (int)std::format("{}", v).size(); }
C
"$CLANGXX" --sysroot="$INHALE_SYSROOT" -fuse-ld=lld -std=c++20 -O2 -shared -fPIC -static-libstdc++ -static-libgcc \
    "$C/t.cpp" -o "$C/t.so" -ldl -lpthread -lm
rm -rf "$C"

# ---- Python, and the AppDir's own files ----
cp -a "$DEPS/python" "$APPDIR/usr/python"
cp packaging/linux/AppRun "$APPDIR/AppRun"
cp packaging/linux/inhale-builder.desktop "$APPDIR/"
cp packaging/icons/inhale.png "$APPDIR/inhale-builder.png"
mkdir -p "$APPDIR/usr/share/icons/hicolor/256x256/apps"
cp packaging/icons/inhale.png "$APPDIR/usr/share/icons/hicolor/256x256/apps/inhale-builder.png"

OUT=$B/Inhale-x86_64.AppImage
rm -f "$OUT"
ARCH=x86_64 APPIMAGE_EXTRACT_AND_RUN=1 "$DEPS/appimagetool" --runtime-file "$DEPS/runtime-x86_64" --comp zstd "$APPDIR" "$OUT"
echo "$OUT ($VERSION): $(du -h "$OUT" | cut -f1)"
