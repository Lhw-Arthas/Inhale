// (inhale) Whether a draw left out of its targets (its pipeline not ready) is drawn again in the next frames: every target
// was rendered into in the frame before (the scene's own, redrawn each frame) and the draw covers it, its viewport and
// scissor over nine tenths of it. Not a piece the game draws once into a target it keeps (a tile, a decal, a cached shadow
// updated a piece at a time): left out, such a piece was never drawn again, and that part of the target kept what was
// there before until the area was loaded again (HeyListen's striped ground). Those wait for their pipeline instead.
// HeyListen 05378921, after hookshot-nr 41f37acf (GPL-3.0); tests/test_targets_redrawn.py
#pragma once
#include <cmath>
#include <cstdint>

// now: the present being drawn; rendered[i]: the present each target was last rendered into (0: never; a missing target
// is not passed); width, height: the targets'; viewport: x, y, width, height; scissor: x, y, width, height (0 wide: none)
inline bool targets_redrawn_by(uint64_t now, const uint64_t* rendered, int n, uint32_t width, uint32_t height,
                               const float viewport[4], const int32_t scissor[4]) {
    for (int i = 0; i < n; i++)
        if (!rendered[i] || rendered[i] + 1 < now) return false;
    if (!width || !height) return false;
    const float w = (float)width * 0.9f, h = (float)height * 0.9f;
    if (std::fabs(viewport[2]) < w || std::fabs(viewport[3]) < h) return false;
    if (scissor[2] > 0 && scissor[3] > 0 && ((float)scissor[2] < w || (float)scissor[3] < h)) return false;
    return true;
}
