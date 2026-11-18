/* (inhale) nn::aoc, and the add-on content mounts of nn::fs.

   Kirby and the Forgotten Land (Switch 2 Edition) keeps its data in a title of its own, which has no code: the code title's
   RomFS is empty, and the data title's id is an add-on content id (the base application's id + 0x1000 + an index, here 1).
   The game counts and lists its add-on content, then mounts one by index. Upstream's game had none of this: the calls ended
   in stubs that answer 0, "no add-on content".

   --aoc <folder> (hos_main.c), or HOS_AOC: the folder that holds one folder per add-on content title, named by its title id
   in 16 hex digits, each with a romfs/ inside. That is what nx2/nup.py unpacks to <dump>/aoc. The index is the id's low 12
   bits. Nothing is read from the titles but their folders' names. */
#include "hos.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#define WIN32_LEAN_AND_MEAN
#include <windows.h>

const char *hos_aoc_dir;
int hos_fs_mount_readonly(uint64_t guest_name, const char *root);   /* nn_fs.c */

enum { MAX_AOC = 64, AOC_PATH = 1024, R_AOC_NOT_FOUND = 0x7D402 };   /* (fs::ResultTargetNotFound: module 2, description 1002) */
typedef struct { int index; char romfs[AOC_PATH]; } Aoc;
static Aoc aocs[MAX_AOC];
static int naocs = -1;   /* (-1: not looked for yet) */
static SRWLOCK aoc_lock = SRWLOCK_INIT;

static int by_index(const void *a, const void *b) { return ((const Aoc *)a)->index - ((const Aoc *)b)->index; }

/* the add-on contents under hos_aoc_dir, by index; looked for once (the game asks from its main thread and its loaders) */
static int aoc_count(void) {
    AcquireSRWLockExclusive(&aoc_lock);
    if (naocs < 0) {
        naocs = 0;
        if (!hos_aoc_dir) hos_aoc_dir = getenv("HOS_AOC");
        char pattern[AOC_PATH];
        WIN32_FIND_DATAA fd;
        HANDLE h = INVALID_HANDLE_VALUE;
        if (hos_aoc_dir && *hos_aoc_dir) {
            snprintf(pattern, sizeof pattern, "%s/*", hos_aoc_dir);
            h = FindFirstFileA(pattern, &fd);
        }
        for (BOOL more = h != INVALID_HANDLE_VALUE; more && naocs < MAX_AOC; more = FindNextFileA(h, &fd)) {
            char *end = NULL;
            const unsigned long long id = strtoull(fd.cFileName, &end, 16);
            if (strlen(fd.cFileName) != 16 || *end) continue;   /* (a title id: 16 hex digits and nothing else) */
            Aoc *a = &aocs[naocs];
            snprintf(a->romfs, sizeof a->romfs, "%s/%s/romfs", hos_aoc_dir, fd.cFileName);
            if (GetFileAttributesA(a->romfs) == INVALID_FILE_ATTRIBUTES) continue;
            a->index = (int)(id & 0xFFF);
            naocs++;
        }
        if (h != INVALID_HANDLE_VALUE) FindClose(h);
        qsort(aocs, (size_t)naocs, sizeof aocs[0], by_index);
        hos_log("aoc: %d add-on content%s under %s", naocs, naocs == 1 ? "" : "s", hos_aoc_dir && *hos_aoc_dir ? hos_aoc_dir : "(no --aoc folder)");
        for (int i = 0; i < naocs; i++) hos_log("aoc: index %d: %s", aocs[i].index, aocs[i].romfs);
    }
    const int n = naocs;
    ReleaseSRWLockExclusive(&aoc_lock);
    return n;
}

/* nn::aoc::CountAddOnContent() -> int */
HLE(_ZN2nn3aoc17CountAddOnContentEv) { RET(aoc_count()); }

/* nn::aoc::ListAddOnContent(int* indices, int offset, int count) -> int: how many were written */
HLE(_ZN2nn3aoc16ListAddOnContentEPiii) {
    const int n = aoc_count(), offset = (int)ARG(1), count = (int)ARG(2);
    int written = 0;
    for (int i = offset < 0 ? 0 : offset; i < n && written < count; i++, written++)
        *(int32_t *)GP(ARG(0) + 4 * (uint64_t)written) = aocs[i].index;
    RET(written);
}

/* nn::fs::QueryMountAddOnContentCacheSize(unsigned long* size, int index) -> Result */
HLE(_ZN2nn2fs31QueryMountAddOnContentCacheSizeEPmi) { G64(ARG(0)) = 0x10000; RET(0); }

/* nn::fs::MountAddOnContent(char const* name, int index, void* cache, unsigned long cacheSize) -> Result */
HLE(_ZN2nn2fs17MountAddOnContentEPKciPvm) {
    const int n = aoc_count(), index = (int)ARG(1);
    for (int i = 0; i < n; i++)
        if (aocs[i].index == index) {
            RET(hos_fs_mount_readonly(ARG(0), aocs[i].romfs) ? 0 : R_AOC_NOT_FOUND);
            return;
        }
    hos_log("aoc: MountAddOnContent: no add-on content with index %d (%d known)", index, n);
    RET(R_AOC_NOT_FOUND);
}
