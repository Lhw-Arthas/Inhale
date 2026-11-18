#!/bin/bash
# What the Windows installer carries, fetched (packaging/pins.txt) and cross-built on Linux into work/pkg/windows-deps (or
# $DEPS): each part once, kept while its version stays the same. Runs in the build image (packaging/linux/docker.sh
# windows) or on any Linux with meson, ninja, nasm, make and pkg-config. Upstream's Windows builder downloads these on the
# player's PC (tools.lock); the installer here carries them.
#
#   llvm-mingw/       the compiler a player's build uses (its Windows release): make_game.py finds it beside nx2/
#   llvm-mingw-host/  the same release for Linux: builds FFmpeg, dav1d and the prebuilt objects here
#   python/           CPython for Windows (python-build-standalone) with tkinter, and requirements.txt's modules
#   cpm/              the Vulkan, SPIR-V and VMA headers, FFmpeg (ffmpeg/<version>/{include,lib/avcodec.lib ...}) and dav1d
#                     (dav1d/<version>/{include,lib/libdav1d.a}), built with llvm-mingw, static: the CPM layout build.py reads
#   sdl/              SDL3.dll and SDL2.dll (sdl2-compat, which loads SDL3.dll beside it)
set -euo pipefail
cd "$(dirname "$0")/../.."
DEPS=${DEPS:-$PWD/work/pkg/windows-deps}
mkdir -p "$DEPS"
JOBS=${JOBS:-$(nproc)}
F() { python3 -I packaging/fetch.py "$@"; }
ver() { F version "$1" windows; }
done_for() { [ -f "$DEPS/.$1" ] && [ "$(cat "$DEPS/.$1")" = "$2" ]; }
mark() { echo "$2" > "$DEPS/.$1"; }

# ---- llvm-mingw, both releases ----
MV=$(ver llvm-mingw)
if ! done_for llvm-mingw "$MV"; then
    rm -rf "$DEPS/llvm-mingw" "$DEPS/llvm-mingw-host"
    F unpack llvm-mingw-host windows "$DEPS/llvm-mingw-host" --strip 1
    F unpack llvm-mingw windows "$DEPS/llvm-mingw" --strip 1
    mark llvm-mingw "$MV"
fi
MINGW=$DEPS/llvm-mingw-host
CC=$MINGW/bin/x86_64-w64-mingw32-clang

# ---- Python for Windows, with the tools' modules: wheels for win_amd64, installed by a Linux Python of the same version ----
PY_MARK="$(ver python)-$(sha256sum requirements.txt nx2/prompt_requirements.txt | sha256sum | cut -c1-12)"
if ! done_for python "$PY_MARK"; then
    rm -rf "$DEPS/python" "$DEPS/pip-python"
    F unpack python windows "$DEPS"
    F unpack python linux "$DEPS/pip-python" --strip 1
    # (--no-deps: every module is pinned, its runtime dependencies too: nx2/prompt_requirements.txt)
    "$DEPS/pip-python/bin/python3" -m pip install --no-cache-dir --disable-pip-version-check -q --no-deps \
        --only-binary :all: --platform win_amd64 --python-version 3.12 --implementation cp \
        --target "$DEPS/python/Lib/site-packages" -r requirements.txt
    rm -rf "$DEPS/pip-python" "$DEPS/python/Lib/test" "$DEPS/python/Lib/idlelib" "$DEPS/python/Lib/turtledemo"
    [ -f "$DEPS/python/pythonw.exe" ] && [ -d "$DEPS/python/Lib/tkinter" ] || { echo "the Windows Python has no pythonw.exe or tkinter"; exit 1; }
    find "$DEPS/python" -name __pycache__ -prune -exec rm -rf {} +
    mark python "$PY_MARK"
fi

# ---- the headers ----
packaging/cpm.sh windows "$DEPS/cpm-headers"

