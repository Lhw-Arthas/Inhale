#!/bin/bash
# The release packages built in a container (packaging/linux/Dockerfile: Ubuntu 22.04), on any distribution. Adapted from
# upstream's scripts/linux/docker.sh (9af4808f).
#
#   packaging/linux/docker.sh            deps.sh, then appimage.sh -> work/pkg/Inhale-x86_64.AppImage
#   packaging/linux/docker.sh windows    packaging/windows/build.sh -> work/pkg/Inhale-Setup-x64.exe
#   packaging/linux/docker.sh shell      a shell in the build environment
#   packaging/linux/docker.sh <command>  any other command, run in the checkout
#
# The checkout is mounted at /src and the build runs as your user, so work/pkg belongs to you. DOCKER=podman uses Podman.
# INHALE_VERSION and JOBS are passed through when set.
set -euo pipefail
cd "$(dirname "$0")/../.."
DOCKER=${DOCKER:-docker}
IMAGE=${INHALE_IMAGE:-inhale-pkg-build}

"$DOCKER" build -t "$IMAGE" -f packaging/linux/Dockerfile packaging/linux

case "${1:-}" in
    "")      CMD=(bash -c 'packaging/linux/deps.sh && packaging/linux/appimage.sh') ;;
    windows) CMD=(packaging/windows/build.sh) ;;
    shell)   CMD=(bash) ;;
    *)       CMD=("$@") ;;
esac

RUN=(run --rm --init -v "$PWD:/src" -w /src)
# (Podman keeps your user with keep-id. Rootless Docker maps the container's root to you; Docker with a root daemon needs
# your user named)
if "$DOCKER" --version 2>/dev/null | grep -qi podman; then
    RUN+=(--userns=keep-id)
elif "$DOCKER" info --format '{{.SecurityOptions}}' 2>/dev/null | grep -q rootless; then
    :
else
    RUN+=(--user "$(id -u):$(id -g)")
fi
# (SELinux enforcing: label=disable lifts the label check for this container alone)
if [ "$(cat /sys/fs/selinux/enforce 2>/dev/null)" = 1 ]; then
    RUN+=(--security-opt label=disable)
fi
[ -t 0 ] && RUN+=(-it)
for v in INHALE_VERSION JOBS; do
    [ -n "${!v:-}" ] && RUN+=(-e "$v")
done

exec "$DOCKER" "${RUN[@]}" "$IMAGE" "${CMD[@]}"
