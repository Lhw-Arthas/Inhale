"""A draw that samples a colour target it writes is drawn into a copy of that target (gpu/vk/vk_feedback.h).

The game's lighting pass reads the light its G-buffer pass left in the scene's target and writes the lit colour over
it, in one full-screen draw. Sampling a texture while drawing into it is undefined in Vulkan; AMD's Windows driver
(Radeon 780M) then gave garbage in the 8x8 blocks where the draw's two triangles meet, which the game's bloom and lens
flare spread into coloured discs. This checks, with no game and no GPU:

- the draw (gpu/vk/vk_draw.cpp): once its pass is settled, the pass it draws in is begun with the targets
  feedback::begin gave it, outside a pass, and what it drew is copied back when the draw ends;
- which draws (gpu/vk/feedback_copy.h, built as C++ and run): the colour targets a draw both samples and writes, not
  its depth, not multisampled ones; on AMD's Windows driver unless RX_VK_FEEDBACK_COPY says otherwise;
- the copies (gpu/vk/vk_feedback.cpp, cut out by its text and run against stand-ins for the Vulkan calls it makes):
  the target is copied into the copy after a barrier and the draw given the copy's view; when the draw ends its pass
  is ended and the copy copied back into the target's level and layer; two targets of one draw get a copy each; a
  target that cannot be copied keeps its view; a copy that could not be made is not tried at every draw.

python -I -B tests/test_feedback_copy.py [--cxx g++] [--headers <Vulkan headers>]
"""
import argparse
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))   # (tests/srccut.py: python -I leaves this folder off the path)
from srccut import block   # noqa: E402

RUN_ALL_ARGS = ["--cxx", "{cxx}", "--headers", "{vulkan_headers}"]

ROOT = Path(__file__).resolve().parents[1]
VK = ROOT / "gpu" / "vk"

FIXTURE = r'''#include "feedback_copy.h"

#include <cstdio>

#define CHECK(name, condition) do { if (!(condition)) { std::fprintf(stderr, "FAIL %s at line %d\n", name, __LINE__); return 1; } } while (0)

int main() {
    namespace fc = mkwvk::feedback_copy;
    // (the masks are draw_hazards': colour target i is bit i, the depth target bit 8)
    CHECK("the lighting pass: samples and writes colour 0", fc::targets(true, 0x001, 0x001, true) == 0x001);
    CHECK("each such colour target", fc::targets(true, 0x00F, 0x005, true) == 0x005);
    CHECK("a target only sampled, or only written, is no feedback", fc::targets(true, 0x002, 0x001, true) == 0 &&
                                                                         fc::targets(true, 0, 0x0FF, true) == 0 &&
                                                                         fc::targets(true, 0x0FF, 0, true) == 0);
    CHECK("the depth target is left as it is", fc::targets(true, 0x100, 0x100, true) == 0 &&
                                                   fc::targets(true, 0x101, 0x101, true) == 0x001);
    CHECK("a multisampled pass is left as it is", fc::targets(true, 0x001, 0x001, false) == 0);
    CHECK("not asked for: nothing", fc::targets(false, 0x001, 0x001, true) == 0);
    // where: AMD's Windows driver, unless the switch says
    CHECK("AMD's Windows driver: on", fc::wanted(true, nullptr));
    CHECK("other drivers: off", !fc::wanted(false, nullptr));
    CHECK("RX_VK_FEEDBACK_COPY=1: on anywhere", fc::wanted(false, "1"));
    CHECK("RX_VK_FEEDBACK_COPY=0: off anywhere", !fc::wanted(true, "0"));
    CHECK("an empty value is not a choice", fc::wanted(true, "") && !fc::wanted(false, ""));
    std::printf("PASS: a draw that samples a colour target it writes draws into a copy\n");
    return 0;
}
'''


