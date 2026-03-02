# -*- coding: utf-8 -*-
"""
GUI for Trigger Generator.

Displays parameters, state indicator, and controls.
Uses trigger_generator_backend for DAQ logic.
"""

import json
import sys
import time
from datetime import datetime
from pathlib import Path

from PyQt5.QtCore import Qt, QThread, QTimer
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QGroupBox, QFormLayout, QSpinBox, QDoubleSpinBox, QCheckBox,
    QPushButton, QLabel, QMessageBox, QLineEdit, QFrame, QFileDialog
)
try:
    from .trigger_generator_backend import build_channel_path, DAQWorker, DAQ_AVAILABLE
except ImportError:
    from trigger_generator_backend import build_channel_path, DAQWorker, DAQ_AVAILABLE


def _app_dir():
    """Return app directory (next to exe when frozen, else script dir)."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).parent


class TriggerGeneratorWindow(QMainWindow):
    """Main application window for trigger generation control."""

    def __init__(self):
        super().__init__()
        self.worker = None
        self.worker_thread = None
        self.state_timer = None
        self.state_start_time = None
        self.worker_params = None
        self.init_ui()
        self.load_params_from_json(silent=True)

    def init_ui(self):
        """Build the main window layout and widgets."""
        self.setWindowTitle("Trigger Generator - NI-DAQmx")
        self.setMinimumWidth(400)

        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)

        # --- Load Parameters (top left) ---
        top_bar = QHBoxLayout()
        self.load_btn = QPushButton("Load Parameters")
        self.load_btn.setMinimumHeight(32)
        self.load_btn.clicked.connect(self.load_params_from_json)
        top_bar.addWidget(self.load_btn)
        top_bar.addStretch()
        layout.addLayout(top_bar)

        # --- Parameters group ---
        params_group = QGroupBox("Parameters")
        params_layout = QFormLayout(params_group)

        # Device and channel (e.g. Dev2, ao0)
        self.device_edit = QLineEdit()
        self.device_edit.setPlaceholderText("Dev1, Dev2, ...")
        self.device_edit.setText("Dev2")
        params_layout.addRow("Device NI-DAQmx:", self.device_edit)

        self.channel_edit = QLineEdit()
        self.channel_edit.setPlaceholderText("ao0, ao1, ...")
        self.channel_edit.setText("ao0")
        params_layout.addRow("Channel:", self.channel_edit)

        # Sampling rate in Hz (output update frequency)
        self.sampling_rate_spin = QDoubleSpinBox()
        self.sampling_rate_spin.setRange(100, 100000)
        self.sampling_rate_spin.setValue(1000)
        self.sampling_rate_spin.setSuffix(" Hz")
        self.sampling_rate_spin.setDecimals(0)
        params_layout.addRow("Sampling rate:", self.sampling_rate_spin)

        # Trigger duration at 2V (seconds)
        self.trigger_duration_spin = QDoubleSpinBox()
        self.trigger_duration_spin.setRange(0.001, 60)
        self.trigger_duration_spin.setValue(0.2)
        self.trigger_duration_spin.setSuffix(" s")
        self.trigger_duration_spin.setDecimals(3)
        params_layout.addRow("Trigger duration (2V):", self.trigger_duration_spin)

        # Time at 0V between triggers (seconds)
        self.inter_trigger_spin = QDoubleSpinBox()
        self.inter_trigger_spin.setRange(0, 3600)
        self.inter_trigger_spin.setValue(20)
        self.inter_trigger_spin.setSuffix(" s")
        self.inter_trigger_spin.setDecimals(1)
        params_layout.addRow("Inter-trigger interval:", self.inter_trigger_spin)

        # Initial 0V period before first trigger (seconds)
        self.initial_trigger_delay_spin = QDoubleSpinBox()
        self.initial_trigger_delay_spin.setRange(0, 300)
        self.initial_trigger_delay_spin.setValue(5)
        self.initial_trigger_delay_spin.setSuffix(" s")
        self.initial_trigger_delay_spin.setDecimals(1)
        self.initial_trigger_delay_spin.setToolTip("Time at 0V before the first trigger")
        params_layout.addRow("Initial trigger delay:", self.initial_trigger_delay_spin)

        # Infinite: repeat forever; else use nb_triggers
        self.infinite_check = QCheckBox("Repeat indefinitely")
        self.infinite_check.setChecked(True)
        self.infinite_check.toggled.connect(self.on_infinite_toggled)
        params_layout.addRow("", self.infinite_check)

        self.nb_triggers_spin = QSpinBox()
        self.nb_triggers_spin.setRange(1, 10000)
        self.nb_triggers_spin.setValue(5)
        self.nb_triggers_spin.setEnabled(False)
        params_layout.addRow("Number of triggers:", self.nb_triggers_spin)

        layout.addWidget(params_group)

        # --- Action buttons ---
        btn_layout = QHBoxLayout()
        self.start_btn = QPushButton("Start")
        self.start_btn.setMinimumHeight(40)
        self.start_btn.setFont(QFont("", 11, QFont.Bold))
        self.start_btn.clicked.connect(self.start_generation)
        self.start_btn.setStyleSheet("background-color: #4CAF50; color: white;")

        self.stop_btn = QPushButton("Stop")
        self.stop_btn.setMinimumHeight(40)
        self.stop_btn.setFont(QFont("", 11, QFont.Bold))
        self.stop_btn.clicked.connect(self.stop_generation)
        self.stop_btn.setEnabled(False)
        self.stop_btn.setStyleSheet("background-color: #f44336; color: white;")

        btn_layout.addWidget(self.start_btn)
        btn_layout.addWidget(self.stop_btn)
        layout.addLayout(btn_layout)

        # --- State indicator: shows current phase (Initial trigger delay, Trigger, 0V) + countdown ---
        self.state_frame = QFrame()
        self.state_frame.setFrameStyle(QFrame.StyledPanel)
        self.state_frame.setMinimumHeight(60)
        self.state_frame.setStyleSheet("""
            QFrame { background-color: #e0e0e0; border-radius: 8px; }
        """)
        state_layout = QVBoxLayout(self.state_frame)
        self.state_label = QLabel("—")
        self.state_label.setAlignment(Qt.AlignCenter)
        self.state_label.setFont(QFont("", 18, QFont.Bold))
        self.state_label.setStyleSheet("color: #666;")
        state_layout.addWidget(self.state_label)
        self.time_label = QLabel("—")
        self.time_label.setAlignment(Qt.AlignCenter)
        self.time_label.setFont(QFont("", 14))
        self.time_label.setStyleSheet("color: #666;")
        state_layout.addWidget(self.time_label)
        layout.addWidget(self.state_frame)

        # --- Total elapsed time (subtle display) ---
        self.time_total_frame = QFrame()
        self.time_total_frame.setFrameStyle(QFrame.NoFrame)
        self.time_total_frame.setMaximumHeight(32)
        self.time_total_frame.setStyleSheet("QFrame { background-color: transparent; }")
        time_total_layout = QHBoxLayout(self.time_total_frame)
        time_total_layout.setContentsMargins(4, 2, 4, 2)
        time_total_label_txt = QLabel("Total time:")
        time_total_label_txt.setStyleSheet("color: #999; font-size: 11px;")
        time_total_layout.addWidget(time_total_label_txt)
        self.time_total_label = QLabel("0:00")
        self.time_total_label.setFont(QFont("", 11))
        self.time_total_label.setStyleSheet("color: #999;")
        time_total_layout.addWidget(self.time_total_label)
        time_total_layout.addStretch()
        layout.addWidget(self.time_total_frame)

        # Disable start if PyDAQmx not installed
        if not DAQ_AVAILABLE:
            self.start_btn.setEnabled(False)
            self.start_btn.setToolTip("PyDAQmx is not installed")

    def on_infinite_toggled(self, checked):
        """Enable nb_triggers only when not in infinite mode."""
        self.nb_triggers_spin.setEnabled(not checked)

    def set_params_enabled(self, enabled):
        """Enable or disable all parameter fields."""
        self.device_edit.setEnabled(enabled)
        self.channel_edit.setEnabled(enabled)
        self.sampling_rate_spin.setEnabled(enabled)
        self.trigger_duration_spin.setEnabled(enabled)
        self.inter_trigger_spin.setEnabled(enabled)
        self.initial_trigger_delay_spin.setEnabled(enabled)
        self.infinite_check.setEnabled(enabled)
        self.nb_triggers_spin.setEnabled(enabled and not self.infinite_check.isChecked())
        self.load_btn.setEnabled(enabled)

    def start_generation(self):
        """Start DAQ generation in a worker thread."""
        if self.worker_thread and self.worker_thread.isRunning():
            return

        # Gather parameters from UI
        device = build_channel_path(self.device_edit.text(), self.channel_edit.text())
        sampling_rate = self.sampling_rate_spin.value()
        trigger_duration = self.trigger_duration_spin.value()
        inter_trigger = self.inter_trigger_spin.value()
        initial_trigger_delay = self.initial_trigger_delay_spin.value()
        infinite = self.infinite_check.isChecked()
        nb_triggers = self.nb_triggers_spin.value()

        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.set_params_enabled(False)

        # Create worker and thread
        self.worker = DAQWorker(device, sampling_rate, trigger_duration, inter_trigger,
                                infinite, nb_triggers, initial_trigger_delay)
        self.worker_thread = QThread()
        self.worker.moveToThread(self.worker_thread)

        self.worker_thread.started.connect(self.worker.run)
        self.worker.started.connect(self.on_generation_started)
        self.worker.finished.connect(self.on_generation_finished)
        self.worker.error.connect(self.on_generation_error)

        # Store params for state indicator and JSON save
        self.worker_params = {
            "device": self.device_edit.text().strip(),
            "channel": self.channel_edit.text().strip(),
            "sampling_rate": sampling_rate,
            "initial_trigger_delay": initial_trigger_delay,
            "trigger": trigger_duration,
            "interval": inter_trigger,
            "infinite": infinite,
            "nb_triggers": nb_triggers,
        }
        self.experiment_start_time = datetime.now()
        self.worker_thread.start()

    def stop_generation(self):
        """Request worker to stop generation."""
        if self.worker:
            self.worker.stop()

    def on_generation_started(self):
        """Start timer to display real-time state (called when DAQ output begins)."""
        self.state_start_time = time.time()
        self.state_timer = QTimer(self)
        self.state_timer.timeout.connect(self.update_state_indicator)
        self.state_timer.start(100)

    def format_elapsed(self, seconds):
        """Format elapsed time as m:ss.cc."""
        m = int(seconds // 60)
        s = seconds % 60
        return f"{m}:{s:05.2f}"

    def format_countdown(self, seconds):
        """Format countdown in seconds."""
        if seconds <= 0:
            return "0.00 s"
        return f"{seconds:.2f} s remaining"

    def update_state_indicator(self):
        """Update indicator based on current signal phase (called every 100ms)."""
        if self.state_start_time is None or self.worker_params is None:
            return
        elapsed = time.time() - self.state_start_time
        self.time_total_label.setText(self.format_elapsed(elapsed))
        p = self.worker_params
        initial_delay, trigger, interval = p["initial_trigger_delay"], p["trigger"], p["interval"]
        cycle_duration = trigger + interval

        # Phase 1: Initial trigger delay (0V)
        if elapsed < initial_delay:
            text, color, bg = "(0V)", "#666", "#e0e0e0"
            remaining = initial_delay - elapsed
            countdown = self.format_countdown(remaining)
        else:
            # Phase 2: Trigger or interval
            cycle_time = elapsed - initial_delay
            if p["infinite"]:
                pos_in_cycle = cycle_time % cycle_duration
            else:
                total_cycles = p["nb_triggers"] * cycle_duration
                if cycle_time >= total_cycles:
                    # All triggers done
                    text, color, bg = "Done", "#666", "#e0e0e0"
                    self.state_label.setText(text)
                    self.state_label.setStyleSheet(f"color: {color};")
                    self.state_frame.setStyleSheet(f"QFrame {{ background-color: {bg}; border-radius: 8px; }}")
                    self.time_label.setText("—")
                    return
                pos_in_cycle = cycle_time % cycle_duration

            if pos_in_cycle < trigger:
                # In trigger phase
                text, color, bg = "Trigger (2V)", "#1b5e20", "#c8e6c9"
                remaining = trigger - pos_in_cycle
            else:
                # In interval phase
                text, color, bg = "0V (interval)", "#37474f", "#eceff1"
                remaining = cycle_duration - pos_in_cycle
            countdown = self.format_countdown(remaining)

        self.state_label.setText(text)
        self.state_label.setStyleSheet(f"color: {color};")
        self.state_frame.setStyleSheet(f"QFrame {{ background-color: {bg}; border-radius: 8px; }}")
        self.time_label.setText(countdown)

    def save_params_to_json(self, duration_seconds):
        """Save parameters and experiment info to a JSON file (on generation stop)."""
        if self.worker_params is None:
            return
        p = self.worker_params
        exp_time = getattr(self, "experiment_start_time", datetime.now())
        data = {
            "device": p.get("device", "Dev2"),
            "channel": p.get("channel", "ao0"),
            "sampling_rate": p.get("sampling_rate", 1000),
            "trigger_duration": p.get("trigger", 0.2),
            "inter_trigger_interval": p.get("interval", 20),
            "initial_trigger_delay": p.get("initial_trigger_delay", 5),
            "infinite": p.get("infinite", True),
            "nb_triggers": p.get("nb_triggers", 5),
            "duree_secondes": round(duration_seconds, 2),
            "heure_debut": exp_time.strftime("%Y-%m-%d %H:%M:%S"),
            "heure_fin": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }
        save_dir = _app_dir() / "experiences"
        save_dir.mkdir(exist_ok=True)
        filename = exp_time.strftime("trigger_generator_%Y-%m-%d_%H-%M-%S.json")
        filepath = save_dir / filename
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def load_params_from_json(self, silent=False):
        """Load parameters from a JSON file.
        If silent=True (e.g. at startup), loads the most recent file without dialog.
        If silent=False (button click), opens a file dialog to choose the file."""
        save_dir = _app_dir() / "experiences"
        if not save_dir.exists():
            if not silent:
                QMessageBox.warning(self, "Load", "No experiments folder found.")
            return
        json_files = list(save_dir.glob("trigger_generator_*.json")) + list(save_dir.glob("wavegene_*.json"))
        if not json_files:
            if not silent:
                QMessageBox.warning(self, "Load", "No experiment file found.")
            return

        if silent:
            path = max(json_files, key=lambda p: p.stat().st_mtime)
        else:
            path_str, _ = QFileDialog.getOpenFileName(
                self, "Load Parameters",
                str(save_dir),
                "JSON files (*.json);;All files (*)"
            )
            if not path_str:
                return
            path = Path(path_str)

        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.device_edit.setText(data.get("device", "Dev2"))
            self.channel_edit.setText(data.get("channel", "ao0"))
            self.sampling_rate_spin.setValue(data.get("sampling_rate", 1000))
            self.trigger_duration_spin.setValue(data.get("trigger_duration", data.get("pulse_duration", 0.2)))
            self.inter_trigger_spin.setValue(data.get("inter_trigger_interval", data.get("inter_pulse_interval", 20)))
            self.initial_trigger_delay_spin.setValue(data.get("initial_trigger_delay", 5))
            self.infinite_check.setChecked(data.get("infinite", True))
            self.nb_triggers_spin.setValue(data.get("nb_triggers", data.get("nb_pulses", 5)))
            if not silent:
                QMessageBox.information(self, "Load", f"Parameters loaded from {path.name}")
        except Exception as e:
            if not silent:
                QMessageBox.critical(self, "Error", f"Failed to load file:\n{e}")

    def on_generation_finished(self):
        """Clean up when generation stops (user stop or completion)."""
        if self.state_timer:
            self.state_timer.stop()
            self.state_timer = None
        duration = 0
        if self.state_start_time is not None:
            duration = time.time() - self.state_start_time
            self.save_params_to_json(duration)
        self.state_start_time = None
        self.state_label.setText("—")
        self.time_label.setText("—")
        self.time_total_label.setText("0:00")
        self.state_label.setStyleSheet("color: #666;")
        self.time_label.setStyleSheet("color: #666;")
        self.state_frame.setStyleSheet("QFrame { background-color: #e0e0e0; border-radius: 8px; }")
        if self.worker_thread:
            self.worker_thread.quit()
            self.worker_thread.wait(2000)
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.set_params_enabled(True)

    def on_generation_error(self, msg):
        """Handle DAQ or worker error: cleanup and show message."""
        self.on_generation_finished()
        QMessageBox.critical(self, "Error", msg)


def main():
    """Application entry point."""
    app = QApplication([])
    app.setStyle("Fusion")
    window = TriggerGeneratorWindow()
    window.show()
    return app.exec_()


if __name__ == "__main__":
    import sys
    sys.exit(main())
