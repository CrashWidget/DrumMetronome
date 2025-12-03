from PyQt5.QtCore import Qt, QSize, QThread, pyqtSignal, pyqtSlot, QTimer
from PyQt5.QtWidgets import (
    QWidget,
    QMainWindow,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSpinBox,
    QSlider,
    QCheckBox,
    QGroupBox,
    QApplication,
    QComboBox,
    QGridLayout,
)
from PyQt5.QtGui import QPainter, QColor, QFont

from .engine import MetronomeEngine, TempoLadderRoutine
from .audio import ClickAudio
from .utils import TapTempo
from .rudiments import RudimentPracticeRoutine, Rudiment


STYLESHEET = """
QMainWindow, QWidget {
    background-color: #2b2b2b;
    color: #f0f0f0;
    font-family: "Segoe UI", "Arial", sans-serif;
    font-size: 10pt;
}

QGroupBox {
    border: 1px solid #4d4d4d;
    border-radius: 8px;
    margin-top: 12px;
    padding-top: 15px;
    font-weight: bold;
    background-color: #323232;
}
QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    padding: 0 5px;
    left: 10px;
    color: #aaa;
}

QPushButton {
    background-color: #0d6efd;
    border: none;
    border-radius: 6px;
    padding: 8px 16px;
    color: white;
    font-weight: bold;
}
QPushButton:hover {
    background-color: #0b5ed7;
}
QPushButton:pressed {
    background-color: #0a58ca;
}
QPushButton:disabled {
    background-color: #555;
    color: #888;
}

/* Secondary buttons can be styled differently if needed, but uniform is fine for now */

QSpinBox, QComboBox {
    background-color: #3b3b3b;
    border: 1px solid #555;
    border-radius: 4px;
    padding: 4px;
    color: #fff;
}
QSpinBox::up-button, QSpinBox::down-button {
    background-color: #444;
    border: none;
    border-radius: 2px;
    margin: 1px;
}

QSlider::groove:horizontal {
    border: 1px solid #333;
    height: 6px;
    background: #1e1e1e;
    margin: 2px 0;
    border-radius: 3px;
}
QSlider::handle:horizontal {
    background: #0d6efd;
    border: 1px solid #0d6efd;
    width: 16px;
    height: 16px;
    margin: -6px 0;
    border-radius: 8px;
}
QSlider::handle:horizontal:hover {
    background: #3689ff;
}

QLabel {
    color: #e0e0e0;
}
"""


class RudimentWidget(QGroupBox):
    selectionChanged = pyqtSignal(list)

    def __init__(self, parent=None):
        super().__init__("Rudiment Trainer", parent)
        self.layout = QVBoxLayout(self)
        
        self.lbl_current_name = QLabel("Ready")
        self.lbl_current_sticking = QLabel("")
        
        self.lbl_next_name = QLabel("Next: ...")
        self.lbl_next_sticking = QLabel("")
        
        # Styling
        self.lbl_current_sticking.setStyleSheet("font-size: 30pt; font-weight: bold;")
        self.lbl_current_sticking.setAlignment(Qt.AlignCenter)
        
        self.lbl_current_name.setStyleSheet("font-size: 20pt; font-weight: bold;")
        self.lbl_current_name.setAlignment(Qt.AlignCenter)

        # Combined style for next items (font + color)
        style_next = "font-size: 16pt; color: #999;"
        self.lbl_next_name.setStyleSheet(style_next)
        self.lbl_next_sticking.setStyleSheet(style_next)

        self.lbl_next_sticking.setAlignment(Qt.AlignCenter)
        self.lbl_next_name.setAlignment(Qt.AlignCenter)

        self.layout.addWidget(self.lbl_current_name)
        self.layout.addWidget(self.lbl_current_sticking)
        self.layout.addSpacing(15)
        self.layout.addWidget(self.lbl_next_name)
        self.layout.addWidget(self.lbl_next_sticking)
        
        # Selection Toggles
        self.toggles_group = QGroupBox("Included Rudiments")
        self.toggles_group.setCheckable(False)
        self.toggles_layout = QGridLayout(self.toggles_group)
        self.layout.addWidget(self.toggles_group)
        
        self.checkboxes = {}

    def set_available_rudiments(self, names):
        # Clear existing
        for i in reversed(range(self.toggles_layout.count())): 
            w = self.toggles_layout.itemAt(i).widget()
            if w: w.setParent(None)
        self.checkboxes.clear()

        # Populate
        row, col = 0, 0
        max_cols = 2
        for name in names:
            cb = QCheckBox(name)
            cb.setChecked(True)
            cb.toggled.connect(self._on_selection_changed)
            self.toggles_layout.addWidget(cb, row, col)
            self.checkboxes[name] = cb
            
            col += 1
            if col >= max_cols:
                col = 0
                row += 1

    def _on_selection_changed(self):
        selected = [name for name, cb in self.checkboxes.items() if cb.isChecked()]
        self.selectionChanged.emit(selected)

    def update_display(self, current: Rudiment, next_r: Rudiment):
        if current:
            self.lbl_current_name.setText(current.name)
            self.lbl_current_sticking.setText(current.sticking)
        else:
            self.lbl_current_name.setText("Ready")
            self.lbl_current_sticking.setText("")
            
        if next_r:
            self.lbl_next_name.setText(f"Next: {next_r.name}")
            self.lbl_next_sticking.setText(next_r.sticking)
        else:
            self.lbl_next_name.setText("Next: ...")
            self.lbl_next_sticking.setText("")


