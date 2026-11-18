#!/bin/bash
# What the Linux AppImage carries, fetched (packaging/pins.txt) and built into work/pkg/linux-deps (or $DEPS): each part
# once, kept while its version stays the same. Run it in the build image (packaging/linux/docker.sh): the sysroot is that
# system's C library, glibc 2.35, and the parts built here link against it. Adapted from upstream's scripts/linux/deps.sh
# (9af4808f), its "tools" mode included: upstream packs these as downloads, the AppImage here carries them.
#
#   python/    CPython (python-build-standalone) with tkinter (the builder's window) and requirements.txt's modules
#   llvm/      LLVM's clang and lld, in the layout toolchain.py finds through EMSDK (upstream/bin, upstream/lib/clang)
#   ffmpeg/    FFmpeg's libavcodec, libswscale, libswresample, libavutil, static and LGPL, with dav1d (AV1, VP8, VP9)
#   sdl2/      libSDL2-2.0.so.0: the window, sound and controllers, put beside the game
#   cpm/       Vulkan-Headers, SPIRV-Headers and VulkanMemoryAllocator, in the CPM layout nx2/build.py reads
#   sysroot/   this system's C library and GCC's runtime pieces: the game is compiled and linked against it
#   appimagetool, runtime-x86_64   the packer and the runtime it puts in front of the image
set -euo pipefail
cd "$(dirname "$0")/../.."
DEPS=${DEPS:-$PWD/work/pkg/linux-deps}
mkdir -p "$DEPS"
JOBS=${JOBS:-$(nproc)}
F() { python3 -I packaging/fetch.py "$@"; }
ver() { F version "$1" linux; }
done_for() { [ -f "$DEPS/.$1" ] && [ "$(cat "$DEPS/.$1")" = "$2" ]; }
mark() { echo "$2" > "$DEPS/.$1"; }

