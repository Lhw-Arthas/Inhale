#!/bin/bash
# The Windows installer, made on Linux: packaging/windows/deps.sh, then the install folder staged in work/pkg/win-stage,
# a64emit.dll and the third-party objects prebuilt with llvm-mingw (RX_TARGET=windows), then NSIS (makensis) packs it into
# work/pkg/Inhale-Setup-x64.exe. Runs in the build image: packaging/linux/docker.sh windows.
#
# The install folder (packaging/windows/inhale.nsi copies it whole to %LOCALAPPDATA%\Programs\Inhale):
#   nx2 host gpu scripts third_party ...   Inhale's sources (the tracked files), VERSION
#   llvm-mingw\  python\  cpm\              the build tools (make_game.py and build.py find them beside nx2\)
#   third_party\sdl2\SDL2.dll, SDL3.dll     put beside the game by build.py
#   gui\                                    Inhale Builder's window (packaging/gui), its icon
#   third_party_objects\  licenses\
set -euo pipefail
cd "$(dirname "$0")/../.."
ROOT=$PWD
B=$ROOT/work/pkg
DEPS=${DEPS:-$B/windows-deps}
VERSION=${INHALE_VERSION:-$(git describe --tags --long --always --match "v[0-9]*" 2>/dev/null || echo dev)}
packaging/windows/deps.sh
S=$B/win-stage
rm -rf "$S"
mkdir -p "$S"

git ls-files -z -- nx2 host gpu scripts third_party requirements.txt LICENSE CREDITS.md README.md PROVENANCE.md |
    tar --null -T - -cf - | tar -xf - -C "$S"
printf '%s\n' "$VERSION" > "$S/VERSION"
cp -a "$DEPS/llvm-mingw" "$DEPS/python" "$DEPS/cpm" "$S/"
mkdir -p "$S/third_party/sdl2" "$S/gui"
cp "$DEPS/sdl/SDL2.dll" "$DEPS/sdl/SDL3.dll" "$S/third_party/sdl2/"
cp packaging/gui/*.py "$S/gui/"
cp packaging/icons/inhale.png packaging/icons/inhale.ico "$S/gui/"
cp -a packaging/licenses "$S/licenses"
# (the hot list, packaging/profiles/hot_funcs.txt: the game's hottest functions by name, which make_game.py lifts together;
# CPU time 10% less, docs/design.md S6. Every package carries it, CI's too)
mkdir -p "$S/work"
cp packaging/profiles/hot_funcs.txt "$S/work/hot_funcs.txt"
# (the profiles, when this checkout has them: counts from playing, no game code. Not tracked: their gain is not shown)
if [ -d work ]; then
    mkdir -p "$S/work/image"
    for f in hot_order.txt inhale_pieces.prof inhale_vk.profdata; do [ -f "work/$f" ] && cp "work/$f" "$S/work/"; done
    [ -f work/image/chunks.txt ] && cp work/image/chunks.txt "$S/work/image/"
fi

# ---- a64emit.dll, as build_emit.py builds it on Windows with the bundled llvm-mingw, and its stamp ----
MINGW=$DEPS/llvm-mingw-host
E=$S/third_party/a64-kit/lift
"$MINGW/bin/x86_64-w64-mingw32-clang++" -std=c++20 -O2 -shared -o "$E/a64emit.dll" "$E/a64emit.cpp" -Wno-everything \
    -fms-extensions -D_CRT_SECURE_NO_WARNINGS -fuse-ld=lld -static
python3 -I -c "import hashlib, sys; f = [sys.argv[1] + '/a64emit.cpp', sys.argv[1] + '/suyu/arm64_to_c.h']; open(sys.argv[1] + '/a64emit.dll.sha1', 'w').write(hashlib.sha1(b''.join(open(x, 'rb').read() for x in f)).hexdigest())" "$E"

# ---- the third-party code's objects, compiled as a player's build compiles them (nx2/third_party_objects.py) ----
# (with a Linux Python of the pinned version and the tools' modules: the build's scripts run here)
PY=$DEPS/host-python/bin/python3
if [ ! -x "$PY" ]; then
    python3 -I packaging/fetch.py unpack python linux "$DEPS/host-python" --strip 1
    "$PY" -m pip install --no-cache-dir --disable-pip-version-check -q --only-binary :all: -r requirements.txt
fi
(cd "$S" && RX_TARGET=windows LONGSHOT_MINGW="$MINGW" RX_CPM="$S/cpm" \
    "$PY" -I -B nx2/third_party_objects.py make "$S/third_party_objects" --jobs "${JOBS:-$(nproc)}")
find "$S" -name __pycache__ -prune -exec rm -rf {} +
rm -f "$S"/third_party/a64-kit/tools/lld-link*.exe

# ---- the installer ----
NUM=0.0.0
[[ $VERSION =~ ^v([0-9]+\.[0-9]+\.[0-9]+) ]] && NUM=${BASH_REMATCH[1]}
makensis -V2 -DSTAGE="$S" -DVERSION="$VERSION" -DVERNUM="$NUM.0" -DOUT="$B/Inhale-Setup-x64.exe" packaging/windows/inhale.nsi
echo "$B/Inhale-Setup-x64.exe ($VERSION): $(du -h "$B/Inhale-Setup-x64.exe" | cut -f1)"
