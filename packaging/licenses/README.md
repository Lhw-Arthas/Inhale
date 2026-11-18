# The bundled tools' notices

The release packages (`packaging/`) carry these tools so a player needs no compiler and downloads nothing. Each folder
here holds the notice of one of them, at the version `packaging/pins.txt` names; the packages ship this folder whole.
The source of each is at the URL its pins.txt line gives.

| Folder | What | Licence | In |
|---|---|---|---|
| `llvm` | clang, lld (LLVM) | Apache-2.0 with LLVM exception | AppImage |
| `llvm-mingw`, `mingw-w64` | llvm-mingw: LLVM, mingw-w64's headers and libraries | Apache-2.0 with LLVM exception; mingw-w64: ZPL, public domain and others (`mingw-w64/COPYING`) | installer |
| `glibc`, `gcc-runtime` | the sysroot: glibc 2.35 and GCC's runtime libraries (Ubuntu 22.04) | LGPL-2.1-or-later; GPL-3.0 with the GCC Runtime Library Exception | AppImage |
| `python`, `tcl-tk` | CPython 3.12 (python-build-standalone), with Tcl/Tk for the window | PSF-2.0; Tcl/Tk's BSD-style terms | both |
| `ffmpeg`, `dav1d` | FFmpeg's libavcodec, libswscale, libswresample, libavutil, with dav1d | LGPL-2.1-or-later; BSD-2-Clause | both |
| `sdl`, `sdl2-compat` | SDL 2 (AppImage), SDL 3 and sdl2-compat (installer) | zlib | both |
| `vulkan-headers`, `spirv-headers`, `vma` | the Vulkan back end's headers | Apache-2.0 / MIT; MIT; MIT | both |
| `nsis` | the installer's own code (NSIS) | zlib and others (`nsis/COPYING`) | installer |

FFmpeg is configured as `packaging/linux/deps.sh` and `packaging/windows/deps.sh` show (LGPL, no GPL or non-free
parts) and is linked into the game on the player's PC from the static libraries the package carries, so it can be
replaced with another build of the same version. The Python modules' own licences are in their `*.dist-info` folders.
