// (inhale) Which draws are drawn into a copy of a target they sample (vk_feedback.h), and on which drivers. Plain code
// with no Vulkan calls: tests/test_feedback_copy.py builds it alone.
#pragma once
#include <cstdint>

namespace mkwvk::feedback_copy {

/// The colour targets a draw both samples and writes, as bits (target i is bit i), from draw_hazards' masks (vk_draw.cpp:
/// the depth target is their bit 8, and stays as it is: nothing was seen wrong with it). None where it is not asked for
/// (wanted, below), nor in a multisampled pass, whose targets a plain copy cannot take.
inline uint16_t targets(bool asked, uint16_t samples, uint16_t writes, bool one_sample) {
    return asked && one_sample ? (uint16_t)(samples & writes & 0xFF) : (uint16_t)0;
}

/// On AMD's Windows driver, the one seen to go wrong (a Radeon 780M, driver 26.11.2: vk_feedback.h); the other drivers
/// tried draw it right, and the copies cost them GPU time for nothing. RX_VK_FEEDBACK_COPY=1 or 0 says so on any driver.
inline bool wanted(bool amd_windows_driver, const char* env) {
    if (env && *env) return env[0] != '0';
    return amd_windows_driver;
}

} // namespace mkwvk::feedback_copy
