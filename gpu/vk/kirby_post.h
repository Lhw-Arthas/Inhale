// (inhale) The Depth of field row (opts.dof) for Kirby and the Forgotten Land, Switch 2 Edition: docs/design.md, "issue #1,
// the depth-of-field switch". The game's DoF is shader/DepthOfField/DepthOfField.bfsha of its data title: three programs, a
// vertex stage of their own and three fragment stages. In the first level only the composite runs (program
// 0383c5894eee303d), which blends the blurred picture into the scene's target by depth; with its draws left out the scene
// stays sharp and every later pass reads the same target. The keys are the fragment stages' code keys (vk_shader.cpp
// code_key: FNV-1a over the control section and the code), hashes of the game's shaders and no game data: another game's
// programs do not have them, so the list needs no build id gate.
#pragma once

#include <cstdint>
#include <mutex>
#include <string>
#include <unordered_map>

#include "skip_code.h"

namespace mkwvk::kirby_post {

/// The DoF programs' fragment code keys, as RX_VK_SKIP_CODE takes them
inline constexpr const char* kDofCodes = "976a0ce23a971ed0,912173d38909e3fd,3fe01c0d0629e41f";

/// Whether the program (its key) is one of the DoF programs; codes() gives its stage code keys as program_code_keys
/// writes them, asked once a program
template <class Codes>
bool is_dof(uint64_t program, Codes codes) {
    static std::mutex mu;
    static std::unordered_map<uint64_t, bool> memo;
    std::lock_guard lk(mu);
    const auto it = memo.find(program);
    if (it != memo.end()) return it->second;
    const std::string c = codes();
    return memo.emplace(program, skip_code::matches(c, kDofCodes)).first->second;
}

}  // namespace mkwvk::kirby_post