# ---- dav1d and FFmpeg, cross-built with llvm-mingw (as scripts/windows/dav1d.sh builds dav1d), static ----
DV=$(ver dav1d-src) FV=$(ver ffmpeg-src)
D=$DEPS/media/dav1d/$DV
P=$DEPS/media/ffmpeg/$FV-dav1d-$DV
if ! done_for media "$FV-$DV-$MV"; then
    rm -rf "$DEPS/media" "$DEPS/src-dav1d" "$DEPS/src-ffmpeg"
    W=$DEPS/cross
    mkdir -p "$W"
    printf '#!/bin/sh\nexec "%s" --reproducible "$@"\n' "$(command -v nasm)" > "$W/nasm"
    chmod +x "$W/nasm"
    cat > "$W/cross.txt" <<EOF
[binaries]
c = '$CC'
ar = '$MINGW/bin/llvm-ar'
strip = '$MINGW/bin/llvm-strip'
windres = '$MINGW/bin/x86_64-w64-mingw32-windres'
nasm = '$W/nasm'

[built-in options]
c_args = ['-mno-incremental-linker-compatible']

[host_machine]
system = 'windows'
cpu_family = 'x86_64'
cpu = 'x86_64'
endian = 'little'
EOF
    F unpack dav1d-src windows "$DEPS/src-dav1d" --strip 1
    (cd "$DEPS/src-dav1d" && meson setup build --cross-file "$W/cross.txt" --prefix="$D" --libdir=lib \
        --buildtype=release --default-library=static -Denable_tools=false -Denable_tests=false -Denable_examples=false \
        -Db_ndebug=true && ninja -C build install)
    cp "$DEPS/src-dav1d/COPYING" "$D/COPYING"
    F unpack ffmpeg-src windows "$DEPS/src-ffmpeg" --strip 1
    # (the same parts as the AppImage's, and Windows threads: --disable-autodetect would leave the decoders on one thread)
    (cd "$DEPS/src-ffmpeg" && PKG_CONFIG_LIBDIR="$D/lib/pkgconfig" ./configure --prefix="$P" --pkg-config-flags=--static \
        --enable-cross-compile --target-os=mingw32 --arch=x86_64 --cc="$CC" --cxx="$CC++" --ar="$MINGW/bin/llvm-ar" \
        --ranlib="$MINGW/bin/llvm-ranlib" --nm="$MINGW/bin/llvm-nm" --strip="$MINGW/bin/llvm-strip" --x86asmexe="$W/nasm" \
        --enable-static --disable-shared --disable-programs --disable-doc --disable-network --disable-autodetect \
        --enable-w32threads --disable-everything --disable-avformat --disable-avfilter --disable-avdevice \
        --enable-avcodec --enable-swscale --enable-swresample --enable-avutil \
        --enable-libdav1d --enable-decoder=vp8,vp9,libdav1d --enable-parser=vp8,vp9,av1 \
        && make -j"$JOBS" && make install)
    # (the names nx2/build.py links on Windows: <name>.lib, as the CPM cache's Visual Studio build has them. lld reads the
    # archive whatever it is called)
    for l in avcodec swscale swresample avutil; do mv "$P/lib/lib$l.a" "$P/lib/$l.lib"; done
    cp "$DEPS/src-ffmpeg/COPYING.LGPLv2.1" "$P/COPYING.LGPLv2.1"
    rm -rf "$DEPS/src-dav1d" "$DEPS/src-ffmpeg" "$W" "$P/share" "$P/lib/pkgconfig" "$D/lib/pkgconfig"
    mark media "$FV-$DV-$MV"
fi
rm -rf "$DEPS/cpm"
mkdir -p "$DEPS/cpm"
cp -a "$DEPS/cpm-headers/." "$DEPS/media/." "$DEPS/cpm/"
rm -f "$DEPS/cpm/.pins"

# ---- SDL ----
SV="$(ver sdl3)-$(ver sdl2-compat)"
if ! done_for sdl "$SV"; then
    rm -rf "$DEPS/sdl" "$DEPS/sdl-x"
    F unpack sdl3 windows "$DEPS/sdl-x/3"
    F unpack sdl2-compat windows "$DEPS/sdl-x/2"
    mkdir -p "$DEPS/sdl"
    cp "$DEPS/sdl-x/3/SDL3.dll" "$DEPS/sdl-x/2/SDL2.dll" "$DEPS/sdl/"
    rm -rf "$DEPS/sdl-x"
    mark sdl "$SV"
fi
echo "Windows deps in $DEPS: $(du -sh "$DEPS" | cut -f1)"