# ---- LLVM: clang, lld and clang's own headers, nothing else ----
LLVM_VER=$(ver llvm)
if ! done_for llvm "$LLVM_VER"; then
    archive=$(F path llvm linux)
    rm -rf "$DEPS/llvm" "$DEPS/llvm-x"
    mkdir -p "$DEPS/llvm-x"
    tar -xJf "$archive" -C "$DEPS/llvm-x" --strip-components=1 --wildcards \
        '*/bin/clang' '*/bin/clang++' '*/bin/clang-[0-9]*' '*/bin/lld' '*/bin/ld.lld' '*/bin/llvm-profdata' \
        '*/bin/llvm-cxxfilt' '*/lib/clang/*' '*/LICENSE.TXT'
    U=$DEPS/llvm/upstream
    mkdir -p "$U/bin" "$U/lib"
    mv "$DEPS/llvm-x/bin/"* "$U/bin/"
    mv "$DEPS/llvm-x/lib/clang" "$U/lib/clang"
    rm -rf "$DEPS/llvm-x"
    # (the runtimes: only the profile and builtins libraries; no sanitizers)
    find "$U"/lib/clang/*/lib -type f ! -name 'libclang_rt.profile*.a' ! -name 'libclang_rt.builtins*.a' -delete
    strip "$U/bin/clang-"[0-9]* "$U/bin/lld" "$U/bin/llvm-profdata" "$U/bin/llvm-cxxfilt" 2>/dev/null || true
    "$U/bin/clang" --version | head -1
    [ -f "$U/lib/clang/${LLVM_VER%%.*}/include/stddef.h" ] || { echo "clang's own headers are missing"; exit 1; }
    mark llvm "$LLVM_VER"
fi

# ---- Python with tkinter, and the tools' modules ----
PY_MARK="$(ver python)-tk-$(sha256sum requirements.txt nx2/prompt_requirements.txt | sha256sum | cut -c1-12)"
if ! done_for python "$PY_MARK"; then
    rm -rf "$DEPS/python"
    F unpack python linux "$DEPS"
    "$DEPS/python/bin/python3" -m pip install --no-cache-dir --only-binary :all: --disable-pip-version-check -q \
        -r requirements.txt
    "$DEPS/python/bin/python3" -I -c "import tkinter, numpy, lz4, capstone, unicorn, zstandard"
    rm -rf "$DEPS/python/lib/python3.12/test" "$DEPS/python/lib/python3.12/idlelib" "$DEPS/python/lib/python3.12/ensurepip" \
        "$DEPS/python/lib/python3.12/turtledemo"
    find "$DEPS/python" -name __pycache__ -prune -exec rm -rf {} +
    mark python "$PY_MARK"
fi

# ---- dav1d and FFmpeg (static, position independent: linked into the game's executable) ----
P=$DEPS/ffmpeg
FF_MARK="$(ver ffmpeg-src)-$(ver dav1d-src)"
if ! done_for ffmpeg "$FF_MARK"; then
    rm -rf "$P" "$DEPS/src-dav1d" "$DEPS/src-ffmpeg"
    F unpack dav1d-src linux "$DEPS/src-dav1d" --strip 1
    (cd "$DEPS/src-dav1d" && meson setup build --prefix="$P" --libdir=lib --buildtype=release --default-library=static \
        -Db_staticpic=true -Denable_tools=false -Denable_tests=false -Denable_examples=false && ninja -C build install)
    F unpack ffmpeg-src linux "$DEPS/src-ffmpeg" --strip 1
    (cd "$DEPS/src-ffmpeg" && PKG_CONFIG_PATH="$P/lib/pkgconfig" ./configure --prefix="$P" --pkg-config-flags=--static \
        --enable-static --disable-shared --enable-pic --disable-programs --disable-doc --disable-network --disable-autodetect \
        --disable-everything --disable-avformat --disable-avfilter --disable-avdevice \
        --enable-avcodec --enable-swscale --enable-swresample --enable-avutil \
        --enable-libdav1d --enable-decoder=vp8,vp9,libdav1d --enable-parser=vp8,vp9,av1 \
        && make -j"$JOBS" && make install)
    cp "$DEPS/src-ffmpeg/COPYING.LGPLv2.1" "$P/FFmpeg-COPYING.LGPLv2.1"
    cp "$DEPS/src-dav1d/COPYING" "$P/dav1d-COPYING"
    rm -rf "$DEPS/src-dav1d" "$DEPS/src-ffmpeg" "$P/share" "$P/lib/pkgconfig"
    mark ffmpeg "$FF_MARK"
fi

# ---- SDL2 (its X11, Wayland and sound back ends load their libraries at run time) ----
SDL_VER=$(ver sdl2-src)
if ! done_for sdl2 "$SDL_VER"; then
    rm -rf "$DEPS/src-sdl2" "$DEPS/sdl2"
    F unpack sdl2-src linux "$DEPS/src-sdl2" --strip 1
    cmake -S "$DEPS/src-sdl2" -B "$DEPS/src-sdl2/build" -G Ninja -DCMAKE_BUILD_TYPE=Release -DSDL_SHARED=ON -DSDL_STATIC=OFF \
        -DSDL_TEST=OFF -DSDL_X11=ON -DSDL_WAYLAND=ON -DSDL_PULSEAUDIO=ON -DSDL_PIPEWIRE=ON -DSDL_ALSA=ON
    ninja -C "$DEPS/src-sdl2/build"
    mkdir -p "$DEPS/sdl2"
    cp -L "$DEPS/src-sdl2/build/libSDL2-2.0.so.0" "$DEPS/sdl2/libSDL2-2.0.so.0"
    strip "$DEPS/sdl2/libSDL2-2.0.so.0"
    cp "$DEPS/src-sdl2/LICENSE.txt" "$DEPS/sdl2/LICENSE.txt"
    rm -rf "$DEPS/src-sdl2"
    mark sdl2 "$SDL_VER"
fi

# ---- the Vulkan back end's headers (their include/ folders and licences: nothing else of them is compiled) ----
packaging/cpm.sh linux "$DEPS/cpm"

# ---- appimagetool and its runtime ----
if ! done_for appimagetool "$(ver appimagetool)-$(ver appimage-runtime)"; then
    cp "$(F path appimagetool linux)" "$DEPS/appimagetool" && chmod +x "$DEPS/appimagetool"
    cp "$(F path appimage-runtime linux)" "$DEPS/runtime-x86_64"
    mark appimagetool "$(ver appimagetool)-$(ver appimage-runtime)"
fi

# ---- the sysroot (made again each time: it is this system's files, which its packages' updates change) ----
S=$DEPS/sysroot
rm -rf "$S"
mkdir -p "$S/usr/lib/x86_64-linux-gnu" "$S/usr/lib/gcc/x86_64-linux-gnu" "$S/lib64"
ln -s usr/lib "$S/lib"
cp -a /usr/include "$S/usr/"
rm -rf "$S/usr/include/c++" "$S/usr/include/x86_64-linux-gnu/c++" "$S/usr/include/llvm"* "$S/usr/include/clang"*
M=/usr/lib/x86_64-linux-gnu
for f in crt1.o crti.o crtn.o Scrt1.o rcrt1.o libc.so libc.so.6 libc_nonshared.a libm.so libm.so.6 libm.a libmvec.so libmvec.so.1 \
         libmvec.a libpthread.so.0 libpthread.a libdl.so.2 libdl.a librt.so.1 librt.a libutil.a libgcc_s.so.1 ld-linux-x86-64.so.2; do
    # (aliases with absolute targets (libmvec.so): their bytes, so the game never links against the player's own libraries)
    [ -e "$M/$f" ] && cp -aL "$M/$f" "$S/usr/lib/x86_64-linux-gnu/" || true
done
cp -aL /lib64/ld-linux-x86-64.so.2 "$S/lib64/"
GCC=$(ls -d /usr/lib/gcc/x86_64-linux-gnu/*/ | sort -V | tail -1)
GV=$(basename "$GCC")
G=$S/usr/lib/gcc/x86_64-linux-gnu/$GV
mkdir -p "$G" "$S/usr/include/c++" "$S/usr/include/x86_64-linux-gnu/c++"
cp -aL "/usr/include/c++/$GV" "$S/usr/include/c++/"
cp -aL "/usr/include/x86_64-linux-gnu/c++/$GV" "$S/usr/include/x86_64-linux-gnu/c++/"
for f in crtbegin.o crtbeginS.o crtbeginT.o crtend.o crtendS.o libgcc.a libgcc_eh.a libgcc_s.so libstdc++.a libstdc++fs.a libstdc++exp.a; do
    [ -e "$GCC/$f" ] && cp -aL "$GCC/$f" "$G/" || true
done
# (libgcc_s.so is a linker script naming /lib/x86_64-linux-gnu/libgcc_s.so.1: found in the sysroot through lib -> usr/lib)
echo "deps in $DEPS: $(du -sh "$DEPS" | cut -f1)"
