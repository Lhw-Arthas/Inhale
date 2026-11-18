# Inhale: design

## 1. Goal and approach

A PC port of *Kirby and the Forgotten Land, Nintendo Switch 2 Edition + Star-Crossed World* by static recompilation,
following Longshot (GPL-3.0-or-later): Python tools lift AArch64 to C, clang compiles it, a native Horizon OS and
NVN2 runtime in C hosts it, and a Vulkan back end replays the NVN2 call stream. No CPU or GPU emulation.

The user supplies their own `.nup` package or extracted `exefs/` and `romfs/`. The repository holds no game files,
keys, or anything made from them, and its documents do not explain how to obtain or dump a game.

Decisions:

- One import of Longshot's tree at commit `31f8d8be`, with identical paths (`PROVENANCE.md`).
- Linux first. Longshot's Windows paths stay in the tree, unverified.
- The project's name through the tree is changed by a script, `scripts/rename_full.py` (S6; until then only the
  player-facing names and the dump variables were changed). It is one rule, so `scripts/sync_upstream.py` puts
  Longshot's files through it before merging them, and Longshot's later changes keep applying.
- This game's code goes in files of its own (`host/kirby_*.c`, `nx2/kirby_*.py`). The other game's code (`oot_*`)
  is gated on that game's build id, not deleted: deleting the host files breaks the link.
- First goal: the first rendered frame (stage S3).

## 2. What the package is

Measured by reading the package in place.

