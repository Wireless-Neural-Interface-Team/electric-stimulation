# -*- coding: utf-8 -*-
"""
Electric Stimulation - NI-DAQmx trigger generator for electrical stimulation.

Provides:
- trigger_generator_backend: DAQWorker, build_channel_path for NI-DAQmx output
- trigger_generator_gui: TriggerGeneratorWindow, main() for the PyQt5 GUI
"""

from .trigger_generator_backend import (
    DAQ_AVAILABLE,
    DAQWorker,
    build_channel_path,
)
from .trigger_generator_gui import TriggerGeneratorWindow, main

__all__ = [
    "DAQ_AVAILABLE",
    "DAQWorker",
    "TriggerGeneratorWindow",
    "build_channel_path",
    "main",
]
__version__ = "0.1.0"
