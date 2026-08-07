#!/usr/bin/env python3
"""Stable entrypoint for JANUS Meta271 sensory lattice.

Pins the WAV codec to the already-proven Meta100 parameters before delegating
to janus_multiconversion_gate.py. Kept separate so the failed experimental DSP
parameters remain visible in branch history instead of being silently erased.
"""
import janus_multiconversion_gate as lattice

lattice.TONE_SECONDS = 0.080
lattice.GAP_SECONDS = 0.010
lattice.LEAD_SECONDS = 0.050
lattice.BASE_FREQ = 300.0
lattice.BYTE_STEP_HZ = 25.0

if __name__ == "__main__":
    lattice.main()