| Item | Value |
|---|---|
| Package | one `.nup`, 15424373958 bytes, 2 titles. Its file name has a non-ASCII character: never hardcode the path |
| Title 0 (code) | `04004d300c5ae001` v65536: `main` 22.9 MB, `sdk`, `subsdk0`, `rtld`, `main.npdm`; its romfs is empty |
| Title 1 (data) | `01004d300c5af001` v0: no exefs, romfs with 11326 files, 11.60 GB (the add-on's levels included) |
| Platform | Native Switch 2: program id prefix 04, no Switch 1 ACID, no `nvdrv` or `vi:u`, DT_RELR in all modules, PAC, LSE and LDAPR in the code, NVN names with DLSS |
| Modules | plain `NSO0` (LZ4), not ZBIC. The build id of `main` starts `395fc326` |
| Size | about 4.9 M instructions in total (Longshot's game: 17.7 M) |
| SDK | 19.3.7 (Longshot's game: 22.2.8). Middleware: G3d, Ui2d, Vfx2, Atk2, movie, NEX 4.6.10, PhysX 5.2.0; `subsdk0` is NVIDIA CUDA |
| Data formats | `.cmp` (a u32 and an LZ4 frame), `.webm` with VP9, `.opus`, `.bfstm`, `.bfsar`, 36 small `.bfsha` |

The package path comes from the `INHALE_NUP` environment variable or from the git-ignored `work/nup.txt`.

## 3. Stages

Each stage has an exit check. Its command output is kept under the git-ignored `work/runs/`.

**S0: the tools accept this package.** The game-free tests have 0 failures; the third-party hashes pass; the package
listing shows both titles; the code signals all say Switch 2; the build id of `main` starts `395fc326`.

**S1: lift everything and prove it.** 100% of the discovered instructions are translated; no indirect branch without
a jump table; every instruction form is bit-exact against Unicorn; every comparable function is identical. From the
import list: the use of `nn::aoc` and `MountAddOnContent`, what `main` imports from `subsdk0`, the VP9 and `nfp`
names, and the symbols no module provides.

**S2: the standalone program boots to graphics start-up.** The lift prints both thread hooks non-zero; the log shows
`boot:` lines for the libc inits, `nnosInitialize`, `nninitStartup`, every `DT_INIT` including `subsdk0`, and
`nnMain`; the game reaches `nvnBootstrapLoader`.

**S3: first frame.** A PNG shows the first logo or loading screen, and the list of NVN procs with no host
implementation that the game called is recorded here.

**S4: title and menus** (outline). Scripted input (`HOS_INPUT_SCRIPT`), one VP9 movie plays, a save round trip.

**S5: gameplay** (outline). The first level without flashes (`RX_VK_FLASH=1`), one add-on map loads, a profile with
`HOS_SAMPLE` and `scripts/prof.py`.

**S6: PC features and packaging.** `nx2/make_game.py` builds a game folder from the package, and the folder's
program starts with no arguments; a hot list and a profile for this game, with their effect measured; the in-game
menu shows no row or text of the other game; one scripted full rename, after which the tests pass and a second run
of the script changes nothing.

## 4. The lessons from MKW, as rules here

Carried over from Longshot's design notes, where each of them cost days in the project before it. They are the checks
that keep the renderer right for another game; `tests/test_doc_anchors.py` keeps the functions that enforce them
pointing here.

1. **Cross-queue `nvnCommandBufferWaitEvent` is honoured.** A game's queues pass stages back and forth with events;
   replaying them in arrival order on one Vulkan queue flashes. `gpu/vk/vk_replay.cpp` `submit_job` replays each
   submission as far as its waits allow, with per-queue state (`RX_VK_EVENT_WAITS=0` turns it off, for A/B only).
   *Check early:* log the game's queues and event waits on the first boot.
2. **Nothing the replay reads comes from live guest memory.** Games write per-frame data ahead of the GPU: every
   read is from submit-time captures, and pools are captured from their creation, not their first GPU use
   (`gpu/vk/vk_memory.cpp`, `RX_VK_CAPTURE_POOL_MB`). *Check:* the mirror sync log's live-sync count stays near 0.
3. **Texture and sampler registrations are queued in order with the submits**, never applied out of band.
4. **GPU timestamps drive dynamic resolution.** A game with a resolution controller is fed by timestamp reports: the
   GPU time the replay reports (`gpu/vk/vk_replay.cpp` `NOP_REPORT_COUNTER`, scaled by `RX_VK_TS_SCALE`) must be
   scaled so the controller settles where the PC is, not at its floor. *Check:* the render size it picks over time.
5. **Clears after draws, and draws that sample a target their pass already wrote (or write one an earlier draw of the
   pass sampled), get passes of their own** (`gpu/vk/vk_draw.cpp` `clear_after_draws`, `draw_hazards`). A draw that
   samples a target it writes itself stays in the pass.
6. **2D views of 3D textures need `VK_EXT_image_2d_view_of_3d`.**
7. **The CPU saturates first.** The game's threads, the replay, captures and pipeline compiles share the cores, and
   extra helper threads have lowered the frame rate before. Thread counts are measured, never raised by default
   (`HOS_VCORES`, `RX_VK_CAPTURE_THREADS`, `HOS_THREAD_TIMES=<seconds>`, the `HOS_SAMPLE` profiler with
   `scripts/prof.py`).

Also inherited: hooks at fixed guest addresses belong to one game and are gated on that game's build id
(`hos_game_is_mkw`, `hos_game_is_oot`). This game's `main` overlaps the other games' address ranges, so an ungated
address compare can fire by coincidence.

## 13. Frame generation's presents, as rules

Carried over from Longshot's design notes as they are at `9af4808f`, under Longshot's number: the renderer's code
points here by it (`// doc: docs/design.md#13-frame-generations-presents-as-rules`, which `tests/test_doc_anchors.py`
checks), and that code is Longshot's. Longshot checked them on 2026-11-16 (Windows 11, RTX 5090, NVIDIA 621.24,
5120x2160 at 165 Hz with G-Sync, DLSS Frame Gen at 3x and 4x, PresentMon 2.3.0); none of it has been measured with
this game. Each fault these rules keep away looked like frame generation turned off: the FPS counter and the display
thread's own counts said the frames were made and on time, and the screen showed the game's frame rate.
`tests/test_framegen_fixed_pace.py` runs the timing functions through a model of the display loop. Longshot's notes
also name its method for rule 1 (its measure skill), which is not carried here.

1. **Frame pacing is measured on the screen, not in the log.** The display thread's `frame interpolation: ... shown on time`
   and `shown apart` counts are its present calls. After the call a present can still wait for the GPU: on 2026-11-16 the
   log had no late frame while PresentMon showed 32% (3x) and 45% (4x) of the frames on the screen under 2 ms. Read
   PresentMon's `DisplayedTime` (the share under 2 ms, its p10 to p90) and, for where a frame waited, `DisplayLatency` against
   `CPUBusy` (the call) and `GPULatency` + `GPUTime` (its GPU work).
2. **A fixed multiplier's set is shown on the game's timeline, in every present mode** (`gpu/vk/vk_framegen.cpp`
   `fixed_on_timeline`, `fixed_dues`, `pace_lead`), whatever Frame pacing says. An immediate (V-Sync Off) swapchain shows
   each present at once: a set presented as it came (its made frames and the game's within a millisecond) showed the
   game's frame and hardly the made ones. Evenly apart (the smoothed frame time over the set) the motion stutters as much
   as the game's frame times vary; on the game's timeline each frame moves as far as its time. Under FIFO (V-Sync On) a VRR
   display shows each present when it comes, one a refresh at most: as they came, a set's frames were a refresh apart and
   its last one waited for the next set (3x at 60 fps on 240 Hz: 4.2, 4.2 and 8.3 ms), so there a frame goes at its time
   but no sooner than a refresh after the one before was given (`fifo_slot`). `RX_VK_FG_TIMELINE=0` gives the old way
   back, for an A/B.
3. **The GPU's delay is fed back only from sets taken as they came** (`pace_delay`, `display_main`'s `as_came`). A set's
   frames are done with the game frame's GPU work, so its times wait for that (`fg.late_ns`). A set whose copies went to the
   GPU late for another reason (no swapchain image free, the display thread busy with the set before) would raise the delay
   by its own lateness, which sends the next set's copies later still: at 4x it ran to a whole game frame.
4. **A set presented ahead needs a frame slot per frame of both sets in flight, and two sets' spare swapchain images**
   (`gpu/vk/vk_replay.cpp` `present_slots_for`, `gpu/vk/vk_main.cpp` `create_swapchain`, `present_ahead_wanted`). Each present
   waits for the copy last made in its slot: with fewer slots than a set's frames, its 4th copy waited for its own first
   copy, and with a slot per frame of one set the next set's copy k waited for the shown set's copy k, each so for all the
   game's work queued before it, while frames of the shown set were due. The slot count is the swapchain's
   (`dev.swap_slots`), set when it is made for its sets, in every present mode; `RX_VK_FG_TIMELINE=0` keeps 3. An app may hold at most
   imageCount - minImageCount acquired images (an NVIDIA surface: 8 images, 6 spare): the next set's copies go as images
   come free (`copy_up_to`), never all or none. The slots are also how many copies may still be on the GPU: what a copy
   reads lives through `kPresentSlotsMax` presents after it (the overlays' staging buffers and old textures,
   `gpu/vk/vk_imgui.cpp` `kFramesLater`; Dear ImGui's vertex buffers, `ImageCount`). At 4, frame generation at 3x and up
   let them go while copies could still read them (a test-only log showed it on an RTX 5090; a likely cause of a
   tester's lost device on an RTX 5080, not reproduced).
5. **A present waits on the queue it is made on.** On the replay's graphics queue it waits behind the game's next frame (3 to
   12 ms at 5120x2160), and a second queue of the graphics family takes turns with it on the GPU. A compute family's queue
   runs beside it (`RX_VK_PRESENT_QUEUE`, `vk_main.cpp` `create_device`): 0.1% of the frames under 2 ms, on the screen 4.9
   to 6.9 ms apart at 3x (p10 to p90), each present's call to the screen 1.3 ms instead of 6.6. It is on by default
   with NVIDIA's driver 621.24 and newer on Windows, where it was measured; Hookshot issue 1161, before the fork (an
   RTX 4090 on NVIDIA's 621.14 had a black screen with it on), was never placed, so older drivers, other drivers and
   Linux keep the replay's queue until they are measured, and `=0` is the way back.
6. **Under FIFO the made frames do not queue** (`gpu/vk/vk_framegen.cpp` `fifo_catch_up`, `fifo_pick`,
   `gpu/vk/vk_reflex.cpp` `fifo_min_interval_us`). FIFO shows one frame a refresh: when the game's frame rate times the
   multiplier passes the refresh, the frames queue in the sets taken ahead and their refresh slots, the game is held
   back, and each game frame reaches the screen later and later (RTX 5090, 165 Hz: 3x, 40 to 51 ms after its hand-over
   before the timeline under FIFO and 65 to 82 ms with it; at 2x under the refresh, 15 and 22 ms; 6x, the game held to
   27.5 game frames a second (45.7 with V-Sync Off) and each game frame presented 138 ms after its hand-over). FIFO's catch-up (`display_main`'s `take`): a set
   whose game frame, its last, would be shown over a refresh after its own time keeps the most frames that bring it
   within one, the ones left out spread over the set so the picture moves in even steps (6x with 3 shown: the 2nd, 4th
   and 6th), and their copies are not made, so no image is held for them. Past the refresh the screen then shows 160 to
   165 frames a second at 165 Hz, each game frame within a refresh of its time, the game at its own rate (the model in
   `tests/test_framegen_fixed_pace.py`: 3x, 4x and 6x at 33 to 60 game frames a second; in the game, 6x: the game at
   52 to 55 frames a second and each game frame on screen 46 to 52 ms after its hand-over). At most all but one made frame is left out:
   at 2x the one made frame stays, as a set of one frame is not presented ahead. The GPU's delay is fed back against
   the set's first frame whichever frames are shown: a copy takes as long for any of them, and against the first one
   shown 6x ran the delay down to 0, so its frames came due before their copies and a frame more a set was left out.
   For a G-SYNC or
   FreeSync display, `RX_VK_FG_FIFO_CAP=1` has NVIDIA Reflex's sleep, while frames are made, hold the game to the
   multiplier's share of refresh - refresh²/3600 frames a second (157 at 165 Hz: 52.5 game frames at 3x), as NVIDIA's
   own Reflex keeps a G-SYNC display under the refresh with V-Sync (with the first catch-up, 3x on 165 Hz: 29 ms on
   screen with a 60 cap against main's 45 to 51 before the timeline under FIFO, and 39 uncapped against 33 to 40). It is off by default: a
   display of a fixed refresh then has refreshes without a new frame (7 a second at 165 Hz), and the game cannot tell
   the two apart.

## 5. Risks, ranked, with the stage that settles each

1. The data lives in a second, romfs-only title: certain to need work. S1 (imports), S2 (the first `fs:` lines).
2. SDK 19.3.7 against a runtime fitted to SDK 21 and 22: thread layout, hooked names that moved, NVN version. S1 to S3.
3. `subsdk0` is NVIDIA CUDA: its init runs at boot, and it may hold instruction forms the lifter lacks. S1, S2.
   Fallback: make its init fail so that PhysX stays on the CPU (untested).
4. DLSS and acceleration-structure NVN procs have no host implementation; harmless unless called. S3, settled by S5.
5. Shader lowering for this engine's programs. S3.
6. The VP9 movie function names may differ in SDK 19; `HOS_NO_MOVIES=1` goes around them until S4.
7. Engine script or dispatch code that makes indirect branches without tables. S1.
8. NEX and the network services answered by stubs that return 0. S4.
9. `mii`, `nfc`, `ngc`, `nim`, `notif`, `ectx` have neither hooks nor stubs. S4 or S5.

## 6. Reused unchanged from Longshot

`nx2/nso2.py`, `image.py`, `insn.py`, `lift_fixes.py`, `poll.py`, `rtgen.py`, `standalone.py`, `build.py`,
`census.py`, `imports.py`, `test_insn.py`, `test_leaf.py`; `third_party/a64-kit`; `tests/run_all.py`;
`scripts/check_third_party.py`, `scripts/inhale_ctl.py`, `scripts/prof.py`; all of `gpu/vk`; `host/nn_video.c`,
`nn_codec.c`, `nn_audio.c`, `nn_fs.c`, `hos_svc.c`, `control.c`.

## 7. Not verified yet

- What `subsdk0` (CUDA) does after its init: its `DT_INIT` runs, but no `cu*` call has been seen yet.
- The NVN API version this game's `sdk` expects, and the SDK 19 thread layout beyond a clean start of the game's threads.
- The shader container type: the three `.bfsha` files looked at carry neither `Nin_NX_NVN` nor `Nin_Ounce_NVN2`.
- Why the presents sometimes drop to 7 a second while the movie player starts (S4, section 9): seen twice, not explained.
- One of three runs sampled with `HOS_SAMPLE_ALL` (`work/runs/s5x/c4.txt`) fell below 6 presents a second at the first zone
  change and stayed there; no unsampled run did. The sampler unwinds inside a signal handler: suspected, not proven.
- That a Star-Crossed World stage (`DlcLevelN`) loads and draws: needs a save past the first world.
- The Windows build, on Windows 11 with Visual Studio Build Tools 2022, LLVM's clang and FFmpeg from vcpkg
  (`x64-windows-static-md`, in a CPM-style folder named by `RX_CPM`): `tests/run_all.py` passes (3 checks that build the
  lifter fail only with MinGW's clang first on `PATH`; they pass with the Visual Studio environment), `nx2/build.py
  --standalone` links `inhale.exe` and `inhale_vk.dll`, and the game runs through the boot and the first scene on an
  RTX 2080 SUPER at 60 presents a second, with nothing in the log but the usual unimplemented imports. Not yet looked at
  on screen: which scene that is, input, audio, the movie. The llvm-mingw route (`LONGSHOT_MINGW`) builds and runs too
  (section 9, "the release packages").
  Slow in a window over Remote Desktop (21 to 25 presents a second, the main thread blocked 3.7 s of every 5 s in GPU sync
  waits while the GPU was busy 4 ms a frame): the same build run headless over ssh gives 60.0 with 0.1 s blocked. The
  remote display adapter paces FIFO presents (V-Sync On); the registry value `DWMFRAMEINTERVAL` = 15 (the RDP frame
  interval, as the user set it) fixed it: 60 in the window afterwards (the player's report). Not a defect of the host or the renderer.
- `make_game.py`'s `--romfs-from` and its folder input (`--game <folder>`, `--exefs` with `--aoc`) on a real dump:
  covered by tests with made-up files only. The package path and `--update` were run for real (section 9, S6).
- Whether the profiles add anything to the hot list: the three measured runs differ more among themselves than from
  the hot list's (section 9, S6).
- The menu rows kept for this game that were not tried in play: Mouse camera, Button prompts, Walk mode, and Output
  resolution on a screen that is not 16:9. The microphone rows are hidden for this game instead: it imports the SDK's
  input-stream API but no game code calls it (section 9, "the microphone rows").

## 8. Status

| Stage | State | Notes |
|---|---|---|
| Import | done 2026-11-16 | Longshot `31f8d8be`; two commits |
| S0 | done 2026-11-16 | tests 575 passed, 0 failed (522 without the system's Vulkan and SPIR-V headers); six signals say Switch 2 |
| S1 | done 2026-11-16 | 4801605 instructions, 100% translated; instruction and function tests pass; one unbounded jump table, in `rtld` |
| S2 | done 2026-11-17 | every `boot:` line, `nnMain`, NVN device, pools, 3840x2160 window textures; the game then loads from `aoc1:` |
| S3 | done 2026-11-17 | 60 presents a second; the online and difficulty screens draw; no NVN proc without a host implementation was called |
| S4 | done 2026-11-17 | scripted input; the opening movie plays (2296 pictures, with its sound); the game's sound plays; a save is read back at the title screen |
| S5 | done 2026-11-17 | the first stage at 60 presents a second, the beach into the jungle with 0 flashes (`RX_VK_PIPE_SKIP=0` by default); the hint movies play; all data loads from `aoc1:`; a profile; tests 575 passed |
| S6 | done 2026-11-17 | `make_game.py` from the package to a folder that starts with no arguments (60 presents a second); a hot list (CPU time down 10%) and profiles; the menu without the other game's rows; the name changed by `scripts/rename_full.py`; tests 575 passed |

Work after the two import commits is in five commits: the rename alone (what `scripts/rename_full.py --write` does
to the tree before it, with the script, and nothing else); the fork's documents and the files changed at import
(`PROVENANCE.md`); the stages S0 to S6; the sync script; the notes for coding agents.

## 10. The release packages

Three downloads, made by `.github/workflows/release.yml` on Linux runners (a `v*` tag: a release; a push to `main` or
Run workflow: the rolling `nightly` prerelease, with `SHA256SUMS`, unsigned):

- `Inhale-x86_64.AppImage` (`packaging/linux/`, built in an Ubuntu 22.04 container by `packaging/linux/docker.sh`).
  The container's image is built once per `packaging/linux/Dockerfile` by `.github/workflows/pkg-image.yml` and pushed
  to `ghcr.io/<owner>/inhale-pkg-build:<first 16 hex digits of the Dockerfile's SHA-256>`; the release jobs pull that
  tag, so a release does not reach Launchpad (the toolchain PPA, which failed three release runs in a row) or the
  Ubuntu mirrors. A Dockerfile with no image pushed yet is built by the release run itself.
  Its AppDir: `usr/python` (CPython 3.12 with tkinter and `requirements.txt`), `usr/lib/inhale/{llvm,sysroot,ffmpeg,
  sdl2,cpm}` (clang and lld, the glibc 2.35 sysroot, static FFmpeg with dav1d, `libSDL2-2.0.so.0`, the Vulkan, SPIR-V
  and VMA headers), `usr/share/inhale` (the tracked sources, `VERSION`, `liba64emit.so`, zbic, the prebuilt
  third-party objects, `packaging/gui`, `licenses/`). `AppRun` starts the window, `--cli` runs `make_game.py` and
  `--play` the game, with the tools' variables (`EMSDK`, `INHALE_SYSROOT`, `INHALE_FFMPEG`, `INHALE_SDL2`, `RX_CPM`)
  set as `packaging/gui/tools_env.py` sets them for the window's build.
- `Inhale-Setup-x64.exe` (`packaging/windows/`, cross-built on Linux: `packaging/linux/docker.sh windows`). NSIS,
  per user, into `%LOCALAPPDATA%\Programs\Inhale`: the sources beside `llvm-mingw\` (its Windows release, which
  `make_game.py` `bundled_mingw()` finds), `python\` (with tkinter), `cpm\` (the headers, and FFmpeg and dav1d built
  with llvm-mingw: FFmpeg's libraries named `<name>.lib`, as `nx2/build.py` links them), `third_party\sdl2\SDL2.dll`
  (sdl2-compat) and `SDL3.dll`, `a64emit.dll` and the third-party objects prebuilt with `RX_TARGET=windows`, `gui\`.
  The uninstaller removes only those names, so a folder chosen by hand keeps its other files; the game folders and
  saves stay, and it asks about the work folder.
- `Inhale-Windows-x64.zip`: the installer's folder, zipped with its contents at the top (no installer, nothing written
  outside the folder), for RecompLauncher. `Inhale.exe` at its top (`packaging/windows/inhale_launch.c`) is the Windows
  `AppRun`: no argument starts the window as the installer's shortcut does, `--cli` runs `make_game.py` with the
  variables `tools_env.build_env` sets (`LONGSHOT_MINGW`, `RX_CPM`, `PYTHONUTF8`, `PYTHONUNBUFFERED`), `--play <dir>`
  starts `<dir>\inhale.exe` in `<dir>`; both wait and return the child's exit code. The installer carries it too.

**RecompLauncher.** `packaging/recomplauncher.json` (format 1) sits at the AppImage's top and the zip's. `prepare` runs
`--cli --prepare --game {game} --out {install}/Inhale` (`make_game.py --prepare`: its `progress` and `error` lines) and
`start` runs `--play {install}/Inhale`, so the game, its `inhale_options.ini` (the `config`) and Windows' `user/` saves
are in the launcher's install folder (upstream's RecompLauncher issue 215: a build into `~/Games` missed the drive the
player chose); Linux's saves are `{local}/inhale`. The check is `nup_build_id` 395fc326, `make_game.py`'s `BUILD_ID`.
Its ten settings are rows this game's menu shows (none of `is_oot_row`'s); Frame generation offers Off and Auto only
(the fixed multipliers' freezes, section 9, "played by hand past the first boss"). No `prepare.options`: DLSS, FSR 4
and XeSS reach this game only through the Upscaler row and Frame generation by, both hidden for it. No `dumps`: Redump
and No-Intro list no `.nup`. `tests/test_recomplauncher_inhale.py` checks all of this against the sources.

Everything downloaded is in `packaging/pins.txt` (name, version, system, URL, SHA-256), fetched and checked by
`packaging/fetch.py` into `work/pkg/dl`; the versions are upstream's at `9af4808f` (LLVM 23.1.5, llvm-mingw 20261104,
Python 3.12.16, FFmpeg 9.0.2, dav1d 1.5.4, SDL 2.32.10 / 3.4.20 / sdl2-compat 2.32.74, Vulkan-Headers v1.4.345,
SPIRV-Headers vulkan-sdk-1.4.341.0, VMA v3.3.0). The window (`packaging/gui/inhale_builder.py`) runs
`python -I nx2/make_game.py` and reads its `@@` lines (`packaging/gui/protocol.py`); nothing in `nx2/` changed for it.

The hot list (section 9, S6: CPU time 10% less) is tracked as `packaging/profiles/hot_funcs.txt`, 301 function names,
and both packages put it in their `work/`, where `make_game.py` takes it; CI's packages have it too. The profiles
(`work/inhale_pieces.prof`, `work/inhale_vk.profdata`) and `work/image/chunks.txt` stay untracked, since their gain over
the hot list is not shown (section 7): a package built on a PC that has them carries them, one built by CI does not.

## 9. Findings

### 2026-11-16, S0

- `nx2/nup.py` listed a title without an exefs by indexing dir `0xffffffff`. `walk` now yields nothing for a tree a
  title does not have; the code title is the newest title with an exefs; a title with a romfs and no exefs is a data
  title and unpacks to `<dump>/aoc/<title id>/romfs` (`nx2/kit.py` `data_romfs` finds it).
- The package's metadata has no name record: `nx2/game_title.py` names the title by id.
- `nx2/kit.py` reads `INHALE_WORK`, `INHALE_DUMP`, `INHALE_EXEFS`, `INHALE_ROMFS` first, then the `OOT_` names.
  Each name is written out where it is read, because `tests/test_lift_cache.py` finds the lift's variables that way.

### 2026-11-16, S1

    $PY nx2/lift.py                      85548 functions, 4801605 instructions, 100.0000% translated, 13 s
    $PY nx2/census.py --nx2              untranslated words are udf and padding only, in every module
    $PY nx2/test_insn.py --per 6 --states 12      583 forms, 34536 cases, 0 failures
    $PY nx2/test_leaf.py --count 3000 --states 4  1363 functions, 3229 cases, 0 differences
    $PY nx2/test_leaf.py --calls                  1695 call trees, 4748 cases, 0 differences

- One indirect branch without a table: `rtld+0x220`, the tag switch of rtld's dynamic-section parser. The standalone
  program does not run rtld (the image is relocated at lift time), so it is not reached.
- `subsdk0` has no instruction form the lifter lacks.
- Both test harnesses were written for Windows (`VirtualAlloc`, structured exceptions). `nx2/test_leaf.py` now also
  builds on Linux (`mmap`, signals); `nx2/test_insn.py` replaces the vendored harness's two Windows lines at run time.
- The other game's lift hooks (`oot_wide`, `oot_fov`, `oot_shadow`, `oot_jitter`) are installed only for its build id
  (`nx2/lift.py`). `nx2/oot_patches.py` is the empty stand-in, so `nx2/chunks.py` needed no gate.
- Imports: `main` takes 899 symbols from `sdk` and 49 from `subsdk0`, all of them CUDA driver calls (`cuInit`,
  `cuCtxCreate_v2`, `cuMemAlloc_v2`, `cuLaunchKernel`, ...): PhysX's GPU path. `subsdk0` takes `NvRmGpu*`, `NvOs*`
  from `sdk`. No module provides eight `glslc*` names (weak, the online shader compiler).
- Add-on content: `nn::aoc::CountAddOnContent`, `ListAddOnContent`, `nn::fs::MountAddOnContent`,
  `QueryMountAddOnContentCacheSize`, beside `MountRom`.
- Movies: `nn::codec` `Vp9Decoder` names of SDK 19 (`InitializeVp9Decoder` with and without a work buffer,
  `RegisterVp9DecoderBuffer`, `SubmitVp9DecoderInputBuffer`, `AcquireVp9DecoderOutputBuffer`, ...). `host/nn_video.c`
  has SDK 22's names (`...ByRemoteMemory`, `...ByTransferMemory`): 21 of its functions match no symbol here. S4.
- `nn::nfp`: 11 names, all answered by stubs.

### 2026-11-17, S2

Run: `work/sa/build/inhale work/sa/image/image.bin --romfs <code title's romfs, may be empty> --aoc work/dump/aoc
--user work/user`, with `HOS_HEADLESS=1 HOS_AUDIO=0 HOS_NO_MOVIES=1`. The whole build takes about 75 s (20 jobs).

What stopped the boot, in order, and the fix:

1. `nn::mem::StandardAllocator::Initialize(NULL, 20 GB)` aborted in `nninitStartup`: the SDK's
   `VammManager::IsVirtualAddressMemoryEnabled` asks `svcGetInfo(16)` (system resource size) and takes 0 as "off".
   `main.npdm` says 0x1000000. `gen/hos_image.c` now carries it (`hos_system_resource_size`) and `host/hos_svc.c`
   answers it.
2. A static initializer of `main` uses `std::random_device`, which ends in
   `nn::crypto::GenerateCryptographicallyRandomBytes` and the `csrng` service. HLE in `host/kirby_hle.c`.
3. `nn::audio::IsValidAudioRendererParameter` was a stub answering 0: abort. HLE answers 1.
4. The game waits until `nn::audio::GetMemoryPoolState` says Attached (1). `host/nn_audio.c` now tracks attach and
   detach requests and answers it.
5. `nn::hid::GetTouchScreenState<16>` (the singular form) aborted in the lifted SDK. HLE forwards to the plural one.

Settled:

- The data title is add-on content index 1. The game mounts the code title's (empty) RomFS as `content:` and the data
  as `aoc1:`, and reads everything from `aoc1:`. `host/nn_aoc.c` lists the titles under `--aoc` (or `HOS_AOC`) and
  mounts them.
- Both thread hooks are found (`0x84e0ac38`, `0x84e0ac40`) and the game's threads start with them.
- The other game's return-address compares in `host/hos_thread.c` and `host/nvn_native.c` are behind
  `hos_game_is_oot()`. `host/hos_main.c` still holds that game's debug and cheat code with fixed addresses; it runs
  only from its menu and the control bridge, and is to be gated before S4.

Open, seen in the last boot (40 s, no abort, no frame):

- 184 imports are answered by stubs. Called so far: `nn::hid::GetNpadState` (five state types),
  `GetSupportedNpadStyleSet`, `GetNpadJoyHoldType`, `GetSixAxisSensorState`, `EnableVibrationNxCompatibleMode`;
  `nn::oe::GetDefaultDisplayResolution` and its change event; `nn::audio::SetDownMixParameterEnabled`;
  `nn::codec::GetOpusDecoderWorkBufferSize`; `nn::nfp::Initialize`, `AttachAvailabilityChangeEvent`, `ListDevices`;
  `nn::nifm`, `nn::bcat`, `nn::prepo`, `nn::socket` `Initialize`; `nn::pl::GetBuiltInFontDataSet`;
  `nn::ro::ProtectRelro`. Not yet called but needed for sound: the `AudioOut` family, `GetVoicePlayState`,
  `ExecuteAudioRendererRendering`, the delay effect, the resampler, the Opus and AAC decoders.
- After NVN start-up (device, three memory pools, sampler and texture pools, two syncs, two 3840x2160 window
  textures, window, queue) the main thread issues no submit and no present. Settled in S3.
- The process ignores SIGTERM while running; runs are ended with SIGKILL.

### 2026-11-17, S3

Evidence: `work/runs/s3/first_frame.png` (present 300 of a headless run, `RX_VK_SHOTS=<dir> RX_VK_SHOT_EVERY=100`): the
"connect online" dialog. `work/runs/s3/first_frames_sheet.png` is from before fixes 3 and 4 (presents 15 to 360). Log
with `--trace`: `work/runs/s3/origin1.txt`.

What stopped the first frame, and the fix:

1. The main thread slept in a loop in `main+0x65b460`: it asks `nn::pl::GetBuiltInFontDataSet` for the console's six
   built-in fonts every 100 ms until the answer is true, and the stub answered 0. Found with a backtrace of every
   thread (`work/gdbbt.sh <name> [seconds]`: the run under gdb, interrupted; `HOS_SAMPLE` is Windows only). The HLE in
   `host/kirby_hle.c` answers with the bundled Libertinus Sans for every type; `nx2/build.py` compiles
   `nx2/ui_fonts.py`'s file into the program too. The entry layout (0x18 bytes: type, flag, address at 8, size at 16)
   is read from the lifted `sdk+0x4fc650`.
2. `nn::fs::CommitSaveData("save")`, SDK 19's name of `nn::fs::Commit`, aborted in the lifted SDK after the game wrote
   its first `save:/system`, `file0` to `file2`. HLE answers 0.

3. Every text was upside down, pane by pane. The game draws each text into a small texture of its own and then draws
   that texture. It never calls `nvnDeviceSetWindowOriginMode`, so its origin is NVN's default, the lower left, where
   +y of clip space is the higher row; the back end flipped every viewport, as the upper-left origin of the two games
   before needs. Found with a frame dump (`RX_VK_DUMP=<present>`). The host now tells the back end the mode
   (`MkwVkHost.origin_lower_left`, API version 26): with a lower-left origin `gpu/vk/vk_draw.cpp` leaves the viewport
   as it is and swaps the front face, and `gpu/vk/vk_replay.cpp` `blit_crop_to_rect` presents bottom row first.
   Not covered: the presents that do not go through that blit (frame generation, the temporal upscalers), and the
   frame dump's pictures, which show row 0 on top.
4. `nn::hid::GetNpadState` (five styles) and `GetSixAxisSensorState`, the singular forms, were stubs that left the
   game's state unwritten: the game answered its first dialogs by itself. HLEs forward to the plural forms.

Settled:

- NVN procs with no host implementation that the game called: none (no `is not implemented` line in 60 s).
- Shader lowering: the 2D screens draw with no renderer complaint in the log. 3D scenes are not reached yet.
- Queues: the game submits to two queues, three submits a frame; presents hold 60.0 a second headless.
- The live-sync count of the mirror log stays 0 (rule 2 of section 4).

Open, for S4:

- `nn::hid::GetSupportedNpadStyleSet` and `GetNpadJoyHoldType` are still stubs.
- Seen before fix 4, when the dialogs answered themselves: after the difficulty screen the game loads the first stage
  (`gfx/Step`, `lyt/Pause/StageTitle/Lv1`) and the frames are black, 3 draws and 1 dispatch each. Stubs called on
  the way: `nn::web::ShowOfflineHtmlPage` (once, right after the first screen), `nn::movie::Initialize`,
  `nn::audio::GetVoiceNodeId`, `GetVoicePlayState`, the delay effect's setters,
  `nn::vi::QueryDisplayBufferMaxResolution`. The opening movie is the first suspect (`HOS_NO_MOVIES=1` was set, and
  `nn::movie` has no host implementation).

### 2026-11-17, S4

Run: `HOS_INPUT_FRAME_CLOCK=1 HOS_NO_MOVIES=0 HOS_INPUT_SCRIPT="10:LEFT,12:A,16:A,20:A,24:A" HOS_VIDEO_LOG=1
RX_VK_SHOTS=<dir> RX_VK_SHOT_EVERY=240 RUNDIR=s4 work/boot.sh <name> 90` (`work/boot.sh` keeps `HOS_NO_MOVIES=1` unless
it is given; the pictures' folder must exist). With `HOS_INPUT_FRAME_CLOCK=1` the script's seconds are 60 presents:
the start takes 3 to 15 s of wall clock from run to run, and a wall-clock script then presses `LEFT` before the first
dialog takes input (the game stays on "connect online" and calls `nn::web::ShowOfflineHtmlPage`). The same variables
work with `work/gdbbt.sh` (`RUNDIR`, `HOS_NO_MOVIES`). Last log: `work/runs/s4/mov9.txt`.

Done:

- Scripted input works: "Do Not Use", the notice after it, the difficulty screen. The game then starts its movie
  player (threads `MoviePlayerMain`, `MovieEventHandler`, `MediaExtractorWorker`, `VideoDecoderThread`,
  `AudioDecoderThread`) on `aoc1:/mov/EventMovie/Opening.webm`. With `HOS_NO_MOVIES=1` the file is "not found" and
  the frames stay black: that was the black after the difficulty screen.
- The lifted `nn::movie::MediaExtractor` demuxes the WebM by itself (class members stay lifted; only the free
  functions `nn::movie::Initialize`, `IsInitialized`, `Finalize` are stubs, and the game goes on with them).
- The VP9 decoder's SDK 19 names are on `host/nn_video.c`'s functions (`host/kirby_hle.c`): `MakeDecodeImagePreference`
  and `InitializeDecoderImagePool` with a `CodecMode`, `CalculateVp9DecoderWorkBuffer`, `InitializeVp9Decoder` with a
  work buffer, `GetVp9DecoderSubmissionReadyEvent` with an out pointer, `GetVp9DecoderOutputBufferProperties` with a
  colour space (its index is on the stack). Before, the first `AcquireVp9DecoderOutputBuffer` answered an error and
  the game aborted. Now: `video: VP9 decoder ready on vp9`. `work/plt.py <addr>` names the import behind a PLT stub
  of `main`.
- `tests/test_audio_output_devices.py`, `tests/test_microphone_test_gain.py` and `tests/present_source_crop_test.cpp`
  follow API version 26 and the new host callback.
- The movie player is the game's own code in `main` (0x8088d000 to 0x80895000, decoders' wrappers at 0x80450000 to
  0x80459000), not the SDK's player. Four things stopped it, in the order found:
  1. `nn::os::TimedReceiveMessageQueue` had no host function: the lifted SDK body ran on a queue the host had made and
     slept forever in `InternalCriticalSection::Enter` (`MovieVideoInputReadThread`, `MovieAudioInputReadThread`).
     Now in `host/nn_os_sync.c`. An audit of the SDK's `nn::os` exports against the host's functions (577 exports,
     140 with a host function; `main` imports 116) found one more of this kind that `main` imports,
     `BroadcastConditionVariable`: added too (wakes every waiter), not seen called in these runs.
  2. The `nn::audio::AudioOut` family (15 imports) was stubs: channel count, rate and sample size read 0, the first
     `AppendAudioOutBuffer` answered false and the player went on without sound. Now in `host/nn_audio.c`: one
     output, 48 kHz, 16 bit, 2 or 6 channels; the renderer thread plays the queue (240 frames each 5 ms, with the
     device off too) and signals the game's event for each buffer played. The game queues four buffers of 10 ms and
     refills one for each signal, on `MovieEventHandler`. It never asks for a played sample count.
  3. `host/nn_video.c` opened libavcodec's VP9 decoder with frame threads, which give a picture back only once three
     more are in; this player submits one picture and waits for it. VP9 now decodes with tile threads: the first
     picture comes back (`video: acquire 3: 1920x1080 pts 0`).
  4. The decoder's submission-ready event was signalled once, when made, and again only after the decoder had been
     full. This player clears the event each time it wakes and submits one picture: it never submitted a second.
     `input_room` now signals at every call with room.
- The opening movie plays to its end (`work/runs/s4/mov12.txt`, 240 s): 2296 pictures of 1920x1080 in 76.5 s, 1.9 ms
  to decode each, none skipped, 0.07 s from the movie's clock at the end, then `Stop`; 60.0 presents a second all
  through. Pictures: `work/runs/s4/movie_sheet.png` (colours and orientation right). Sound: `HOS_AUDIO_DUMP=<wav>`
  works with `HOS_AUDIO=0`; the dump has the movie's sound for those 76 s (peaks about 15000 of 32767).
- After the movie the game writes `save:/system` and `save:/file0` and starts the first stage: a 3D scene, drawn at
  60 presents a second (`work/runs/s4/after_movie_sheet.png`).
- The present stall of the first S4 runs (7 presents a second, the main thread's `nvnSyncWait` 70 to 140 ms each,
  each wait satisfied, GPU time 0.2 ms a frame) is not explained. Runs with the movie started and no picture decoded:
  it came in `mov2` and `mov7`, not in `mov4`, `mov5` or under gdb (`stall1`). With the first picture decoded (`mov9`)
  the rate dipped twice for a few seconds and came back to 60. The wait is in `gpu/vk/vk_replay.cpp` `wait`.

- The game's own sound was silent (0 in the dump, before and after the movie) though its voices were made:
  `nn::audio::GetVoicePlayState` was a stub that answered 0, "started", and the sound engine starts only the voices
  it reads as stopped, so it never called `AppendWaveBuffer` or `SetVoicePlayState` (0 calls with `HOS_HLE_STATS=1`).
  The host function answers the state the game set last. Now `HOS_AUDIO_STATS=1` shows 2 to 6 voices playing and
  the dump has sound on the title screen and in the stage (`work/runs/s4/snd2.txt`, `snd2.wav`). Not listened to.
- Save round trip: after the movie the game wrote `save:/system` and `save:/file0`; the next boot shows the title
  screen with "File 1, Continue, Select File", and `A` there enters the stage with its HUD
  (`work/runs/s4/second_boot_sheet.png`). A first boot (no save) has no title screen: its three dialogs, the movie,
  the stage. With a save the script is `HOS_INPUT_SCRIPT="10:A"`; for a first boot again, move `work/user/save` away.
- Tests after these changes: 575 passed, 0 failed (`work/runs/s4/tests3.txt`).

Left for later stages:

- The first stage is drawn under a cyan wash, the lower half plain cyan (`work/runs/s4/after_movie_sheet.png`,
  `second_boot_sheet.png`): S5's first item.
- The presents' drop to 7 a second while the movie player starts (above): not explained, not seen since the movie
  plays.
- Not adapted, not called so far: `InitializeVp9Decoder` without a work buffer,
  `GetDecoderImagePoolNativeImageHandle`, `nn::codec::sdk::MakeDecodeImagePreferenceForCompat`.
- Stubs called and unanswered: `nn::web::ShowOfflineHtmlPage` (when "Use" is chosen on the first screen),
  `nn::movie::Initialize`, `IsInitialized`, `Finalize`, `nn::audio::SetDownMixParameterEnabled`, `AddDelay` and the
  delay's setters (the effect is not heard), `GetVoiceNodeId`, `nn::codec::GetOpusDecoderWorkBufferSize`,
  `nn::vi::QueryDisplayBufferMaxResolution`, `nn::hid::GetSupportedNpadStyleSet`, `GetNpadJoyHoldType`,
  `EnableVibrationNxCompatibleMode`, `nn::nfp` (three), `nn::oe::GetDefaultDisplayResolution` and its event.
- The other game's debug and cheat code in `host/hos_main.c`, `host/nn_hid.c` and `host/oot_*.c` is reached only
  through that game's lift hooks or through menu options that are off by default; gating it on the build id is S6's.
- The `nnos*` C wrappers of the SDK (about 140, 20 imported by `main`) have no host functions of their own: safe
  where a wrapper branches to the hooked C++ function, not checked one by one.

### 2026-11-17, S5

Run, with the save of S4 in `work/user/save`: `HOS_INPUT_FRAME_CLOCK=1 HOS_INPUT_SCRIPT="10:A" RUNDIR=s5 work/boot.sh
<name> 45` (title screen, Continue, the first stage by present 900). One frame pass by pass: add `RX_VK_DUMP=1500
RX_VK_DUMP_DIR=<existing dir> RX_VK_DUMP_W=480`; the pictures go to `<dir>/dump_1500` (row 0 on top: upside down for
this game), and the log's `vk: dump` lines give each pass's result (`dump NNN ...: mean, min, max`), its state
(`dump-st`) and its textures (`dump-in`, where `none(0x<handle>)` is a texture the back end has no view of).

Done:

- The cyan wash is gone (`work/runs/s5/d2.txt`, `work/runs/s5/d2/vk_001500.png`: the beach, right colours, 60.0
  presents a second, GPU time 2.7 ms a frame). Cause: the scene's depth buffer is NVN `DEPTH24_STENCIL8`, Vulkan
  `D24_UNORM_S8_UINT` (129), and RADV on AMD has no 24-bit depth format at all (`vulkaninfo`: the format is not
  listed). Its features read 0, so the image was made without sampled usage (and was not a valid image), the passes
  that read the scene's depth got the dummy, and the lighting pass fogged the picture. `image_format_of`
  (`gpu/vk/vk_texture.cpp`) now answers the 32-bit float twin (`D32_SFLOAT_S8_UINT`, `D32_SFLOAT`) where the device
  cannot attach the 24-bit one: the image, its views and the pipeline list's attachment format follow from that one
  rule. The format table (`vk_format`) stays a plain table: two tests read it as text.
- The frame gate (`gpu/vk/vk_replay.cpp` `gate_need_value`) dropped a fence request made while a present was queued.
  This game submits once more after its present and waits for that submit's fence (hand-over order: submit, submit,
  present, submit; 10 s timeout). Where the present is replayed at once (a shot of that present: `RX_VK_SHOT_EVERY=1`
  or 2), the last submit then stood alone at the gate for `RX_VK_FRAME_GATE_MS` (1000): 1.0 present a second
  (`work/runs/s5/f4.txt`; `RX_VK_FRAME_GATE=0`: 57). The request is now honoured with a present queued too: 60.0 with
  a shot of every present (`work/runs/s5/f8.txt`). Whether this is also the S4 stall (7 presents a second while the
  movie player starts) is not checked.
- Slots with no view, looked at: `0x2cb`, `0x48b`, `0x521` are 16x16x16 3D textures (NVN format 0x38) a 2D sample
  instruction reads. `make_view` makes such a view only with `sampler2DViewOf3D`, which RADV does not have
  (`image2DViewOf3D` only): they are sampled as the dummy. None of them is in the dumped frame of the stage; which
  passes read them is not known. `0x55a` / `0x397` (512x512 BC4, 2D) is bound where the lighting pass's program
  declares a 3D sampler (`t19` of dump 022), and handle `0xffffffff` is an unset binding (dumps 015 and 062): both
  get the dummy, and the picture is right with it.

- The two one-frame flashes are gone: 0 flashes in 5040 presents, the beach into the jungle, with a shot of every
  present (`work/runs/s5/g5.txt`). Run: `HOS_INPUT_FRAME_CLOCK=1 HOS_INPUT_SCRIPT="10:A,20:LUP/9000,23:A,26:A,
  30:LRIGHT/2000,33:LUP/10000,36:B,40:A/800,45:LLEFT/2000,48:LUP/8000,52:B/1500,58:LUP/10000" RUNDIR=s5 RX_VK_FLASH=1
  RX_VK_FLASH_DUMPS=0 RX_VK_SHOTS=<dir> RX_VK_SHOT_EVERY=1 work/boot.sh <name> 85` (before: `work/runs/s5/f9.txt`, two
  flashes, `work/runs/s5/f9/flash_sheet.png`: the title screen's blue background black for a frame at present 461 to
  477, and at present 1406, where the beach ends, a frame without the new zone's objects). Cause: the renderer, not the
  game. Its default leaves a draw out of the frame while its pipeline is built, where the targets hold an earlier
  frame's picture (`gpu/vk/vk_draw.cpp`, the `may_skip` branch; the build is a job even when the pipeline cache has
  it, so a warm cache flashes too). The log said so all along: `draws left out (not ready)` read 4.7 a frame in the
  120 presents around the place, 0.0 elsewhere. `host/hos_main.c` now sets `RX_VK_PIPE_SKIP=0` (every pipeline is
  waited for) where the player has not set the switch; `RX_VK_PIPE_SKIP=1` is the renderer's default again. Cost,
  measured with `work/cold.sh` (a fresh folder: no pipeline or program cache, `MESA_SHADER_CACHE_DISABLE=true`):
  cold and left out, 3 flashes (`work/runs/s5/c1.txt`); cold and waited for, 0 flashes, the slowest 120 presents at
  52.9 a second against 59.1 (`work/runs/s5/c2.txt`); warm, no wait measured (0.0 ms a frame).
  The earlier reading here (the game keeps frame data in two copies and one takes the new zone a frame late) was
  wrong. What ruled it out: a log of each recording's age at the submit (temporary, removed; `work/runs/s5/g3.txt`,
  read with `work/agelog.py`). The main thread records one 730 KB buffer a present, the thread `Thread_8091ce68`
  records the 16 buffers it calls and submits; every one of them is recorded in the present that submits it, and the
  lists change once at the zone change (present 1405) and never go back. The game does keep its cached per-object
  lists in two sets used in turn (17 new lists twice at the zone change), and both sets held the new zone.
  The renderer's quick pipelines (`RX_VK_QUICK_MS`, off by default) are the other way to draw such a frame without
  the wait; not tried, as its budget can still leave a draw out.

- The black box at the "Jump" hint is the hint's movie, left out by `HOS_NO_MOVIES=1`, which the helpers set
  (`host/nn_fs.c` OpenFile answers "path not found" for every `.webm` then; log: `fs: OpenFile(aoc1:/mov/GuideMovie/
  Jump.webm): movies are left out (HOS_NO_MOVIES)`). With `HOS_NO_MOVIES=0` the box shows the movie (Kirby jumping on
  a checkered floor), then the check mark, then fades by present 2550; the script needs no change
  (`work/runs/s5x/a2.txt`, `work/runs/s5x/a2_hint.png` against `work/runs/s5x/a3_hint.png`). 480x270 VP9, it loops,
  `video: Stop after 168 submits and 157 acquires`; presents stay 59.5 to 60.3 a second while the player starts, so
  the S4 stall did not show here. Not checked: the other 35 files of `mov/GuideMovie`, colours against a console.
- "One add-on map loads", read literally, is met: `work/dump/romfs` is empty and the add-on title is the whole game's
  data. In `work/runs/s5x/a2.txt`: `aoc: index 1: work/dump/aoc/01004d300c5af001/romfs`, `fs: mounted aoc1:`, 11062
  OpenFile calls on `aoc1:` (3203 found), 14 on `content:` (all not found), and the first stage's maps from it
  (`aoc1:/ubin/Step/Map/Level0/Stage1/Step01/Attr_Attr.bin.cmp` and the rest of `Step01`, `Step02`, the models under
  `aoc1:/gfx/Step/Decor/Map/Level0/Stage1/`). The Switch 2 Edition's extra stages are the `Dlc` names of the same
  romfs (1223 files, 1.53 GB; maps `ubin/Step/Map/DlcLevel0/Stage1` to `DlcLevel8/Stage1`, 13 stages, and
  `DlcArena`). None of those maps has been opened: a Starry stage is entered from the world map, and the game's texts
  say one appears when a world's boss is beaten, so it needs a save past the first world or a long scripted
  play-through. Left for after S6 unless such a save turns up.
- A profile in the stage (script `"10:A,20:LUP/9000"`, 60.0 presents a second; `work/runs/s5x/c5.txt`, `c6_all.txt`,
  `c7_main.stacks`; helpers `work/runs/s5x/prof_cpu.py`, `prof_all.py`). The whole process uses 101 to 126% of a
  core over ten threads, none above a fifth: `mkw_vk recorder` 17 to 19, `mkw_vk replay` 16 to 18, `MainThread` 14 to
  15, seven `Thread_8091ce68` workers from 13 down to 2. The render thread's jobs take 2.48 ms of a 16.65 ms frame.
  Of the game threads' CPU samples 77% are lifted game code, 12% the host runtime, 6% libc or the driver, 5% the
  renderer; `f_807eff00` (a bytecode interpreter by its disassembly: 32-bit words, a jump table at 0x809c76a8) holds
  65% inclusive. No hot stub and no costly spin. Small host-side items: the recorder spins idle 0.76 s in 10 s
  against 0.44 s of work; `spin_until_set` (`host/nn_os_sync.c`) 3.4%; futex wakes under `WakeAllConditionVariable`
  3.4% (the virtual cores change hands about 24000 times a second); with `--trace` every NVN call goes through
  `a64_call_miss` (10 to 21% of the workers' samples), so profiles are taken with `TRACE=`.
  Tool notes: `HOS_SAMPLE` is wall-clock (most leaves in libc are waits; `scripts/prof.py` does not split them);
  it cannot reach the workers, which share one name: `HOS_SAMPLE_ALL=<file>` samples every thread while `<file>.go`
  exists; `RX_MAPS=<folder>` tells `scripts/prof.py` where the build's maps are.

- The 3D textures a 2D sample instruction reads, looked at: no change made, the dummy is harmless here. The texture
  is the colour grading's 16x16x16 table (the grading pass `5be22000a0782116` samples it as 3D, rightly). The 2D
  readers are layout programs that name it in an unused third sampler slot: `517266ea5da77cfe` in the stage intro
  (present 726 to 730, one HUD draw) and six programs on the title screen in one run of three. In `517266ea...` the
  sample sits in a block that runs only when the float at c3+4 is not 0, and it was 0 in every such draw of a 62 s
  run (`work/wt2/w/runs/a7.txt`, IR in `work/wt2/w/runs/b4ir/`): the shader never executes the sample. A fix exists
  and is not applied: `work/wt2/item2.diff` (a 2D image holding slice 0, made in `texture_view`, copied again after
  each upload; the copy was pixel-identical to slice 0, the pictures unchanged, 60.0 presents a second). Applied to
  the main tree it failed two tests that compile `vk_texture.cpp`'s functions against their own `Texture`
  (`tests/test_image_view_retry.py`, `tests/test_readback_timeout_source.py`; `work/runs/s5/tests3.txt`), and its
  re-upload and destroy paths were never run: not worth carrying for a sample that is not executed. Apply it, with
  the two fixtures extended, if a dump ever shows a 16x16x16 `none(0x...)` in a draw whose picture is wrong.
- Tests at the end of S5: 575 passed, 0 failed (`work/runs/s5/tests4.txt`).

S5's exit checks: the first level without flashes (met), one add-on map loads (met as written; no Star-Crossed
World stage yet, section 7), a profile (met).

### 2026-11-17, S6

Order: the rename first, so that everything after it was written and tested under the final names. Logs:
`work/runs/s6/`. The work tree as it was before S6 is kept in `work/runs/s6/pre/` (the diff of the tracked files and
the two untracked sources).

**The rename** (`scripts/rename_full.py`; without `--write` it only counts).

- One rule, case by case (`longshot`, `Longshot`, `LONGSHOT`), over the tracked and the untracked files: 2228 places
  in 428 files, 4 files renamed (`gpu/vk/compat/inhale_env.h`, `scripts/inhale_ctl.py` and its two tests). A second
  run finds 0 places.
- Kept, and why: the marks `(longshot)`, `(longshot: ...)`, `(longshot-amd)` on upstream's changes to code it took
  from others (1575); `LONGSHOT_MINGW` and `LONGSHOT_LIGHT_PASSES`, which the vendored a64-kit reads by name (its tree
  hash is checked); upstream's repository and tracker addresses and one launcher issue number; whole files: the
  provenance and credit documents, the readme, this file, the sync script, `third_party/`, the renderer's shader
  sources with their compiled headers (a header names the hash of its source: `tests/test_hdr_encode.py` failed
  until they were left alone), and the other game's item table, where the name is an item of that game.
- One span has an answer of its own: the window's application id was under upstream's domain, and is now the plain
  `inhale`.
- A name of another length breaks lengths written by hand. Thirteen places copied or compared a string holding the
  name with its length as a number (`memcpy(path + n, "longshot_env.txt", 17)`, `strncmp(text, "Longshot crash
  record 1\n", 24)`, `strstr(line, "] longshot ") ... at + 11`): three tests found the first of them
  (`test_crash_record`, `test_env_file`, `test_log_open_failure`, under gcc's `-Werror`), a scan of every string
  holding the name found the rest. The script now moves such a number with its string (`LENGTH`: the first number
  that ends an argument or a sum after the string, where it equals the string's length with or without the end's
  zero); run over the files as they were before the rename it changes exactly those thirteen.
- Where this fork's own text meant upstream by the name (six comments), it now says "upstream": the rule cannot tell
  the two meanings apart, so the text that must keep the name is in the kept files.
- `scripts/sync_upstream.py` builds both sides of Longshot's diff as trees put through the same rule (file names and
  text, blobs written into this repository so that `git apply -3` finds its bases) and applies the diff between
  them. Tried on two throwaway clones: a change to `longshot_env.h` and to `longshot_ctl.py` and a new file arrived
  under the new names with the new text, and a line changed on both sides was left as a conflict.
- Consequences: the environment variables are `INHALE_*` (`INHALE_VULKAN_HEADERS`, `INHALE_SPIRV_HEADERS`,
  `INHALE_JOBS` and the rest), the program is `work/sa/build/inhale`, the saves' default folder is
  `$XDG_DATA_HOME/inhale`, the builder's default work folder `~/.cache/inhale-builder` (no longer shared with a
  Longshot install), and every cache keyed on the old names was built again once. The prefix lists that pass or drop
  `INHALE_` variables now also match the dump variables (`INHALE_WORK`, `INHALE_DUMP`): harmless, the game reads none.

**`nx2/make_game.py`.**

- The game folder: `inhale`, `inhale_vk.so`, `image.bin`, an empty `romfs/`, and `aoc/<title id>/romfs` with the
  data. `host/hos_main.c` takes `aoc` from beside the executable, as it takes `romfs` and `user`, unless `--aoc` or
  `HOS_AOC` names one.
- Changed in the builder: the data check (`ROMFS_NEEDED`: `ubin/Step/Map`, `gfx/Common`, `fdg/Archive.dat`, tested
  on the romfs that holds the data); the package path moves `aoc` into the folder and always makes `romfs`; reuse
  by stamp and `--update` do not unpack again; `--aoc <dir>` and `--game <folder with exefs and aoc>`;
  `--romfs-from` carries `aoc`; the lift and the build get `INHALE_*`; the game's name for folder input comes from
  `main.npdm`'s program id; the texts and button prompts steps, which read the other game's archives, are gone from
  the build; the language list is this game's 13 (the folders of `msg/Kirby15`), in `make_game.py`,
  `host/nn_applet.c` and `gpu/vk/vk_menu_i18n.cpp`.
- Run for real: `make_game.py --nup <package> --out work/game --work work/mg` ends `@@done`, 132 s after the unpack
  (83 s of compiling), 12 GB (`work/runs/s6/make_game1.txt`). `work/game/inhale` with no arguments mounts `aoc1:`
  from the folder and presents 60.0 a second (`game_folder1.txt`; `XDG_DATA_HOME` set to a folder under `work/`, so
  the first-boot script was used). `--update work/game` after later source changes: 10 s, 99 of 455 files compiled,
  no unpack, 60.0 again (`make_game2.txt`, `game_folder2.txt`).
- Left as they are, harmless here: the shader list step (it ends "the shader list was not made: the game will
  compile its shaders as it plays", which is true), the damaged texture check (nothing to find: no `.zs` files),
  sizes in a few messages that are the other game's.

**The hot list and the profiles.** None is in the repository (upstream kept its own out too): they are
`work/hot_funcs.txt`, `work/inhale_pieces.prof` and `work/inhale_vk.profdata`, which `make_game.py` copies into its
work folder and uses when they exist. `work/boot.sh` sets the matching variables, since `nx2/lift.py` and
`nx2/build.py` take them from the environment alone: a lift without `A64_HOT_FUNCS` takes the hot chunk away, and a
build without `RX_PGO` / `RX_VK_PGO` compiles without the profiles again.

- Sampling: `HOS_SAMPLE_ALL=<file> HOS_PROFILE=5`, no call tracing, the S5 walk script; `<file>.go` must be made
  after the stage has started (second 20): made before the start, only `MainThread` is ever sampled (41983 lines of
  one thread; the sampler takes its thread list when it first sees the file).
- `scripts/hotlist.py work/runs/s6/hot2/all.txt <out> 0.95`: 10414 samples of game threads in 725 lifted functions;
  301 functions cover 95% (79 cover 85%). First: `f_807eff00`, the bytecode interpreter of S5's profile. Two faults
  of the tool fixed on the way: on Linux it took the module from the empty entry the linker map gives the `.exe`
  name (0 samples counted), and it appended the other game's decoder functions to every list (now only where the
  build's `gen/hos_image.c` carries that game's build id).
- Lift with the list: `hot functions (A64_HOT_FUNCS): 301 of 301 listed found, in code_hot.c`; `nx2/split_hot.py`
  makes 8 pieces.
- Profiles: `RX_PGO=gen RX_VK_PGO=gen` build, `work/pgo_run.sh` (the walk script; at present 4200 both modules
  write their counters, on the `.dump` files; the instrumented build presents about 25 a second, and the script
  counts presents, so the play is the same), `llvm-profdata merge`: 1310 functions of the hot pieces, 4369 of the
  renderer. The build says `the Vulkan back end: built with the profile ...`; the game side says nothing.
- Measured (`work/cpu.sh <folder with the two binaries> <name>`: the process's CPU seconds by thread between
  presents 1800 and 3000 of a fixed walk, from `/proc`; all runs at 60.0 presents a second; three runs each on a
  quiet machine, `work/runs/s6/cpu_*{7,8,9}.cpu`): before 18.29, 18.30, 18.43; with the hot list 16.87, 16.42,
  16.24 (10% less; the workers `Thread_8091ce68` 10.66 to 8.61); with the hot list and both profiles 16.13, 15.60,
  17.45. The profiles' gain over the hot list is not shown by these numbers (section 7).

**The in-game menu.** The host tells the menu once, before the renderer starts, whether the game is the one the
game-specific rows were made for (`HOS_OPT_OOT_GAME`, 72, through the existing option call: `host/rx_backend.c`,
`gpu/vk/vk_menu.cpp` `row_shown`, `is_oot_row`). Never told (a menu built alone, as the tests build it), every row
shows; no row or string was deleted.

- Hidden for this game, each for a consumer that is only the other game's code: Field of view, Shadow resolution,
  Aspect ratio, Ultrawide menus, HUD layout, Text speed, Text size, Camera speed, Skip title screen, Skip opening,
  the Debug tab's tools, the ocarina notes of the Controls page, the microphone rows (Audio's Microphone, Microphone
  gain and Test microphone: the ocarina's input streams in host/nn_audio_in.c, which no game code calls); and, read to
  be sure, Render resolution (its values are read by no host code), Upscaler and DLSS model (the chain replaces only the
  other game's programs), Frame generation by (DLSS frame generation needs that upscaler's picture), Game frame rate cap
  and Game speed (the limiter and the time step need the other game's graphics module; measured: a cap of 120 still gives
  60, a cap of 30 gives 30 presents with the same game state each, so half speed), Disable camera centering.
- A hidden row's saved value is held at its default while the row is hidden (`oot_rows_hold`, for the run only: the
  file keeps its value). Checked with a saved cap of 30: 60.0 presents a second.
- Any game but the other one stays 16:9 (`host/hos_main.c`): told another shape, the renderer stretched the 16:9
  picture.
- Words: "Link" is "the character" in the Walk rows; the Microphone help no longer speaks of the ocarina; the
  Quality preset's and the weak laptop row's help are chosen by the flag, without the hidden rows' names; the
  graphics card message no longer names the other game; the three texts that sent the player to upstream's tracker
  name `tracker.inhale.invalid` (this fork has no tracker). Carried through the 13 language tables where the text
  had entries.
- Kept, generic or half so: Mouse camera (falls back to "as the stick"), Button prompts (names the pad's inputs;
  the game's own icons are the other game's files), Walk mode and speed.
- Seen: `work/runs/s6/menu/*.png` (one picture a tab, in the stage) and `options.txt` (the control bridge's list,
  65 settings). Left: texts that speak of a launcher or a builder application, which this fork does not have
  (`host/hos_crash_dialog.h`, two in `gpu/vk/vk_menu.cpp`); the Controls help names the Button prompts row.

**At the end of S6:** the walk from the beach into the jungle, 0 flashes in 5040 presents with a shot of every
present, on the build with the hot list and the profiles (`work/runs/s6/flash1.txt`); tests 575 passed, 0 failed
(`work/runs/s6/tests2.txt`); `scripts/check_third_party.py`: 13 parts as their notes say.

S6's exit checks: the builder and the folder's program (met), the hot list and a profile measured (met; the hot
list's effect is shown, the profiles' is not), the menu (met for the rows and texts listed; the launcher texts are
left), the rename (met).

### 2026-11-17, after S6: played by hand

The first stage was played in a window, with sound, from `work/game/inhale`.

- Keyboard defaults are this game's (Type A): Space or Enter A, E or the left mouse button B, F X, Q Y, Shift or the
  right mouse button L, Tab Plus (`host/nn_hid.c` `key_default`). The keys were not pressed in a scripted run.
- A hint movie that plays to its end and starts again aborted the game (`nn::diag::detail::AbortImpl`, lr 0x80450168:
  the decoder wrapper in `main` gives back a picture it no longer has). S5 saw a hint movie only until the walk
  finished the hint, before its 5 s were over. Three causes in `host/nn_video.c`, all at a movie's end:
  1. Every acquire after the last submission marked its buffer "last": three "last" pictures, where the player takes
     one and flushes. Now one; later buffers go out not last, their sync not reached.
  2. `RequestSyncPointEvent` for a sync not reached left the event signalled from the buffer's last picture. The
     wrapper's decoder thread then queued such a buffer for the player as a picture; the loop's flush took it back
     (the wrapper's flush at 0x8044f860 releases everything it handed out) and the player's next release aborted.
     The event is now cleared when the request is put off.
  3. A flush kept the buffers' times. The first buffers of the next pass told 4.9 s, the player took its clock from
     them and ran through the 150 pictures in 0.45 s. The times are zeroed at a flush.
  Checked: `work/runs/c1/h.txt`, 120 s with the "Jump" hint up (Kirby walks against a ledge), 17 passes, each 150 pictures 33.3 ms apart,
  none skipped, no abort; the opening movie still ends with `Stop` and the stage starts (`work/runs/c1/first.txt`);
  tests 575 passed. The player's crash came after copying an ability, so at a later hint: the same abort and
  backtrace, that hint itself not replayed. Helpers: `work/runs/c1/run.sh <name> <seconds> <input script>` (the game folder on a copy of the
  player's save, `HOS_VIDEO_LOG=1`), `work/runs/c1/script_b.txt` (the walk that reaches the hint and stays).
  `HOS_VIDEO_LOG=1` now also logs each buffer's release and each sync event request.
- Not looked at: each pass of a looping movie starts with the two buffers as they were (the last pass's final
  pictures) for a frame or two.
- Background music missing in stages and in the scenes drawn by the engine: the software `nn::codec::OpusDecoder`
  family was all stubs. It is now in `host/nn_codec.c`, on the hardware decoder's bodies (not committed; in
  `work/game/inhale` since 14:03). The player heard the music in play afterwards; the check below forced a track.
  - The game's music is 160 Opus streams (`snd/Kirby15/stream/*.opus`, Nintendo header `0x80000001`) and 66
    `.bfstm`. The title's `K15_TitleAndTownNewWorld1` is a `.bfstm`, which is why it always played. The sound engine
    decodes Opus with the software decoder: `GetOpusDecoderWorkBufferSize` twice at start (lr 0x805823ec,
    0x805822d0), then `InitializeOpusDecoder` (48000 Hz, 2 channels, lr 0x80582b0c) and `DecodeOpusInterleaved`
    (lr 0x80582ed8) on the stream thread `Thread_8059dc48`. The hardware family is not called.
  - The first stage's beach has no music by the game's data, so a run that stops there says nothing about the fix
    (the mistake of the first look: "the change alone brings no music"). `yaml/Scn/Step/Map/MapData.bin` names
    `_NO_SOUND` for `Level0/Stage1/Step01` and `Step02`; its `GimmickData` row for both is
    `["_NO_SOUND", "K15_Grassland1"]`, so the music there starts from something in the map, further in than any
    scripted walk has reached. The game's scripts ask for a step's music through `f_8090d740(manager, archive,
    label, ...)` (bindings at 0x8070f074 and after; `f_8090da40` is its sibling); the manager's per-frame update
    `f_8090dd40` starts it with `f_8057f364(startable, handle, label, archive, info)`, and `f_8057b2ec` looks a
    label up. With the save on the beach the only requests are the title's and `_NO_SOUND`.
  - Check: under gdb the stage's `_NO_SOUND` request was rewritten in place to `K15_Cave1` (an Opus stream, same
    length). The decoder is created and decodes (`codec: decode 803 bytes (of 4096) -> 960 samples`), and the audio
    dump is music for the 45 s after: RMS 2500 to 3400 by 4 s windows against about 400 for the beach's waves alone
    (`work/runs/bgm/force1.wav`, `work/runs/c1/bgm1.wav`). With `GetOpusDecoderWorkBufferSize` made to answer 0
    again the stream still starts and decodes: the missing bodies were the cause, not the size. Tests 575 passed.
  - Not checked by a scripted run: a loop point of a `.marker.opus` stream, and the natural start of
    `K15_Grassland1` in the first stage (holding the stick up and jumping stalls in the first clearing,
    `work/runs/bgm/wj1_sheet.png`). The player's report covers the music in play, not these two by name.
  - Method, helpers in `work/runs/bgm/`: `gdb.sh <name> <seconds> <input script> <python file>` runs the game
    folder under gdb on the copy of the player's save; the Python file sets breakpoints on lifted `f_<addr>`
    symbols and writes `<name>.out.txt`. In a breakpoint the guest registers are `((unsigned long*)$rdi)[n]` (lr is
    30) and guest memory is at `0x100000000000 + (addr & 0x7fffffffff)`: the guest space is 39 bits here, and a
    32-bit mask (as in the first look's label script) reads the wrong place for anything on the heap. A host
    function's `hle_<symbol>` body is inlined into `imp_<symbol>` unless `HOS_HLE_STATS=1`: break on `imp_*`.
    gdb does not count a hit when a Python `stop` answers False: log from `stop`. Scripts: `start2.py` (labels of
    every start and lookup; `FUNCS=` picks the functions), `watch.py` (write watch on the manager's label buffer),
    `force.py` (`LABEL=`), `codec.py` (the Opus host functions' first calls; `ZERO=1`), `xyaml.py <file.bin>`
    (HAL's `XBIN` YAML version 6 to JSON: every offset is relative to its own field; node types 1 int, 2 float,
    3 bool, 5 string, 6 map, 7 list).

### 2026-11-17, after S6: far objects at 30 and 15 updates a second

- Report: far animated objects (the Maxim tomato sign across the first stage's village) move at 30 while the game presents
  at 60. Measured first (`work/runs/c1/mask.py`, `reg.py`, `farnear.py`; a shot of each present from the player's save,
  `RX_VK_SHOT_FROM=1500 RX_VK_SHOT_TO=1559`): the tomato and the Waddle Dees beside it change once every fourth present
  (29 of 59 pairs changed, in a burst every fourth), the Waddle Dee near Kirby every present. So the far updates are
  at 15 here, not 30; the cell metric also sees periods of 2 (other objects).
- Cause, in the game's code: each animated object is put in an update level by its squared distance to the camera
  (`main+0x8e2064` on; three cumulative steps in the object's +0x84, +0x88, +0x8c). The dispatch at `main+0x8e2350` does
  level 1 = skip odd frames (`(frame counter [+0x3f4] + object index [+0x38]) & 1`), level 2 = one frame in four
  (`& 3`). Past step 1 an object is level 1 (2 when its sphere is outside the view), past step 2 level 2. With the
  dispatch skipped (an experiment, not kept) the tomato changes in 58 of 59 pairs: this is the whole cause, not the host.
- The Switch 1 60 fps patch (build id D9BA7DB7, three edits): `0x5330d8` and `0x533110` force the main loop's
  per-frame wait count to one vertical sync (frame pacing, already 60 here, not carried over); `0x7f0d1c` turns the step 1
  compare's `b.pl` into a `b`, so objects past step 1 are judged near. The listed addresses are module offsets as they are
  (the `offset_shift 0x100` is not to be added: the words there are `b.eq`, `mul` and `b.pl`, the three sites). The same
  code is in this build (found by the frame-counter dispatch's shape: the counter's offset moved from +0x3e4 to +0x3f4).
- Step 1 alone does not help here: the tomato stayed at one in four (`work/runs/c1/shots_s7c`) because it and its
  neighbours are past step 2. Step 2 skipped as well gives 57 of 59 pairs for the tomato (`shots_s7f`, the built
  game), the near Waddle Dee unchanged. Skipping step 2 goes past what the Switch 1 patch does (a decision of this port, to be confirmed by the
  player's look); the third step (level 3) and the hidden-object level 2 stay the game's.
- Fix: `nx2/kirby_far.py` (gated on main's build id `395fc326...` and on each site's word) writes three branches in the
  lifter's copy of the image before the discovery (`nx2/lift.py`): `main+0x8e21a0` `b.mi` to `nop`, `main+0x8e21f4`
  `b.pl` to `b`, `main+0x8e2180` `b.pl` to `b`. The image the guest reads is the game's. Test: `nx2/test_kirby_far.py`.
  (Not `edit_c`'s text pass: the lifter's other edits are in the instruction stream, and the branch is then gone
  from the lifted C, so no label is left for the skipped path; checked in `work/sa/gen/code_hot_1.c`.)
- Cost, `work/cpu.sh` (20 s of the first stage walking): 18.21 CPU seconds before, 18.43 after; the game's own
  thread 10.24 to 10.56 (that walk is the beach, not the village). In the village run itself (`work/runs/c1/s7b.txt`, `s7f.txt`) both stay at
  60.0 presents a second up to present 1920 and after (the fixed build to 2640).
- Not checked: other stages (their objects have other step values), the game's own scripted cut scenes, whether
  keeping the Switch 1 scope (step 1 only) is wanted somewhere. The player is to look at the tomato spot.

### 2026-11-17, after S6: the microphone rows

- The microphone support is Longshot's Ocarina of Time path (`host/nn_audio_in.c`: the ocarina's input streams), not
  something this game uses. The `sdk` module imports 16 `nn::audio` virtual-input/input-stream functions
  (`ListVirtualInputDevices`, `GetDefaultVirtualInputDevice`, `IsVirtualInputDeviceStreamFormatSupported`, the
  `*InputStream` family and `SetInputStreamGain`); none is referenced anywhere in the lifted image: no call from the
  lifted C and no constant or pointer in the relocated guest image (`work/sa/gen/code_*.c`, `nx2/image.py` `EdenImage.mem`).
  The output thunks do have callers (e.g. `OpenAudioOut`), which is how the difference was checked. `main` imports none
  of the input symbols (only `ListAudioOutputDeviceName` and `SetAudioDeviceOutputVolume`), `GetTrueRawAudioInputDevice`
  is imported by no module, and no run log has an `audio in:` line or an input-stream HLE call under `HOS_HLE_STATS=1`.
- Kept, not deleted, so upstream's (OoT's) fixes to it stay easy to cherry-pick: the menu hides its three rows for this
  game through `is_oot_row` (Microphone, Microphone gain, and the Test microphone action row), so they leave the Audio
  tab, its counts and the control bridge (the two value rows: 65 settings -> 63; the Test row is an action). The saved
  `microphone_device` line is still read and the host still lists devices when the menu opens, but no stream can start:
  the Test row is the only way, and it is hidden.
- Check: `tests/test_mic_rows_hidden.py` (the hiding stays), and the full suite. A menu built alone (the tests) still
  shows the rows, as it shows every row.

### 2026-11-18: the first sync, to Longshot `v3.0.0-rc.7`

- `scripts/sync_upstream.py --to v3.0.0-rc.7` (`544229a2`, 36 commits past the import's base): 204 files changed in
  the imported paths, 191 applied (59 of them new), 13 not applied (12 not tracked here, and the stand-in). Five
  files conflicted, in 8 places, each with one answer: `.gitignore` (both sides), `gpu/vk/vk_api.h` and
  `host/rx_backend.c` (below), and the two checks that assert the interface's version.
- The renderer's interface is version 30 here: Longshot went from 25 to 29 with six new host members, and this
  fork's `origin_lower_left` (26 before the sync) now comes after them, in `MkwVkHost`, in `host/rx_backend.c`'s
  table and in `tests/test_audio_output_devices.py`.
- The rename rule was wrong in two places, found on a trial of this sync and fixed before it:
  `scripts/fsr3_shaders.py` now holds shader text with functions named after Longshot, compiled into headers the rule
  keeps (the file is kept whole), and the mark `(version 26, longshot)` on a member of the interface was renamed (it
  stays). `tests/test_sync_rules.py` has both.
- Longshot now sends things: the crash window's Send posts a crash report, and a launcher's tick sends performance
  statistics, both to Longshot's own services, whose addresses are in `nx2/addresses.ini`. Every key is empty here,
  which turns each use off (`nx2/make_game.py` writes no address into the game folder, `nx2/perf_report.py` has no
  relay). `tests/test_perf_report.py` expects that.
- The stand-in `nx2/oot_patches.py` needed nothing: Longshot's file gained 14 names, and nothing in `nx2/` uses one.
- Checks: `tests/run_all.py` had 19 new failures after the sync. Longshot's own tree at the same revision, checked out
  under `work/` and run on the same machine, fails 16 of them too (45 in all): checks whose source moved on without
  them. Those are left out, with one script and three checks bound to things left out (`PROVENANCE.md` has the
  lists). One was this fork's: `nx2/test_kirby_far.py` named the lift's call, which Longshot reworded; the merge of
  `nx2/lift.py` itself was right. After that: 530 passed, 5 failed, 64 skipped, the five being the ones that fail
  only in the sandbox the checks ran in (a run outside it, `work/runs/s7/tests.txt`, has 0 failed).
- In the game: `work/boot.sh rc7 60 --lift` (the lift with the hot list, the build with the profiles, 0 files
  failed, then 60 s headless without movies or sound): 3599 frames presented, 60.0 a second over the last 5 s, every
  present interval between 15.5 and 17.8 ms (`work/runs/sync-rc7/rc7.txt`). No picture was looked at and nothing was
  played: that is still to do by hand.
- Not looked at: what Longshot's 36 commits change for this game beyond the checks and that run (its new settings
  rows, the fullscreen monitor choice, the crash window).

### 2026-11-18: the nightly sync

- `scripts/sync_nightly.py` does the sync unattended (the sync-upstream skill, section 8): Longshot's clone fetched,
  the agent at work in a clone of this repository (`work/sync/tree`), and `main` moved by fast-forward only when a
  gate the script runs itself passes. A stopped night is kept, never discarded.
- The gate runs the game. `INHALE_WORK` and `INHALE_DUMP` (`nx2/kit.py`) give the lift, the build and the run a work
  folder apart from the one a person builds in, reading the same dump: `work/sync/game`. Measured there on the tree
  at `v3.0.0-rc.7`, with no hot list and no profiles: lift 17 s, build 73 s from an empty object cache (24 jobs),
  then 60 s with `HOS_HEADLESS=1 HOS_AUDIO=0 HOS_NO_MOVIES=1` and a new user folder: 3301 frames presented, 60.0 a
  second over the last 5 s. With the cache filled the three take 81 s together.
- The gate passes the game when it is still running at 60 s and has presented 1800 frames. It does not look at a
  picture and plays nothing: a sync that draws wrong or breaks a level still lands.

### 2026-11-18: the second sync, to Longshot `9af4808f`

- `scripts/sync_upstream.py --to 9af4808f` (66 commits past `v3.0.0-rc.7`), run by the nightly agent in
  `work/sync/tree`: 347 files changed in the imported paths, 315 applied (88 of them new), 32 not applied (31 not
  tracked here, and the stand-in). Five files conflicted, in 7 places, each with one answer: `gpu/vk/vk_api.h`,
  `host/rx_backend.c` and `tests/test_audio_output_devices.py` (the interface, below), `nx2/lift.py` (both sides:
  Longshot's entry hooks, then this fork's `other_game`) and `nx2/make_game.py` (Longshot's new sentence with this
  fork's wording of its end).
- `git apply -3` runs git's rerere when it leaves conflicts. With `rerere.enabled` and `rerere.autoupdate` set (they
  are in this PC's `~/.gitconfig`) and a resolution of the same conflict recorded in the clone's `.git/rr-cache` (a
  trial run to `310e7c9d` the same night had left all five), git writes the recorded resolutions into the files and
  then stops at the index lock it holds itself (`fatal: Unable to create '.git/index.lock': File exists`): the work
  tree is whole, with no conflict marks, and nothing is staged, so `git diff --diff-filter=U` lists nothing and the
  new files are untracked. That night the work tree was compared with a second run in a scratch clone with rerere off
  (the same files, the same bytes but for the five), the five replayed resolutions were read against the rules of the
  sync-upstream skill, and the paths were staged by name. `scripts/sync_upstream.py` does not turn rerere off for its
  `git apply`; it is not changed here.
- The renderer's interface is version 34 here: Longshot went from 29 to 33 (the pose sample's `perf_tracking`, the
  renderer's `nvn_invalidate_quick`, `rumble_test`, seven NFC members), and this fork's `origin_lower_left` comes after
  them in `MkwVkHost` and in `host/rx_backend.c`'s table. Longshot's list of names in
  `tests/test_audio_output_devices.py` now ends at its own `perf_tracking` and is checked as one run from `take_text`,
  so this fork's member is no longer in that list: a line of its own there asserts that it is the last member and the
  last entry of the table.
- Longshot's lift now puts the host's `memcpy`, `memmove`, `memset`, `memcmp`, `strlen` and `strcmp` first in the
  SDK's functions of those names (`nx2/entry_hooks.py`, `host/nn_libc.c`), for any game. In this game's `sdk` it finds
  all six (`entry hooks spliced: 6`), and the game's log says so (`libc: ... are the host's`). `HOS_GUEST_LIBC=1`
  gives the game's own back. It is the one change of this sync known to alter what this game runs.
- Section 13 above is new: Longshot's renderer now points at rules in its own design notes
  (`// doc: docs/design.md#13-frame-generations-presents-as-rules`), which `tests/test_doc_anchors.py` follows, so the
  rules are carried here under Longshot's number, as they are at `9af4808f`. Nothing brings Longshot's later changes
  to them over: `docs/` is not an imported path.
- The stand-in `nx2/oot_patches.py` needed nothing: Longshot's file gained 11 names (the horse's jump, the texture
  heap's compaction), and nothing in `nx2/` uses one. `host/oot_tex_compact.c` is reached only from code those patches
  edit.
- Checks: before the sync `tests/run_all.py` had 0 failed (536 passed, 64 skipped; 590 and 10 with the Vulkan and
  SPIR-V headers given). After it, 12 failed. Five fail in Longshot's own tree at the same revision for the same reason
  (checked out under `work/` and run on the same machine) and are left out, with two more that run only with the
  Vulkan headers and fail in both trees there. Five are bound to things left out (three read Longshot's
  `docs/development.md`, two the text of its `nx2/oot_patches.py`) and are left out with their fixtures, as are eleven
  build outputs of a builder test project that Longshot committed (`tests/builder_workers/obj/`). `PROVENANCE.md` has
  the lists. Two were this fork's to repair: `tests/test_doc_anchors.py` (section 13) and Longshot's new
  `tests/test_share_message_i18n.py`, whose fixture compiles the menu's lookup and needed this fork's rows
  (`menu_i18n_inhale.h`). After that: 556 passed, 0 failed, 79 skipped, and 625 passed, 0 failed, 10 skipped with the
  headers given (`INHALE_VULKAN_HEADERS` and `INHALE_SPIRV_HEADERS`, a folder holding only them; Longshot's own tree
  reads `LONGSHOT_VULKAN_HEADERS`).
- In the game, in the clone's own work folder, no hot list and no profiles: lift 18 s, build 12 s (0 files failed;
  the trial's object cache was there), then 60 s with `HOS_HEADLESS=1 HOS_AUDIO=0 HOS_NO_MOVIES=1`: 3288 frames
  presented, 60.0 a second over the last 5 s, still running at the end. No picture was looked at and nothing was
  played.
- Not looked at: what Longshot's 66 commits change for this game beyond the checks and that run (the Insert menu's
  NFC tab and Rumble row, the log's redaction, long paths, the present queue and frame generation changes).

### 2026-11-18: the release packages

`packaging/` (section 10) built here at `eb25254` plus the packaging changes: `Inhale-x86_64.AppImage` 235 MB,
`Inhale-Setup-x64.exe` 127 MB (its folder 1.1 GB). Each prebuilt its 316 third-party objects with 0 failures.
`tests/run_all.py`: 560 passed, 0 failed, 79 skipped.

- Linux, the AppImage in clean `ubuntu:22.04` and `fedora:latest` containers with no compiler: `--cli --check` on the
  package says "Linux build prerequisites: OK" and accepts it. A whole build in the `ubuntu:22.04` container
  (`--cli --game <.nup>`): `@@times 135 81 -1`, `@@done`. That folder, started on this PC through `--play` with
  `PATH=/usr/bin:/bin` and a clean environment, ran at 60.0 presents a second for 60 s. No picture was looked at.
- Windows, on aubox (Windows 11, RTX 2080 SUPER), as a normal user with no compiler on `PATH`: the silent install
  (`/S`) into `%LOCALAPPDATA%\Programs\Inhale`, with its Start menu shortcut and its "Apps & features" entry. The window's
  own runner (`gui/inhale_builder.Child`) with the installed Python: `--check --game <dump folder>` said "the
  compiler: ...\llvm-mingw (no Visual Studio needed)" and ok. A whole build from the extracted folders (`--game` with
  `exefs/` and `aoc/`) took 306 s, prepared the shaders and ended with `@@done`. This is the first run of both the
  llvm-mingw route and the folder input on a real dump. Started as the window's Play button starts it, in the
  disconnected desktop session, the game ran at 60.0 presents a second. No picture was looked at, because the console
  session is another user's. The silent uninstall left the game folder and removed the install folder, both shortcuts
  and the uninstall key.
- Cancel: the runner's `kill()` during the compile took the build's session from 25 processes to 0 (Linux). The
  Windows path (`taskkill /T`) was not tried.
- Both builds print a traceback from `nx2/shader_census.py`, which reads `romfs/Pack/ZsDic.pack.zs` (the other game's
  file), then "the shader list was not made". It is make_game's own and the build goes on. Not looked into.
- Played by hand (the user): the AppImage's window, a build into the default `~/Games/Inhale`, Play: the game works.
- The release workflow (run 44315474239, from a branch with a commit adding it to the push trigger, dropped after):
  the three jobs passed, and the `nightly` prerelease got `Inhale-x86_64.AppImage` (245 MB), `Inhale-Setup-x64.exe`
  (132 MB) and `SHA256SUMS`. Downloaded, both match the sums; the AppImage carries the hot list and no profiles, and
  its `--cli --check` in a clean `ubuntu:22.04` container accepts the package.
- Not tried: the window clicked through on Windows; Cancel there.

### 2026-11-18: played by hand past the first boss

- The user played the AppImage's build (`~/Games/Inhale`, Linux, RX 7900 XTX, RADV, Mesa 26.2.6) through the first
  world's stages, its boss and several special stages. Nothing else was seen to go wrong.
- With frame generation on, the game hung now and then for a few seconds and then went on. The options file had
  V-Sync on and Frame pacing on (`vsync=1`, `frame_pacing=1`); the multiplier was not noted, and frame generation is
  now off there. No log was kept. Section 13's rules were measured by upstream on NVIDIA under Windows only; this
  is the first report from RADV. Not looked into.

### 2026-11-18: RecompLauncher's manifest and the Windows zip

`packaging/recomplauncher.json`, `Inhale.exe` and `Inhale-Windows-x64.zip` (section 10), checked here at `6d5040d` plus
the changes. `tests/run_all.py`: 561 passed, 0 failed, 79 skipped.

- The manifest validates against RecompLauncher's `schema.json` (`jsonschema`).
- `packaging/linux/docker.sh windows`: `Inhale-Setup-x64.exe` 127 MB and `Inhale-Windows-x64.zip` 270 MB (deflate,
  against the installer's LZMA), with `Inhale.exe` and `recomplauncher.json` at its top. `docker.sh`: the AppImage,
  235 MB, with `recomplauncher.json` at its root.
- Under Wine, from the unpacked zip: `Inhale.exe --cli --help` prints `make_game.py`'s usage; `--cli -c` returns 2,
  `make_game.py`'s own code; `--play <empty folder>` says "no built game" and returns 1. An argument with spaces,
  quotes and a trailing backslash reaches `make_game.py` whole. A non-ASCII argument came through mangled, as it does
  when Wine starts `python.exe` directly too, so that part is not shown either way.
- The AppImage: `--cli --prepare --game <the other game's .nup>` printed `progress` lines, then
  `error This is build e0f3ccfa. Inhale supports build 395fc326.`, and returned 1. It unpacked the whole 26 GB first,
  then removed it. `--play ~/Games/Inhale` started the build there: 59.5 presents a second, the window closed at 25 s.
  With no argument, the window was still up at 15 s.
- The AppImage, as the manifest starts it: `--cli --prepare --game <this game's .nup> --out work/rl/out` returned 0
  in 48 s (the object cache from earlier builds), with 469 `progress` lines on stdout, from `0.000 Reading your game
  files` to `1.000 Done`, and the known `shader_census.py` traceback (section 9, the release packages) on stderr.
  `--play work/rl/out` ran at 60.0 presents a second at 30 s. No picture was looked at.
- Not tried: RecompLauncher itself, and the zip on Windows.
