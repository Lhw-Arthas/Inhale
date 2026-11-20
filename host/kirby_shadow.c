/* (inhale) The Insert menu's Shadow resolution for this game (Kirby and the Forgotten Land, Switch 2 Edition):
   docs/design.md, "issue #7, shadow resolution".

   The game's shadow map is one square depth target (D16) that it draws in three passes (land, decor, characters),
   then blurs twice into two R16 targets of the same size. Its size comes from data: basil/ScnCommon.bin of the data
   title holds, at 0x173ec40, ShadowMapResolutionConsole and ShadowMapResolutionHandheld as two u32, 1400 and 980.
   Docked, every stage seen draws its map at 1400 x 1400, which is coarse at a PC's resolutions.

   As the file is read, the console size becomes the row's: 0 (Game's) leaves it, 1 (High) 2800, twice the game's,
   2 (Highest) 4096, the largest side every Vulkan device can make. The handheld size stays the game's, as the handheld
   profile keeps the frame sizes (host/kirby_res.c). The size is raised, never lowered. The bytes are checked first: another
   version of the file is left as it is, and says so. The file is read once, at the start, so a change applies after a
   restart: the read tells the menu the level it applied, the row's value this run started with (gpu/vk/vk_menu.cpp
   menu_option_set), so that a change of it is tagged After restart and closing the menu asks to restart. */
#include <stdint.h>
#include <string.h>
#include "../gpu/vk/vk_api.h"

void hos_log(const char *fmt, ...);
int rx_option(int id, int otherwise);
void rx_option_set(int id, int value);

#define KIRBY_SHADOW_AT 0x173ec40
static const uint32_t kirby_shadow_game[2] = {1400, 980};   /* (console, handheld), as the game ships them */

/* Where the pair is in the read of [off, off + n) of a file the game opened as guest: its offset in the read, or -1 when
   the file is not ScnCommon.bin or the read does not hold the pair whole */
static int64_t kirby_shadow_where(const char *guest, int64_t off, uint64_t n) {
    static const char name[] = "/basil/ScnCommon.bin";
    const size_t len = guest ? strlen(guest) : 0, tail = sizeof name - 1;
    if (len < tail || strcmp(guest + len - tail, name)) return -1;
    const int64_t at = KIRBY_SHADOW_AT - off;
    return at < 0 || (uint64_t)at + sizeof kirby_shadow_game > n ? -1 : at;
}

/* The read of [off, off + n) of a file the game opened as guest, now in buf: the console size raised to the level's
   (HOS_OPT_SHADOW_RES, Auto resolved: 0 the game's, 1 High, 2 Highest) when the pair is there whole. Returns 1 when
   it was changed. */
int kirby_shadow_patch(const char *guest, int64_t off, uint8_t *buf, uint64_t n, int level) {
    const int64_t at = kirby_shadow_where(guest, off, n);
    if (at < 0) return 0;   /* (not this file or this read, or not all of the pair in it) */
    uint32_t v[2];
    memcpy(v, buf + at, sizeof v);
    if (memcmp(v, kirby_shadow_game, sizeof v)) {
        hos_log("kirby: %s: the shadow map sizes at %#x are not the ones known: left as they are", guest, KIRBY_SHADOW_AT);
        return 0;
    }
    const uint32_t size = level == 1 ? 2800 : level == 2 ? 4096 : 0;
    if (size <= v[0]) return 0;
    v[0] = size;
    memcpy(buf + at, v, sizeof v);
    hos_log("kirby: docked shadow map %ux%u (the game's %ux%u; the handheld profile's stays %ux%u)", size, size,
            kirby_shadow_game[0], kirby_shadow_game[0], v[1], v[1]);
    return 1;
}

/* kirby_res.c's kirby_read_done, for ScnCommon.bin's reads. Where the known pair is read, the level applied (Game's
   too) is told to the menu: what this run draws, the Shadow resolution row's start value for its restart */
void kirby_shadow_read(const char *guest, int64_t off, uint8_t *buf, uint64_t n) {
    const int level = rx_option(HOS_OPT_SHADOW_RES, 0);
    const int64_t at = kirby_shadow_where(guest, off, n);
    const int known = at >= 0 && !memcmp(buf + at, kirby_shadow_game, sizeof kirby_shadow_game);
    kirby_shadow_patch(guest, off, buf, n, level);
    if (known) rx_option_set(HOS_OPT_SHADOW_RES, level);
}