COPIES = r'''#include <vulkan/vulkan.h>

#include <algorithm>
#include <cstdarg>
#include <cstdio>
#include <cstdlib>
#include <functional>
#include <mutex>
#include <vector>

#include "feedback_copy.h"

// ---- stand-ins for what vk_feedback.cpp calls (vk_internal.h, vk_texture.h, vk_draw.h), each noting what it was asked ----
typedef struct VmaAllocation_T* VmaAllocation;
enum { kEndPass, kBarrier, kLayout, kCopy };
struct Event {
    int kind;
    VkImage src, dst;
    uint32_t src_level, src_layer, dst_level, dst_layer, width, height;
};
static std::vector<Event> events;
static int images_made, images_asked, images_destroyed, views_destroyed;
static bool make_fails;
static VkImageCreateFlags last_flags;
static VkImageUsageFlags last_usage;
static uint64_t frame_now = 100, gpu_done = 0;

namespace mkwvk {
struct Texture {
    VkImage image = VK_NULL_HANDLE;
    VkFormat format = VK_FORMAT_UNDEFINED;
    VkImageType type = VK_IMAGE_TYPE_2D;
    VkImageUsageFlags usage = 0;
    VkImageCreateFlags create_flags = 0;
    uint32_t width = 1, height = 1, levels = 1, layers = 1;
    VkSampleCountFlagBits samples = VK_SAMPLE_COUNT_1_BIT;
};
struct {
    VkDevice device = VK_NULL_HANDLE;
    VkDriverId driver_id = VK_DRIVER_ID_MESA_RADV;
} dev;
void logf(const char*, ...) {}
bool create_image(const VkImageCreateInfo& ci, VkImage& image, VmaAllocation& memory, bool = false, bool = false, bool = false) {
    images_asked++, last_flags = ci.flags, last_usage = ci.usage;
    if (make_fails) return false;
    image = (VkImage)(uintptr_t)(0x1000 + ++images_made), memory = (VmaAllocation)(uintptr_t)images_made;
    return true;
}
void destroy_image(VkImage, VmaAllocation) { images_destroyed++; }
uint64_t texture_frame_no() { return frame_now; }
uint64_t vk_retirement_value() { return 7; }
uint64_t vk_timeline_completed() { return gpu_done; }
void end_pass(VkCommandBuffer) { events.push_back({kEndPass, {}, {}, 0, 0, 0, 0, 0, 0}); }
void full_barrier(VkCommandBuffer, const char* = "") { events.push_back({kBarrier, {}, {}, 0, 0, 0, 0, 0, 0}); }
} // namespace mkwvk
extern "C" {
VKAPI_ATTR VkResult VKAPI_CALL vkCreateImageView(VkDevice, const VkImageViewCreateInfo* ci, const VkAllocationCallbacks*, VkImageView* view) {
    *view = (VkImageView)((uintptr_t)ci->image + 0x100000);   // (a view names its image, for the checks below)
    return VK_SUCCESS;
}
VKAPI_ATTR void VKAPI_CALL vkDestroyImageView(VkDevice, VkImageView, const VkAllocationCallbacks*) { views_destroyed++; }
VKAPI_ATTR void VKAPI_CALL vkCmdPipelineBarrier2(VkCommandBuffer, const VkDependencyInfo* di) {
    for (uint32_t i = 0; i < di->imageMemoryBarrierCount; i++)
        events.push_back({kLayout, {}, di->pImageMemoryBarriers[i].image, 0, 0, 0, 0, 0, 0});
}
VKAPI_ATTR void VKAPI_CALL vkCmdCopyImage(VkCommandBuffer, VkImage src, VkImageLayout, VkImage dst, VkImageLayout, uint32_t n,
                                          const VkImageCopy* r) {
    for (uint32_t i = 0; i < n; i++)
        events.push_back({kCopy, src, dst, r[i].srcSubresource.mipLevel, r[i].srcSubresource.baseArrayLayer,
                          r[i].dstSubresource.mipLevel, r[i].dstSubresource.baseArrayLayer, r[i].extent.width, r[i].extent.height});
}
}

// ---- vk_feedback.h's declarations and vk_feedback.cpp's code, as they are in the tree ----
namespace mkwvk {
@HEADER@
} // namespace mkwvk
@CODE@

#define CHECK(name, condition) do { if (!(condition)) { std::fprintf(stderr, "FAIL %s at line %d\n", name, __LINE__); return 1; } } while (0)

using namespace mkwvk;

static VkImage image_of(VkImageView v) { return (VkImage)((uintptr_t)v - 0x100000); }
static const VkImageUsageFlags kTarget = VK_IMAGE_USAGE_COLOR_ATTACHMENT_BIT | VK_IMAGE_USAGE_SAMPLED_BIT |
                                         VK_IMAGE_USAGE_TRANSFER_SRC_BIT | VK_IMAGE_USAGE_TRANSFER_DST_BIT;
static Texture target(uintptr_t image, VkFormat f, uint32_t w, uint32_t h, uint32_t levels = 1, uint32_t layers = 1) {
    Texture t;
    t.image = (VkImage)image, t.format = f, t.usage = kTarget, t.width = w, t.height = h, t.levels = levels, t.layers = layers;
    t.create_flags = VK_IMAGE_CREATE_MUTABLE_FORMAT_BIT | VK_IMAGE_CREATE_EXTENDED_USAGE_BIT;
    return t;
}
struct Pass {   // (a draw's colour targets, as vk_draw.cpp's Targets holds them)
    Texture* color[8]{};
    VkImageView color_view[8]{};
    VkFormat color_format[8]{};
    uint32_t color_level[8]{}, color_layer[8]{};
    void set(int i, Texture* t, uint32_t level = 0, uint32_t layer = 0) {
        color[i] = t, color_view[i] = (VkImageView)((uintptr_t)t->image + 0x900000), color_format[i] = t->format;
        color_level[i] = level, color_layer[i] = layer;
    }
};
static bool begin(feedback::Draw& d, Pass& p, uint16_t targets, uint32_t w, uint32_t h) {
    return feedback::begin(d, (VkCommandBuffer)0x42, targets, p.color, p.color_view, p.color_format, p.color_level, p.color_layer, w, h);
}

int main() {
    const VkFormat hdr = VK_FORMAT_B10G11R11_UFLOAT_PACK32;
    {   // the lighting pass: one target, sampled and written
        Texture scene = target(0x10, hdr, 2560, 1440);
        Pass p;
        p.set(0, &scene);
        const VkImageView own = p.color_view[0];
        VkImage copy = VK_NULL_HANDLE;
        {
            feedback::Draw d;
            CHECK("the draw is given a copy", begin(d, p, 1, 2560, 1440) && p.color_view[0] != own);
            copy = image_of(p.color_view[0]);
            CHECK("a copy that can be drawn into and copied both ways, made as the target was",
                  (last_usage & (VK_IMAGE_USAGE_COLOR_ATTACHMENT_BIT | VK_IMAGE_USAGE_TRANSFER_SRC_BIT | VK_IMAGE_USAGE_TRANSFER_DST_BIT)) ==
                          (VK_IMAGE_USAGE_COLOR_ATTACHMENT_BIT | VK_IMAGE_USAGE_TRANSFER_SRC_BIT | VK_IMAGE_USAGE_TRANSFER_DST_BIT) &&
                      last_flags == scene.create_flags);
            CHECK("barrier, the copy's layout, then the target into the copy",
                  events.size() == 3 && events[0].kind == kBarrier && events[1].kind == kLayout && events[1].dst == copy &&
                      events[2].kind == kCopy && events[2].src == scene.image && events[2].dst == copy &&
                      events[2].width == 2560 && events[2].height == 1440);
            events.clear();
        }
        CHECK("at the draw's end: the pass ended, a barrier, the copy back into the target",
              events.size() == 3 && events[0].kind == kEndPass && events[1].kind == kBarrier && events[2].kind == kCopy &&
                  events[2].src == copy && events[2].dst == scene.image && events[2].width == 2560 && events[2].height == 1440);
        events.clear();
        {   // the next frame's draw: the same copy, not another image
            Pass q;
            q.set(0, &scene);
            feedback::Draw d;
            CHECK("the copy is kept for the next such draw", begin(d, q, 1, 2560, 1440) && image_of(q.color_view[0]) == copy && images_made == 1);
        }
        events.clear();
    }
    {   // a draw with nothing to copy: nothing recorded, and its end leaves the pass alone
        Texture scene = target(0x11, hdr, 2560, 1440);
        Pass p;
        p.set(0, &scene);
        const VkImageView own = p.color_view[0];
        {
            feedback::Draw d;
            CHECK("no target asked for: none replaced", !begin(d, p, 0, 2560, 1440) && p.color_view[0] == own);
        }
        CHECK("and nothing recorded, the pass not ended", events.empty());
    }
    {   // a level and layer of a larger texture: copied from there, and back there
        Texture mips = target(0x12, hdr, 1024, 512, 4, 6);
        Pass p;
        p.set(0, &mips, 2, 5);
        VkImage copy;
        {
            feedback::Draw d;
            CHECK("a level's size", begin(d, p, 1, 256, 128));
            copy = image_of(p.color_view[0]);
            CHECK("from the level and layer", events.back().kind == kCopy && events.back().src == mips.image && events.back().src_level == 2 &&
                                                  events.back().src_layer == 5 && events.back().dst_level == 0 && events.back().dst_layer == 0);
            events.clear();
        }
        CHECK("and back to them", events.back().kind == kCopy && events.back().src == copy && events.back().dst == mips.image &&
                                      events.back().dst_level == 2 && events.back().dst_layer == 5 && events.back().width == 256);
        events.clear();
    }
    {   // two targets of one draw, alike: a copy each, each back into its own
        Texture a = target(0x13, hdr, 640, 360), b = target(0x14, hdr, 640, 360);
        Pass p;
        p.set(0, &a), p.set(1, &b);
        VkImage ca, cb;
        {
            feedback::Draw d;
            CHECK("both replaced", begin(d, p, 3, 640, 360));
            ca = image_of(p.color_view[0]), cb = image_of(p.color_view[1]);
            CHECK("two targets of one draw do not share a copy", ca != cb);
            events.clear();
        }
        int back_a = 0, back_b = 0;
        for (const Event& e : events) back_a += e.kind == kCopy && e.src == ca && e.dst == a.image, back_b += e.kind == kCopy && e.src == cb && e.dst == b.image;
        CHECK("each copied back into its own target", back_a == 1 && back_b == 1);
        events.clear();
    }
    {   // what a plain copy cannot take keeps its view, and the other target of the draw is still served
        Texture ms = target(0x15, hdr, 640, 360), volume = target(0x16, hdr, 640, 360), locked = target(0x17, hdr, 640, 360),
                other = target(0x18, hdr, 320, 180), good = target(0x19, hdr, 640, 360);
        ms.samples = VK_SAMPLE_COUNT_4_BIT, volume.type = VK_IMAGE_TYPE_3D, locked.usage &= ~(VkImageUsageFlags)VK_IMAGE_USAGE_TRANSFER_DST_BIT;
        Pass p;
        p.set(0, &ms), p.set(1, &volume), p.set(2, &locked), p.set(3, &other), p.set(4, &good);
        const Pass before = p;
        {
            feedback::Draw d;
            CHECK("the one that can be copied", begin(d, p, 0x1F, 640, 360) && p.color_view[4] != before.color_view[4]);
            for (int i = 0; i < 4; i++) CHECK("multisampled, 3D, not copyable, another size: as they are", p.color_view[i] == before.color_view[i]);
        }
        events.clear();
    }
    {   // a copy that cannot be made: the draw is left as it is, and the driver is not asked again at every draw
        Texture wide = target(0x1A, hdr, 3840, 2160);
        make_fails = true;
        const int asked = images_asked;
        for (int n = 0; n < 3; n++) {
            Pass p;
            p.set(0, &wide);
            const VkImageView own = p.color_view[0];
            feedback::Draw d;
            CHECK("no copy: the target's own view", !begin(d, p, 1, 3840, 2160) && p.color_view[0] == own);
        }
        CHECK("asked of the driver once", images_asked == asked + 1);
        make_fails = false;
        CHECK("and nothing recorded for it", events.empty());
    }
    {   // more sizes than are kept: the oldest goes, but only once the GPU is past the work that may use it
        const int destroyed = images_destroyed;
        for (uint32_t n = 0; n < 8; n++) {
            Texture t = target(0x20 + n, hdr, 100 + n, 50);
            Pass p;
            p.set(0, &t);
            frame_now++;
            feedback::Draw d;
            CHECK("each size its copy", begin(d, p, 1, 100 + n, 50));
        }
        CHECK("none destroyed while the GPU may still use it", images_destroyed == destroyed);
        frame_now += 10, gpu_done = 7;
        Texture t = target(0x30, hdr, 100, 50);
        Pass p;
        p.set(0, &t);
        feedback::Draw d;
        begin(d, p, 1, 100, 50);
        CHECK("destroyed once it is done", images_destroyed > destroyed && views_destroyed > 0);
    }
    std::printf("PASS: the target is copied in, drawn aside and copied back\n");
    return 0;
}
'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cxx", default="g++")
    parser.add_argument("--headers", type=Path, help="the Vulkan headers, where the compiler does not find them itself")
    args = parser.parse_args()

    # the draw: its pass is begun with the copy in place of each colour target it samples and writes
    source = (VK / "vk_draw.cpp").read_text(encoding="utf-8")
    draw = block(source, "void draw(VkCommandBuffer cmd, NvnState& s, const DrawArgs& d) {")
    settled = draw.index("writes = draw_hazards(cmd, p, s, at, samples);")
    if "feedback::begin(" not in draw:
        raise SystemExit("draw: a draw that samples a colour target it writes is drawn into that target itself "
                         "(feedback::begin is not called: no copy)")
    begin = draw.index("feedback::begin(")
    if begin < settled:
        raise SystemExit("draw: the copy is made before the draw's pass is settled (draw_hazards)")
    if "feedback_copy::targets(" not in draw[settled:begin]:
        raise SystemExit("draw: which targets are copied is not asked of feedback_copy::targets")
    if "end_pass(cmd);" not in draw[settled:begin]:
        raise SystemExit("draw: the target is copied inside a pass")
    passes = [at for at in range(len(draw)) if draw.startswith("begin_pass(cmd, ", at)]
    if not passes or any(at < begin for at in passes):
        raise SystemExit("draw: a pass is begun before the copy is made")
    if any(not draw.startswith("begin_pass(cmd, *at_pass);", at) for at in passes):
        raise SystemExit("draw: a pass of the draw is begun with the game's targets, not with the copy's")
    # (what the draw drew is copied back when the draw ends, on every way out of it: the guard's destructor)
    if "feedback::Draw " not in draw or draw.index("feedback::Draw ") > begin:
        raise SystemExit("draw: nothing copies back what was drawn when the draw ends (feedback::Draw)")
    for guard in ("} mask_guard;", "} each_guard;"):   # (destroyed in reverse order: the copy back comes first)
        if draw.index("feedback::Draw ") < draw.index(guard):
            raise SystemExit("draw: %s reads the target before what was drawn is copied back" % guard.strip("} ;"))

    if "at_pass = &*at_copy;" not in draw[begin:passes[0]]:
        raise SystemExit("draw: the copy's targets are never the ones the pass is begun with")

    # the copies: vk_feedback.cpp's own code, with stand-ins for what it calls
    header = block((VK / "vk_feedback.h").read_text(encoding="utf-8"), "namespace feedback {")
    code = block((VK / "vk_feedback.cpp").read_text(encoding="utf-8"), "namespace mkwvk::feedback {")
    copies = COPIES.replace("@HEADER@", header).replace("@CODE@", code)

    with tempfile.TemporaryDirectory(prefix="feedback-copy-") as tmp:
        for name, text in (("rule", FIXTURE), ("copies", copies)):
            cpp = Path(tmp) / (name + ".cpp")
            exe = Path(tmp) / name
            cpp.write_text(text, encoding="utf-8")
            # (-Wno-missing-field-initializers: the renderer writes Vulkan's structures as {sType}, as its build takes them)
            subprocess.run([args.cxx, "-std=c++20", "-Wall", "-Wextra", "-Werror", "-Wno-missing-field-initializers",
                            "-I", str(VK), *(["-I", str(args.headers)] if args.headers else []), str(cpp), "-o", str(exe)],
                           check=True)
            subprocess.run([str(exe)], check=True)


if __name__ == "__main__":
    main()
