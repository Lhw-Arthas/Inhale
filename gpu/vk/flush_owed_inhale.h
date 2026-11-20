// (inhale) A blocking wait for a fence value owes a flush of the batched submits (RX_VK_BATCH) to the submit that signals it.
//
// The race (vk_replay.cpp). A game's thread waiting for value f (wait) lets its submit on (gate_need_value), sends what is
// held (queue_flush_for(FR_WAIT)) and waits on the timeline. Its send often comes before the render thread has recorded the
// submit of f, so it sends nothing of it; the render thread then holds that submit (submit_recording's batch branch), and
// sends a batch itself only at RX_VK_BATCH_MAX or when the GPU is idle (batch_gpu_idle). With the GPU busy on the frame's
// long work, nothing sends it, and the wait gives up after its 10 s: the stall at the start of docs/design.md section 9,
// "issue #6", which issue #6's order (host/kirby_queue.c) made more frequent, and which every boot with
// RX_VK_FRAME_GATE=0 had.
//
// The fix stands in for upstream's (rec::take_flush_owed, ed9495bb, #1866), which is keyed on its recorder rewrite's
// parts and cannot be taken alone. The same idea keyed on fence values: the waiter owes f before its own send, and the
// submit that holds f sends the batch at once. Remove this file and its four lines in vk_replay.cpp at the sync that
// brings #1866.
//
// The order. The waiter: owe (a read-modify-write of upto), a seq_cst fence, then its send looks at pend_held. The
// submitter (dev.present_mu held): pend_held raised, a seq_cst fence, then due looks at upto. Of two seq_cst fences one
// comes first, so at least one side sees the other: the waiter's send finds the submit held (and takes dev.present_mu
// after the submitter let it go: f is in what it sends), or the submit finds f owed. owe always writes (a CAS of the max,
// not a load alone), as the fences' rule holds for a modification.
//
// As upstream's: the max of the values owed, cleared once a send reaches it (met). A lower waiter (f < g, both owed) is
// sent at the latest with g's submit, which g's own gate_need_value lets on. A value already sent is not owed: it would
// stay owed until the next submit, and every such wait (the frame before's fence, once a frame) would send that submit
// alone. A value sent while its waiter owes it can still be owed after: one batch then goes out early, once.
#pragma once
#include <atomic>
#include <cstdint>

namespace mkwvk {
struct FlushOwed {
    std::atomic<uint64_t> upto{0};   // the highest fence value a blocking wait asked for and not yet sent; 0: none
    /// (the waiter, before its own send) fence value v is waited for; sent: the highest value already in the queue
    void owe(uint64_t v, uint64_t sent) {
        if (v <= sent) return;
        uint64_t was = upto.load(std::memory_order_relaxed);
        while (!upto.compare_exchange_weak(was, was > v ? was : v, std::memory_order_relaxed)) {}
        std::atomic_thread_fence(std::memory_order_seq_cst);
    }
    /// (the submitter, dev.present_mu held, after pend_held is raised) whether what is held, up to fence value held_upto,
    /// is to be sent now
    bool due(uint64_t held_upto) {
        std::atomic_thread_fence(std::memory_order_seq_cst);
        const uint64_t u = upto.load(std::memory_order_relaxed);
        return u && held_upto >= u;
    }
    /// (a send, dev.present_mu held) the values up to sent are in the queue: owed no more, unless a later one is owed
    void met(uint64_t sent) {
        uint64_t u = upto.load(std::memory_order_relaxed);
        while (u && sent >= u && !upto.compare_exchange_weak(u, 0, std::memory_order_relaxed)) {}
    }
};
inline FlushOwed flush_owed;   // (vk_replay.cpp's)
}   // namespace mkwvk
