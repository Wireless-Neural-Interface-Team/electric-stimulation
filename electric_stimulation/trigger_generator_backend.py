# -*- coding: utf-8 -*-
"""
Backend for NI-DAQmx trigger generation.

Contains:
- build_channel_path: build device/channel path
- DAQWorker: worker thread for DAQ output (infinite/finite, initial_trigger_delay, 0V on exit)
"""

import time
from ctypes import byref, c_int32

import numpy as np
from PyQt5.QtCore import QObject, pyqtSignal, pyqtSlot

# Optional: PyDAQmx for NI-DAQmx hardware access
try:
    import PyDAQmx as nidaq
    DAQ_AVAILABLE = True
except ImportError:
    DAQ_AVAILABLE = False
    nidaq = None


def build_channel_path(device_str, channel_str):
    """
    Build full channel path for NI-DAQmx.
    Example: Dev2 + ao0 -> Dev2/ao0
    """
    dev = device_str.strip() or "Dev2"
    ch = channel_str.strip() or "ao0"
    return f"{dev}/{ch}" if ch else dev


class DAQWorker(QObject):
    """
    Worker for DAQ generation (runs in QThread).
    Emits: started (when output begins), finished, error(str).
    """
    finished = pyqtSignal()
    error = pyqtSignal(str)
    started = pyqtSignal()

    def __init__(self, device, sampling_rate, trigger_duration, inter_trigger_interval,
                 infinite, nb_triggers, initial_trigger_delay=5.0):
        super().__init__()
        self.device = device
        self.sampling_rate = sampling_rate
        self.trigger_duration = trigger_duration
        self.inter_trigger_interval = inter_trigger_interval
        self.infinite = infinite
        self.nb_triggers = nb_triggers
        self.initial_trigger_delay = initial_trigger_delay
        self._stop_requested = False

    def stop(self):
        """Request worker to stop (called from main thread)."""
        self._stop_requested = True

    @pyqtSlot()
    def run(self):
        """Main generation logic (runs in worker thread)."""
        try:
            if not DAQ_AVAILABLE:
                self.error.emit("PyDAQmx is not installed.")
                return

            # Compute sample counts from durations
            initial_delay_samples = int(self.initial_trigger_delay * self.sampling_rate)
            trigger_samples = int(self.trigger_duration * self.sampling_rate)
            interval_samples = int(self.inter_trigger_interval * self.sampling_rate)
            samples_per_cycle = trigger_samples + interval_samples

            # Build one cycle: trigger at 2V, then interval at 0V
            Sig_cycle = np.zeros(samples_per_cycle)
            Sig_cycle[:trigger_samples] = 2.0

            read = c_int32()
            t = None
            if self.infinite:
                # Initial delay once at start, then repeat (trigger+interval) cycle
                if initial_delay_samples > 0:
                    # Phase 1: Output initial delay (0V) once at start
                    self.started.emit()
                    t_delay = nidaq.Task()
                    t_delay.CreateAOVoltageChan(self.device, None, -10.0, 10.0,
                                              nidaq.DAQmx_Val_Volts, None)
                    t_delay.CfgSampClkTiming("", self.sampling_rate, nidaq.DAQmx_Val_Rising,
                                          nidaq.DAQmx_Val_FiniteSamps, initial_delay_samples)
                    t_delay.WriteAnalogF64(initial_delay_samples, False, 10,
                                         nidaq.DAQmx_Val_GroupByScanNumber,
                                         np.zeros(initial_delay_samples), byref(read), None)
                    t_delay.StartTask()
                    # Poll for completion or stop; WaitUntilTaskDone raises on timeout
                    delay_timeout = self.initial_trigger_delay + 5
                    elapsed = 0
                    while not self._stop_requested and elapsed < delay_timeout:
                        try:
                            t_delay.WaitUntilTaskDone(1.0)
                            break  # Task completed
                        except Exception:
                            elapsed += 1.0  # Timeout, keep polling
                    t_delay.StopTask()
                    t_delay.ClearTask()
                    if self._stop_requested:
                        t = None  # User stopped during initial delay, skip main task
                    else:
                        # Phase 2: Continuous trigger+interval cycle
                        t = nidaq.Task()
                        t.CreateAOVoltageChan(self.device, None, -10.0, 10.0,
                                             nidaq.DAQmx_Val_Volts, None)
                        t.CfgSampClkTiming("", self.sampling_rate, nidaq.DAQmx_Val_Rising,
                                          nidaq.DAQmx_Val_ContSamps, samples_per_cycle)
                        t.WriteAnalogF64(samples_per_cycle, False, 10,
                                         nidaq.DAQmx_Val_GroupByScanNumber,
                                         Sig_cycle, byref(read), None)
                        t.StartTask()
                else:
                    # No initial delay: start continuous cycle directly
                    t = nidaq.Task()
                    t.CreateAOVoltageChan(self.device, None, -10.0, 10.0,
                                         nidaq.DAQmx_Val_Volts, None)
                    t.CfgSampClkTiming("", self.sampling_rate, nidaq.DAQmx_Val_Rising,
                                      nidaq.DAQmx_Val_ContSamps, samples_per_cycle)
                    t.WriteAnalogF64(samples_per_cycle, False, 10,
                                     nidaq.DAQmx_Val_GroupByScanNumber,
                                     Sig_cycle, byref(read), None)
                    t.StartTask()
            else:
                # Finite mode: initial_delay + nb_triggers × (trigger + interval)
                data = np.concatenate([
                    np.zeros(initial_delay_samples),
                    np.tile(Sig_cycle, self.nb_triggers)
                ])
                nb_samples = len(data)
                t = nidaq.Task()
                t.CreateAOVoltageChan(self.device, None, -10.0, 10.0,
                                     nidaq.DAQmx_Val_Volts, None)
                t.CfgSampClkTiming("", self.sampling_rate, nidaq.DAQmx_Val_Rising,
                                  nidaq.DAQmx_Val_FiniteSamps, nb_samples)
                t.WriteAnalogF64(nb_samples, False, 10,
                                 nidaq.DAQmx_Val_GroupByScanNumber,
                                 data, byref(read), None)
                t.StartTask()

            # Emit started for GUI timer (initial delay case already emitted)
            if self.infinite and initial_delay_samples == 0:
                self.started.emit()
            elif not self.infinite:
                self.started.emit()

            # Run main task until stop or completion
            if t is not None:
                if self.infinite:
                    while not self._stop_requested:
                        time.sleep(0.1)  # Poll for stop request
                else:
                    timeout = self.initial_trigger_delay + self.nb_triggers * (self.inter_trigger_interval + self.trigger_duration) + 10
                    elapsed = 0
                    while not self._stop_requested and elapsed < timeout:
                        try:
                            t.WaitUntilTaskDone(1.0)
                            break  # Task completed
                        except Exception:
                            elapsed += 1.0  # Timeout, keep polling

                t.StopTask()
                t.ClearTask()

        except Exception as e:
            self.error.emit(str(e))
        finally:
            # Safety: always set output to 0V on exit (stop, completion, or error)
            if DAQ_AVAILABLE:
                # First, stop and release any running task that might hold the channel
                try:
                    if t is not None:
                        try:
                            t.StopTask()
                        except Exception:
                            pass
                        try:
                            t.ClearTask()
                        except Exception:
                            pass
                except NameError:
                    pass
                time.sleep(0.05)  # Allow hardware to release the channel
                t_zero = None
                try:
                    t_zero = nidaq.Task()
                    t_zero.CreateAOVoltageChan(self.device, None, -10.0, 10.0,
                                               nidaq.DAQmx_Val_Volts, None)
                    if hasattr(t_zero, 'WriteAnalogScalarF64'):
                        t_zero.StartTask()
                        t_zero.WriteAnalogScalarF64(1, 10.0, 0.0, None)
                    else:
                        read_zero = c_int32()
                        t_zero.CfgSampClkTiming("", 1000, nidaq.DAQmx_Val_Rising,
                                               nidaq.DAQmx_Val_FiniteSamps, 1)
                        t_zero.WriteAnalogF64(1, True, 10, nidaq.DAQmx_Val_GroupByScanNumber,
                                              np.array([0.0], dtype=np.float64), byref(read_zero), None)
                        try:
                            t_zero.WaitUntilTaskDone(10.0)
                        except Exception:
                            pass
                except Exception:
                    pass
                finally:
                    if t_zero is not None:
                        try:
                            t_zero.StopTask()
                            t_zero.ClearTask()
                        except Exception:
                            pass
            self.finished.emit()
