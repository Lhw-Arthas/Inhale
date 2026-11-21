// (inhale) What the translator may put in a program by what the device has: 8- and 16-bit integers (shaderInt8,
// shaderInt16) and the 32-bit denorm modes (shaderDenormPreserveFloat32, shaderDenormFlushToZeroFloat32). upstream's
// profile (vk_shader.cpp make_profile) said every device had them, and a module that declares the Int8 or Int16 capability
// without the feature (VUID-VkShaderModuleCreateInfo-pCode-08740), or a denorm mode the device does not report, is invalid:
// the driver need not accept it. Without them Eden converts through 32 bits and leaves the mode out (emit_spirv.cpp
// SetupDenormControl). missing() goes into the program cache's stamp only when it is not 0, so every GPU that has all four
// keeps its cache. HeyListen 6f82d229 and the denorm part of 98f34e24 (GPL-3.0); tests/test_shader_caps_inhale.py
#pragma once
#include <cstdint>
#include <vulkan/vulkan.h>

struct InhaleShaderCaps {
    bool int8 = true, int16 = true, fp32_denorm_preserve = true, fp32_denorm_flush = true;
    uint32_t missing() const {   // (a bit each that the device lacks; 0 when it has all)
        return (int8 ? 0u : 1u) | (int16 ? 0u : 2u) | (fp32_denorm_preserve ? 0u : 4u) | (fp32_denorm_flush ? 0u : 8u);
    }
};

inline InhaleShaderCaps inhale_shader_caps(const VkPhysicalDeviceFeatures& f, const VkPhysicalDeviceVulkan12Features& f12,
                                           const VkPhysicalDeviceFloatControlsProperties& fc) {
    InhaleShaderCaps c;
    c.int8 = f12.shaderInt8 != VK_FALSE;
    c.int16 = f.shaderInt16 != VK_FALSE;
    c.fp32_denorm_preserve = fc.shaderDenormPreserveFloat32 != VK_FALSE;
    c.fp32_denorm_flush = fc.shaderDenormFlushToZeroFloat32 != VK_FALSE;
    return c;
}
