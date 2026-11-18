#!/bin/bash
# The Vulkan back end's headers (packaging/pins.txt) in the CPM layout nx2/build.py reads, <dest>/<name>/<version>/include,
# with their licences: for both packages, as they are the same files.
#
#   packaging/cpm.sh <linux|windows> <dest>
set -euo pipefail
cd "$(dirname "$0")/.."
OS=$1 DEST=$2
mark=$(for n in vulkanheaders spirv-headers vulkanmemoryallocator; do python3 -I packaging/fetch.py version "$n" "$OS"; done | tr '\n' ' ')
[ -f "$DEST/.pins" ] && [ "$(cat "$DEST/.pins")" = "$mark" ] && exit 0
rm -rf "$DEST" "$DEST.x"
for n in vulkanheaders spirv-headers vulkanmemoryallocator; do
    v=$(python3 -I packaging/fetch.py version "$n" "$OS")
    python3 -I packaging/fetch.py unpack "$n" "$OS" "$DEST.x/$n" --strip 1
    mkdir -p "$DEST/$n/$v"
    cp -a "$DEST.x/$n/include" "$DEST/$n/$v/"
    for f in "$DEST.x/$n"/LICENSE*; do [ -f "$f" ] && cp "$f" "$DEST/$n/$v/"; done
done
rm -rf "$DEST.x"
echo "$mark" > "$DEST/.pins"
