# -*- coding: utf-8 -*-
"""
Launcher for WaveGene - NI-DAQmx pulse generator.

Runs the GUI (wavegene_gui) which uses the backend (wavegene_backend)
for DAQ logic.
"""

import sys

from wavegene_gui import main

if __name__ == "__main__":
    sys.exit(main())