class BeatIndicator(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.beats_per_bar = 4
        self.current_beat = 0
        self.flash = False
        self.setMinimumHeight(80)

    def sizeHint(self):
        return QSize(300, 100)

    def set_beats(self, beats: int):
        self.beats_per_bar = max(1, beats)
        self.update()

    def set_current(self, beat_idx: int, flash: bool):
        self.current_beat = beat_idx
        self.flash = flash
        self.update()

    def paintEvent(self, e):
        p = QPainter(self)
        w = self.width()
        h = self.height()
        margin = 10
        radius = min((w - 2 * margin) // (self.beats_per_bar * 2), (h - 2 * margin) // 2)
        cx_start = margin + radius
        cy = h // 2
        for i in range(self.beats_per_bar):
            cx = cx_start + i * 2 * radius
            if i == self.current_beat:
                color = QColor(255, 90, 90) if self.flash else QColor(240, 160, 160)
            else:
                color = QColor(120, 120, 120)
            p.setBrush(color)
            p.setPen(Qt.NoPen)
            p.drawEllipse(cx - radius, cy - radius, 2 * radius, 2 * radius)


class MainWindow(QMainWindow):
    # Signals for worker thread control
    sig_start = pyqtSignal()
    sig_stop = pyqtSignal()
    sig_change_device = pyqtSignal(str)
    sig_audio_play = pyqtSignal(bool)
    sig_ladder_start = pyqtSignal()
    sig_ladder_stop = pyqtSignal()
    sig_ladder_configure = pyqtSignal(int, int, int, int)
    sig_rudiment_start = pyqtSignal()
    sig_rudiment_stop = pyqtSignal()
    sig_rudiment_configure = pyqtSignal(int)
    sig_rudiment_enable_list = pyqtSignal(list)
    sig_init_audio = pyqtSignal()
    sig_init_engine = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Drum Metronome")
        self.setStyleSheet(STYLESHEET)

        # Threading
        self.worker_thread = QThread()
        self.worker_thread.start()

        # Core (moved to thread)
        self.engine = MetronomeEngine()
        self.audio = ClickAudio()
        # Make ladder a child of engine to ensure they share thread affinity
        self.ladder = TempoLadderRoutine(self.engine, parent=self.engine)
        self.rudiment_routine = RudimentPracticeRoutine(self.engine, parent=self.engine)
        
        self.engine.moveToThread(self.worker_thread)
        self.audio.moveToThread(self.worker_thread)
        # routines move with engine because they are children

        # Internal worker wiring
        self.engine.click.connect(self.audio.play)

        # Helpers
        self.tap = TapTempo()

        # Local state tracking for UI
        self._running_state = False

        # UI
        root = QWidget()
        layout = QVBoxLayout(root)

        # BPM controls
        bpm_row = QHBoxLayout()
        bpm_label = QLabel("BPM:")
        self.bpm_spin = QSpinBox()
        self.bpm_spin.setRange(20, 400)
        self.bpm_spin.setValue(self.engine.bpm)
        self.bpm_slider = QSlider(Qt.Horizontal)
        self.bpm_slider.setRange(20, 400)
        self.bpm_slider.setValue(self.engine.bpm)
        self.btn_start = QPushButton("Start")
        self.btn_tap = QPushButton("Tap")
        bpm_row.addWidget(bpm_label)
        bpm_row.addWidget(self.bpm_spin)
        bpm_row.addWidget(self.bpm_slider, 1)
        bpm_row.addWidget(self.btn_tap)
        bpm_row.addWidget(self.btn_start)
        layout.addLayout(bpm_row)

        # Meter and subdivision
        meter_row = QHBoxLayout()
        self.beats_spin = QSpinBox()
        self.beats_spin.setRange(1, 12)
        self.beats_spin.setValue(self.engine.beats_per_bar)
        self.subdiv_spin = QSpinBox()
        self.subdiv_spin.setRange(1, 12)
        self.subdiv_spin.setValue(self.engine.subdivision)
        self.chk_accent = QCheckBox("Accent on 1")
        self.chk_accent.setChecked(True)
        meter_row.addWidget(QLabel("Beats/Bar:"))
        meter_row.addWidget(self.beats_spin)
        meter_row.addSpacing(12)
        meter_row.addWidget(QLabel("Subdivision:"))
        meter_row.addWidget(self.subdiv_spin)
        meter_row.addSpacing(12)
        meter_row.addWidget(self.chk_accent)
        layout.addLayout(meter_row)

        # Audio output device selector
        audio_row = QHBoxLayout()
        audio_row.addWidget(QLabel("Audio Output:"))
        self.device_combo = QComboBox()
        audio_row.addWidget(self.device_combo, 1)
        self.btn_test = QPushButton("Test Click")
        audio_row.addWidget(self.btn_test)
        layout.addLayout(audio_row)

        # Session/Workout Clock
        clock_row = QHBoxLayout()
        clock_row.addWidget(QLabel("Session Time:"))
        self.lbl_workout_time = QLabel("00:00")
        f_clock = self.lbl_workout_time.font()
        f_clock.setBold(True)
        self.lbl_workout_time.setFont(f_clock)
        clock_row.addWidget(self.lbl_workout_time)
        self.btn_reset_workout = QPushButton("Reset")
        clock_row.addWidget(self.btn_reset_workout)
        clock_row.addStretch(1)
        layout.addLayout(clock_row)

        # Beat indicator
        self.indicator = BeatIndicator()
        layout.addWidget(self.indicator)

        # Routine group
        routine_box = QGroupBox("Tempo Ladder")
        r_layout = QHBoxLayout(routine_box)
        self.r_start = QSpinBox(); self.r_start.setRange(20, 400); self.r_start.setValue(80)
        self.r_end = QSpinBox(); self.r_end.setRange(20, 400); self.r_end.setValue(120)
        self.r_step = QSpinBox(); self.r_step.setRange(1, 50); self.r_step.setValue(5)
        self.r_bars = QSpinBox(); self.r_bars.setRange(1, 32); self.r_bars.setValue(4)
        self.btn_routine = QPushButton("Start Ladder")
        for lbl, w in (("Start", self.r_start), ("End", self.r_end), ("Step", self.r_step), ("Bars/Step", self.r_bars)):
            r_layout.addWidget(QLabel(lbl+":"))
            r_layout.addWidget(w)
        r_layout.addStretch(1)
        r_layout.addWidget(self.btn_routine)
        layout.addWidget(routine_box)

        # Rudiment Trainer
        self.rudiment_widget = RudimentWidget()
        
        rud_layout = QHBoxLayout()
        self.rud_bars = QSpinBox()
        self.rud_bars.setRange(1, 32)
        self.rud_bars.setValue(1)
        self.rud_bars.setPrefix("Switch every ")
        self.rud_bars.setSuffix(" bars")
        self.rud_bars.setMinimumWidth(150)
        
        self.btn_rudiment = QPushButton("Start Rudiments")
        
        rud_layout.addWidget(self.rud_bars)
        rud_layout.addStretch(1)
        rud_layout.addWidget(self.btn_rudiment)
        
        layout.addWidget(self.rudiment_widget)
        layout.addLayout(rud_layout)

        # Footer info
        self.info = QLabel("Ready")
        f = self.info.font()
        f.setPointSize(9)
        self.info.setFont(f)
        layout.addWidget(self.info)

        self.setCentralWidget(root)

        # Connections
        # -- Control (UI -> Worker via Auto-Queued Slots or Signals) --
        self.bpm_spin.valueChanged.connect(self.engine.set_bpm)
        self.bpm_spin.valueChanged.connect(self.bpm_slider.setValue)
        self.bpm_slider.valueChanged.connect(self.bpm_spin.setValue)
        
        self.beats_spin.valueChanged.connect(self.engine.set_beats_per_bar)
        self.beats_spin.valueChanged.connect(lambda v: self.indicator.set_beats(v))
        
        self.subdiv_spin.valueChanged.connect(self.engine.set_subdivision)
        self.chk_accent.toggled.connect(self.engine.set_accent_on_one)
        
        self.sig_start.connect(self.engine.start)
        self.sig_stop.connect(self.engine.stop)
        self.sig_change_device.connect(self.audio.set_output_device_by_name)
        self.sig_audio_play.connect(self.audio.play)
        
        self.sig_ladder_start.connect(self.ladder.start)
        self.sig_ladder_stop.connect(self.ladder.stop)
        self.sig_ladder_configure.connect(self.ladder.configure)
        
        self.sig_rudiment_start.connect(self.rudiment_routine.start)
        self.sig_rudiment_stop.connect(self.rudiment_routine.stop)
        self.sig_rudiment_configure.connect(self.rudiment_routine.set_bars_per_rudiment)
        self.sig_rudiment_enable_list.connect(self.rudiment_routine.set_enabled_rudiments)

        self.sig_init_audio.connect(self.audio.initialize)
        self.sig_init_engine.connect(self.engine.initialize)

        # -- Feedback (Worker -> UI) --
        self.engine.tick.connect(self._on_tick)
        self.engine.bpmChanged.connect(self._on_bpm_changed)
        self.engine.runningChanged.connect(self._on_running_changed)
        self.audio.deviceChanged.connect(self._on_device_changed_info)
        
        self.ladder.stateChanged.connect(self._routine_state)
        self.ladder.routineFinished.connect(self._routine_finished)
        
        self.rudiment_routine.activeChanged.connect(self._rudiment_active_changed)
        self.rudiment_routine.rudimentChanged.connect(self._rudiment_update)

        # -- Local UI Logic --
        self.btn_start.clicked.connect(self._toggle_start)
        self.btn_tap.clicked.connect(self._tap_tempo)
        self.btn_routine.clicked.connect(self._toggle_routine)
        self.btn_rudiment.clicked.connect(self._toggle_rudiment)
        self.rud_bars.valueChanged.connect(self.sig_rudiment_configure.emit)
        self.rudiment_widget.selectionChanged.connect(self.sig_rudiment_enable_list.emit)
        self.btn_reset_workout.clicked.connect(self._reset_workout_time)
        self.device_combo.currentTextChanged.connect(self._device_changed)
        self.btn_test.clicked.connect(lambda: self.sig_audio_play.emit(False))

        self.indicator.set_beats(self.beats_spin.value())
        
        # Workout timer
        self.workout_timer = QTimer()
        self.workout_timer.setInterval(1000)
        self.workout_timer.timeout.connect(self._update_workout_time)
        self.workout_seconds = 0
        
        # Populate rudiments
        self.rudiment_widget.set_available_rudiments(self.rudiment_routine.get_rudiment_names())

        # Populate audio devices
        self._populate_devices()
        self._update_info_device_label()

        # Start audio engine in worker thread
        self.sig_init_audio.emit()
        self.sig_init_engine.emit()

    # Slots / handlers
    def _on_tick(self, step_idx: int, beat_idx: int, is_beat: bool, is_accent: bool):
        # Audio is handled by worker thread now.
        # Update visual on beats
        if is_beat:
            self.indicator.set_current(beat_idx, True)
        else:
            # turn off flash between steps
            self.indicator.set_current(self.indicator.current_beat, False)

    def _update_workout_time(self):
        self.workout_seconds += 1
        m = self.workout_seconds // 60
        s = self.workout_seconds % 60
        self.lbl_workout_time.setText(f"{m:02d}:{s:02d}")

    def _reset_workout_time(self):
        self.workout_seconds = 0
        self.lbl_workout_time.setText("00:00")

    def _on_running_changed(self, running: bool):
        self._running_state = running
        if running:
            self.btn_start.setText("Stop")
            self.info.setText("Running")
            self.workout_timer.start()
        else:
            self.btn_start.setText("Start")
            self.info.setText("Stopped")
            self.workout_timer.stop()

    def _toggle_start(self):
        if self._running_state:
            self.sig_stop.emit()
        else:
            self.sig_start.emit()

    def _tap_tempo(self):
        bpm = self.tap.tap()
        if bpm is not None:
            self.bpm_spin.setValue(bpm)
            self.info.setText(f"Tapped {bpm} BPM")

    # Removed _change_beats / _change_subdiv as they are direct connects now

    def _on_bpm_changed(self, bpm: int):
        self.info.setText(f"BPM: {bpm}")

    def _toggle_routine(self):
        if self.ladder.is_running(): # This calls a method on object in another thread. Is it safe?
             # is_running() just reads self._running. It might race but boolean read is atomic.
             # Better to track state locally or use exception.
             # Let's assume ladder state is tracked by _routine_state
             # But _routine_state updates button text.
             pass
        
        # Actually, we should check button text or store state.
        # Let's use the text or a flag.
        if "Stop" in self.btn_routine.text():
             self.sig_ladder_stop.emit()
             return
        
        # configure and start
        self.sig_ladder_configure.emit(
            self.r_start.value(), self.r_end.value(), self.r_step.value(), self.r_bars.value()
        )
        if not self._running_state:
            self.sig_start.emit()
        self.sig_ladder_start.emit()

    def _routine_state(self, running: bool):
        self.btn_routine.setText("Stop Ladder" if running else "Start Ladder")
        if not running:
            self.info.setText("Ladder stopped")
        else:
            self.info.setText("Ladder running")

    def _routine_finished(self):
        self.info.setText("Ladder finished")

    # Audio device helpers
    def _populate_devices(self):
        self.device_combo.blockSignals(True)
        self.device_combo.clear()
        try:
            # Calling method on audio object in worker thread?
            # list_output_devices is a static-like utility, accessing static QAudioDeviceInfo.
            # It does NOT touch QAudioOutput instance. Safe.
            devices = self.audio.list_output_devices()
            names = [d.deviceName() for d in devices]
        except Exception:
            names = []
        if not names:
            self.device_combo.addItem("(no devices)")
            self.device_combo.setEnabled(False)
        else:
            for n in names:
                self.device_combo.addItem(n)
            # We can't easily ask audio for 'current_device_name' synchronously if we want to be 100% pure.
            # But reading _device_info (internal) is low risk.
            cur = self.audio.current_device_name()
            idx = self.device_combo.findText(cur)
            if idx >= 0:
                self.device_combo.setCurrentIndex(idx)
        self.device_combo.blockSignals(False)

    def _device_changed(self, name: str):
        if not name or name == "(no devices)":
            return
        self.sig_change_device.emit(name)
        # We can't verify success synchronously. Rely on signal back.

    def _on_device_changed_info(self, name: str, fmt: str):
        self.info.setText(f"Device: {name}  •  {fmt}")
        # Trigger test click
        self.sig_audio_play.emit(False)

    def _update_info_device_label(self):
        # Initial label update
        self._on_device_changed_info(self.audio.current_device_name(), self.audio.negotiated_format_summary())

    def _toggle_rudiment(self):
        if "Stop" in self.btn_rudiment.text():
            self.sig_rudiment_stop.emit()
        else:
            self.sig_rudiment_configure.emit(self.rud_bars.value())
            if not self._running_state:
                self.sig_start.emit()
            self.sig_rudiment_start.emit()

    def _rudiment_active_changed(self, active: bool):
        self.btn_rudiment.setText("Stop Rudiments" if active else "Start Rudiments")
        if not active:
             self.rudiment_widget.update_display(None, None)

    def _rudiment_update(self, current, next_r):
        self.rudiment_widget.update_display(current, next_r)


if __name__ == "__main__":
    # for quick local run
    import sys
    app = QApplication(sys.argv)
    w = MainWindow()
    w.show()
    sys.exit(app.exec_())
