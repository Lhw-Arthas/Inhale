/* SPDX-License-Identifier: GPL-3.0-or-later
   (inhale) A trap from the lifted code, kept for the crash record: docs/design.md, "issue #4".

   The record's reason is a fixed label ("hos_fatal"), never the formatted message (host/hos_crash_record.h), so a trap's
   address and kind were in the log alone, and a report can come without a log. a64_on_trap (host/hos_thread.c) notes
   them here before it stops the game, and the record's writer (host/hos_crash_record.c) puts them in a line of their
   own, guest_trap. The kind is one of the labels below, never the runtime's text: an svc's has a number formatted into
   it, and any other text becomes "other". The first trap is the one kept, as the first record is. */
#include <stddef.h>
#include <stdint.h>
#include <string.h>

static uint64_t trap_pc;
static const char *trap_label;
static int trap_state;   /* 0 none, 1 being written, 2 there */

/* why is the runtime's text (third_party/a64-kit/rt/a64_rt.c) */
void kirby_trap_note(uint64_t pc, const char *why) {
    static const struct { const char *why, *label; } kinds[] = {
        {"trap", "trap"},
        {"branch to a non-function", "branch to a non-function"},
        {"indirect call to an address with no function", "indirect call"},
        {"indirect jump to an address with no function", "indirect jump"},
    };
    int expected = 0;
    if (!__atomic_compare_exchange_n(&trap_state, &expected, 1, 0, __ATOMIC_ACQ_REL, __ATOMIC_ACQUIRE)) return;
    const char *label = why && !strncmp(why, "svc #", 5) ? "svc" : "other";
    for (size_t i = 0; why && i < sizeof kinds / sizeof kinds[0]; ++i)
        if (!strcmp(why, kinds[i].why)) label = kinds[i].label;
    trap_pc = pc;
    trap_label = label;
    __atomic_store_n(&trap_state, 2, __ATOMIC_RELEASE);
}

/* The noted trap's label and its address, NULL when no trap was noted. Reads three words: for the failing thread's writer */
const char *kirby_trap_noted(uint64_t *pc) {
    if (__atomic_load_n(&trap_state, __ATOMIC_ACQUIRE) != 2) return NULL;
    *pc = trap_pc;
    return trap_label;
}
