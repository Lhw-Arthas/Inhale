"""Where the packaged build tools are, as the variables nx2/make_game.py and nx2/build.py read; and the environment the game
plays in, without them. The same places packaging/linux/AppRun sets, so the window's build and --cli agree.

The source root (the folder that holds nx2/) is:
  Linux AppImage    <AppDir>/usr/share/inhale        tools in <AppDir>/usr/lib/inhale/{llvm,sysroot,ffmpeg,sdl2,cpm}
  Windows install   <install>                        tools in <install>/{llvm-mingw,cpm}, SDL in <install>/third_party/sdl2
  a source checkout the repository                   no bundled tools: the system's, as the README says
"""
import os
import sys

GUI = os.path.dirname(os.path.abspath(__file__))
# (packaging/gui in a checkout and in the AppImage; gui/ beside nx2/ in the Windows install)
ROOT = os.path.dirname(GUI) if os.path.isdir(os.path.join(os.path.dirname(GUI), "nx2")) else \
    os.path.dirname(os.path.dirname(GUI))

# (make_game.game_env drops the same: the AppImage runtime's and the tools' variables, so the game loads its own SDL and the
# system's Vulkan)
PLAY_DROP = ("INHALE_", "PYTHON", "APPDIR", "APPIMAGE", "ARGV0", "OWD", "RX_CPM", "RX_TARGET", "EMSDK", "LONGSHOT_MINGW")


def linux_tools(root=ROOT):
    """{variable: path} for the AppImage's tools, or {} when root is not inside one"""
    lib = os.path.join(os.path.dirname(os.path.dirname(root)), "lib", "inhale")
    if not os.path.isfile(os.path.join(lib, "llvm", "upstream", "bin", "clang")):
        return {}
    return {
        "EMSDK": os.path.join(lib, "llvm"),   # (third_party/a64-kit/tools/toolchain.py: clang in EMSDK/upstream/bin)
        "INHALE_SYSROOT": os.path.join(lib, "sysroot"),
        "INHALE_FFMPEG": os.path.join(lib, "ffmpeg"),
        "INHALE_SDL2": os.path.join(lib, "sdl2", "libSDL2-2.0.so.0"),
        "RX_CPM": os.path.join(lib, "cpm"),
    }


def windows_tools(root=ROOT):
    """{variable: path} for the installer's tools, or {} when root has none. make_game.py finds <root>/llvm-mingw and build.py
    <root>/cpm by themselves; named here all the same, so a LONGSHOT_MINGW or RX_CPM set on the PC for something else is not
    what the build takes"""
    mingw = os.path.join(root, "llvm-mingw")
    if not os.path.isfile(os.path.join(mingw, "bin", "clang.exe")):
        return {}
    return {"LONGSHOT_MINGW": mingw, "RX_CPM": os.path.join(root, "cpm")}


def build_env(environ=None, root=ROOT, windows=None):
    """The environment make_game.py runs in"""
    env = dict(os.environ if environ is None else environ)
    windows = os.name == "nt" if windows is None else windows
    tools = windows_tools(root) if windows else linux_tools(root)
    env.update(tools)
    if tools:
        env.pop("INHALE_MSVC", None)   # (the bundled compiler, not a Visual Studio the PC may have)
    env["PYTHONUTF8"] = "1"
    env["PYTHONUNBUFFERED"] = "1"
    return env


def play_env(environ=None):
    """The environment the game starts in: as the player's own double click would give it"""
    env = {k: v for k, v in (os.environ if environ is None else environ).items() if not k.startswith(PLAY_DROP)}
    env.pop("LD_LIBRARY_PATH", None)
    return env


def python():
    """The Python that runs make_game.py: this one (the bundled one in a package), python.exe for pythonw.exe on Windows so
    the child's output can be read"""
    exe = sys.executable
    if os.name == "nt" and os.path.basename(exe).lower() == "pythonw.exe":
        console = os.path.join(os.path.dirname(exe), "python.exe")
        if os.path.isfile(console):
            return console
    return exe
