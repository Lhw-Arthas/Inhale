# Credits

Inhale is free software under the [GNU General Public License, version 3 or later](LICENSE) (GPL-3.0-or-later).

    Hookshot: Copyright (C) 2026 NotRexed and the Hookshot contributors
    Longshot: Copyright (C) 2026 the Longshot contributors
    Inhale:   Copyright (C) 2026 the Inhale contributors

## Notice of modification

Inhale is a modified version of Longshot (https://git.magicbean.dev/MagicBeanDev/Longshot), which is a modified
version of NotRexed's Hookshot (https://github.com/NotRexed/Hookshot); both were released under the GPL, version 3
or later. Inhale started on 2026-11-16 from Longshot's commit `31f8d8be2ef4a077a49562136ed8e16689a30483`. The files
taken, the files left out and the files changed on that date are listed in [PROVENANCE.md](PROVENANCE.md); every
change since is in this repository's history, with its date. Longshot and Hookshot are not responsible for Inhale,
and problems with Inhale are not to be reported to them.

Inhale includes code from Eden and suyu, which are under the GPL too. Third-party parts under other licences that
work with the GPL (Sirit, the Vulkan Memory Allocator, SDL, Opus, Dear ImGui, zstd, the Libertinus fonts, zbic and
the a64-kit tools) keep their own notices in their folders.

Inhale is an unofficial fan project, not affiliated with or endorsed by Nintendo or HAL Laboratory. Kirby and Kirby
and the Forgotten Land are trademarks of their owners. Inhale contains no game code, game data or keys, and nothing
made from them.

## People and projects

Inhale's tools, runtime and renderer are Longshot's, and exist thanks to the work of many people. This list is
carried over from Longshot's README at the commit above:

- **The Longshot contributors**: [Longshot](https://git.magicbean.dev/MagicBeanDev/Longshot), which Inhale is a
  fork of.
- **NotRexed**: [Hookshot](https://github.com/NotRexed/Hookshot), which Longshot is a fork of, BlueShell (Mario Kart
  World), Skybound (Tears of the Kingdom) and the a64-kit tools.
- **[Eden](https://git.eden-emu.dev/eden-emu/eden)** and **Eglantine**: the shader recompiler and Switch 2 shader
  work.
- **suyu**: the graphics decoders and the AArch64 translator.
- **[seedds/nxnative](https://github.com/seedds/nxnative)**: reference for how task and mesh shaders work.
- **[EvilBoyce / evilmfkr](https://github.com/evilmfkr/Hookshot)**: GPU culling, light probes, Horizon's mutex
  handoff and other fixes in the runtime and renderer.
- **[zortos293/Lichii](https://github.com/zortos293/Lichii)**: reference for Ampere shader lowering, and its
  compare-exchange retry fix.
- **[mstorsjo/llvm-mingw](https://github.com/mstorsjo/llvm-mingw)**: the Windows compiler the build can use.
- **NVIDIA DLSS**: builds made with NVIDIA's DLSS SDK (optional, never bundled) use NVIDIA DLSS Super Resolution,
  NVIDIA's technology. NVIDIA and DLSS are trademarks of NVIDIA Corporation.
- **AMD FSR 3.1 and FSR 4**: AMD FidelityFX Super Resolution 3.1 is built from AMD's MIT-licensed FidelityFX SDK
  shaders; FSR 4 (optional; AMD's libraries are never bundled) goes through AMD's MIT-licensed FSR API headers.
  Both are AMD's technology. AMD, Radeon and FidelityFX are trademarks of Advanced Micro Devices, Inc.
- **[kinnay/zbic](https://github.com/kinnay/zbic)**, **Opus** and **SDL**: decompression, audio and controllers.
- **[sostenesfreitas/ocarina-recomp](https://github.com/sostenesfreitas/ocarina-recomp)**: its notes confirmed the
  mesh stage's control section.
- **[MythosOfs/Orchid](https://github.com/MythosOfs/Orchid)**: a fog and exposure workaround Longshot used.
- **Mesa (NAK)**: the reference for Ampere's instruction encoding.
- Everyone who sent fixes to Hookshot and Longshot: SkippySteve, monsterlag, klimovich008, hckrman101, madebyjordan,
  N3oTraX, shayderrr, gab9281, Wpaif, nicholasgower, ZurielAtr, Joey-Magnus, Zorkats, d3zessete, chrispository,
  vzeol, leonidasmark, Segmentree, ShyVortex, hiKareeem and i900gaming, among others.
