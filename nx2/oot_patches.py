"""Edits of the lifted C after the lift writes it (nx2/lift.py, nx2/chunks.py edit_c): none in Inhale.

Upstream's file of this name holds text matched against another game's lifted code. That text is not carried here: this
stand-in keeps the names the lift calls, with empty tables, so the lift's edit passes run and change nothing. A game
patch for Inhale goes in a file of its own (nx2/kirby_*.py), gated on this game's build id.
"""
import collections

LIFE_BUILD_ID = None   # (no build is "the supported build" of these patches: a build id never equals None)
OUT_EDITS = []


def patch_file(s, name, protect_hearts=False):
    """One lifted file: (its text, the places counted in it, the lines to print)"""
    return s, collections.Counter(), []


def report(paths, counts, protect_hearts=False):
    """The warnings from the files' counts: none"""


def output_size_file(s, name):
    """One lifted file: (its text, each place's count in it, the lines to print)"""
    return s, [], []


def check_output_size(found, required=False):
    """found: each place's count over all the files"""
