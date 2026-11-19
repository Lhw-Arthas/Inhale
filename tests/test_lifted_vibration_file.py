"""The lift leaves the SDK's vibration file reader as lifted code (nx2/standalone.py, hle_set).

nn::hid::ParseVibrationFile and nn::hid::RetrieveVibrationValue are free functions of an OS-facing namespace, so a
game that imports them got a stub for each: the first left the file's info zeroed and the second wrote no value, and
the game played none of its .bnvib files (issue #2: no rumble in the game). Both only read the bytes they are given
and reach no system service, so they run as the SDK has them. A function of the same namespace that the runtime does
not have and that does reach the system (nn::hid::EnableVibrationNxCompatibleMode) is still stubbed, and one the
runtime has (nn::hid::SendVibrationValue) is still its HLE's. Fake modules, no game.

    python -I -B tests/test_lifted_vibration_file.py
"""
import contextlib
import importlib.util
import io
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "nx2"))   # (python -I leaves it off the path: standalone.py imports kit and toolchain)
spec = importlib.util.spec_from_file_location("standalone_under_test", ROOT / "nx2" / "standalone.py")
standalone = importlib.util.module_from_spec(spec)
spec.loader.exec_module(standalone)

PARSE = "_ZN2nn3hid18ParseVibrationFileEPNS0_17VibrationFileInfoEPNS0_26VibrationFileParserContextEPKvm"
RETRIEVE = "_ZN2nn3hid22RetrieveVibrationValueEPNS0_14VibrationValueEiPNS0_26VibrationFileParserContextE"
NX_MODE = "_ZN2nn3hid31EnableVibrationNxCompatibleModeEv"
SEND = "_ZN2nn3hid18SendVibrationValueERKNS0_21VibrationDeviceHandleERKNS0_14VibrationValueE"


def check(what, ok):
    if not ok:
        raise SystemExit("FAIL: " + what)


def main():
    names = [PARSE, RETRIEVE, NX_MODE, SEND]
    sym = lambda name, defined: {"name": name, "defined": defined, "type": "func"}
    modules = [SimpleNamespace(name="main", symbols=[sym(n, False) for n in names]),
               SimpleNamespace(name="sdk", symbols=[sym(n, True) for n in names])]
    with mock.patch.object(standalone, "implemented", lambda host=None: {"imp_" + SEND}), \
            contextlib.redirect_stdout(io.StringIO()):
        hle, stubbed = standalone.hle_set(modules)
    check("nn::hid::ParseVibrationFile is not stubbed", PARSE not in stubbed)
    check("nn::hid::RetrieveVibrationValue is not stubbed", RETRIEVE not in stubbed)
    check("neither is hooked: both run as the SDK's lifted code", PARSE not in hle and RETRIEVE not in hle)
    check("a function the runtime lacks that reaches the system is still stubbed", NX_MODE in stubbed)
    check("a function the runtime has is its HLE's, not a stub", SEND in hle and SEND not in stubbed)
    print("ok: the vibration file reader stays lifted; %d stubbed, %d hooked" % (len(stubbed), len(hle)))


if __name__ == "__main__":
    main()
