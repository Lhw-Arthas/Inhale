# The release packages' build environment, on any distribution: Ubuntu 22.04, adapted from upstream's
# scripts/linux/Dockerfile (9af4808f). Ubuntu 22.04 is not a preference: the AppImage's sysroot is this system's C library
# (packaging/linux/deps.sh), so the game a player builds runs on glibc 2.35 and newer. The same image cross-builds the
# Windows installer's FFmpeg and dav1d with llvm-mingw and packs it with NSIS (packaging/windows/build.sh).
#
# The image holds the system packages only. The checkout is mounted at /src when it runs (packaging/linux/docker.sh).
FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive
# (libstdc++ 13, from the toolchain PPA: C++20 <format>; linked in statically)
RUN apt-get update \
 && apt-get install -y --no-install-recommends software-properties-common gpg-agent \
 && add-apt-repository -y ppa:ubuntu-toolchain-r/test \
 && apt-get install -y --no-install-recommends g++-13 libstdc++-13-dev \
 && apt-get install -y --no-install-recommends git ca-certificates curl xz-utils zstd file unzip python3 \
      build-essential gcc-12 g++-12 libstdc++-12-dev nasm meson ninja-build cmake pkg-config nsis \
      libx11-dev libxext-dev libxrandr-dev libxcursor-dev libxi-dev libxss-dev libxfixes-dev libxinerama-dev \
      libxkbcommon-dev libwayland-dev wayland-protocols libdecor-0-dev libegl-dev libgles-dev libdrm-dev libgbm-dev \
      libpulse-dev libasound2-dev libpipewire-0.3-dev libudev-dev libdbus-1-dev zlib1g-dev \
 && rm -rf /var/lib/apt/lists/*

# (run as the caller's user, whose home is not in the image: git and pip want a writable HOME)
ENV HOME=/tmp
RUN git config --system --add safe.directory /src
WORKDIR /src
