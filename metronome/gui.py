import json
import random
from pathlib import Path

from PyQt5.QtCore import (
    Qt,
    QSize,
    QThread,
    pyqtSignal,
    pyqtSlot,
    QTimer,
    QSettings,
    QPropertyAnimation,
    QEasingCurve,
    pyqtProperty,
    QRectF,
    QPointF,
    QElapsedTimer,
)
from PyQt5.QtWidgets import (
    QWidget,
    QMainWindow,
    QDialog,
    QDialogButtonBox,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSpinBox,
    QDoubleSpinBox,
    QSlider,
    QCheckBox,
    QGroupBox,
    QApplication,
    QComboBox,
    QGridLayout,
    QFrame,
    QAction,
    QWidgetAction,
    QProgressBar,
    QTableWidget,
    QHeaderView,
    QAbstractItemView,
    QFileDialog,
    QMessageBox,
    QInputDialog,
)
from PyQt5.QtGui import QPainter, QColor, QFont, QPen, QLinearGradient, QRadialGradient

from .engine import MetronomeEngine, TempoLadderRoutine
from .audio import ClickAudio, GrooveMidiAudio
from .midi_out import MidiOutput, DEFAULT_DRUM_MAPPING
from .utils import TapTempo
from .rudiments import RudimentPracticeRoutine, Rudiment
from .groove import GrooveLibrary, GrooveRoutine, DrumGroove
from .drum_staff import DrumStaffWidget
from .groove_editor import GrooveEditorDialog
from .remote_control import ControlServer, ControlState, DISCOVERY_PORT, HTTP_PORT
from .voice import BpmVoiceAnnouncer


STYLESHEET = """
QMainWindow {
    background-color: #151515;
    color: #e6e6e6;
    font-family: "IBM Plex Sans", "Segoe UI", "Helvetica Neue", sans-serif;
    font-size: 12pt;
}

QWidget {
    background-color: #151515;
    color: #e6e6e6;
}

QMenuBar {
    background-color: #1c1c1c;
    color: #e6e6e6;
    padding: 4px 8px;
}
QMenuBar::item {
    background: transparent;
    padding: 4px 10px;
    border-radius: 6px;
}
QMenuBar::item:selected {
    background: #2a2a2a;
}
QMenu {
    background-color: #1f1f1f;
    color: #e6e6e6;
    border: 1px solid #2c2c2c;
    padding: 6px;
}
QMenu::item {
    padding: 6px 20px 6px 16px;
    border-radius: 6px;
}
QMenu::item:selected {
    background-color: #2b2b2b;
}
QMenu::separator {
    height: 1px;
    background: #2c2c2c;
    margin: 6px 0;
}

QGroupBox {
    border: 1px solid #2b2b2b;
    border-radius: 12px;
    margin-top: 16px;
    padding: 16px 10px 10px 10px;
    font-weight: 600;
    background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                                      stop:0 #1f1f1f, stop:1 #171717);
}
QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    padding: 0 8px;
    left: 10px;
    color: #6ad1c0;
}

QPushButton {
    background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                                      stop:0 #63c9b8, stop:1 #3aa391);
    border: 1px solid #2f8f7f;
    border-radius: 8px;
    padding: 6px 14px;
    color: #0b0b0b;
    font-weight: 600;
}
QPushButton:hover {
    background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                                      stop:0 #73d6c7, stop:1 #46b09e);
}
QPushButton:pressed {
    background-color: #2f8f7f;
}
QPushButton:disabled {
    background-color: #333;
    color: #666;
}

QSpinBox, QComboBox, QLineEdit {
    background-color: #202020;
    border: 1px solid #333;
    border-radius: 6px;
    padding: 4px 8px;
    color: #fff;
    min-height: 30px;
    selection-background-color: #4fb3a1;
    selection-color: #0f0f0f;
}
QSpinBox:focus, QComboBox:focus, QLineEdit:focus {
    border: 1px solid #4fb3a1;
}

QComboBox QAbstractItemView {
    background-color: #202020;
    color: #fff;
    selection-background-color: #4fb3a1;
    selection-color: #0f0f0f;
    outline: 0;
    border: 1px solid #333;
}
QComboBox QAbstractItemView::item {
    min-height: 28px;
}

QScrollArea {
    border: none;
    background-color: transparent;
}

QTableWidget {
    background-color: #1b1b1b;
    border: 1px solid #2b2b2b;
    border-radius: 8px;
    gridline-color: #2c2c2c;
}
QHeaderView::section {
    background-color: #202020;
    color: #e6e6e6;
    padding: 6px 8px;
    border: 1px solid #2b2b2b;
}
QTableWidget::item:selected {
    background-color: #2a2a2a;
}

QSpinBox::up-button, QSpinBox::down-button {
    background-color: #2a2a2a;
    border-left: 1px solid #333;
    width: 20px;
}
QSpinBox::up-button:hover, QSpinBox::down-button:hover {
    background-color: #343434;
}

QSlider::groove:horizontal {
    border: none;
    height: 8px;
    background: #2a2a2a;
    margin: 2px 0;
    border-radius: 4px;
}
QSlider::sub-page:horizontal {
    background: #4fb3a1;
    border-radius: 4px;
}
QSlider::handle:horizontal {
    background: #4fb3a1;
    border: 2px solid #151515;
    width: 18px;
    height: 18px;
    margin: -6px 0;
    border-radius: 9px;
}
QSlider::handle:horizontal:hover {
    background: #63c4b3;
    width: 20px;
    height: 20px;
    margin: -7px 0;
    border-radius: 10px;
}

QProgressBar {
    background-color: #1f1f1f;
    border: 1px solid #333;
    border-radius: 6px;
    text-align: center;
    color: #e6e6e6;
}
QProgressBar::chunk {
    background-color: #4fb3a1;
    border-radius: 6px;
}

QCheckBox {
    spacing: 8px;
}
QCheckBox::indicator {
    width: 18px;
    height: 18px;
    border-radius: 4px;
    border: 1px solid #3a3a3a;
    background-color: #1a1a1a;
}
QCheckBox::indicator:checked {
    background-color: #4fb3a1;
    border: 1px solid #4fb3a1;
}

QLabel {
    color: #e6e6e6;
}

#controlPanel {
    background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                                      stop:0 #1e1e1e, stop:1 #151515);
    border: 1px solid #2b2b2b;
    border-radius: 14px;
}

#workoutTime {
    font-size: 30pt;
    font-weight: 700;
}
#ladderCurrent {
    font-size: 11pt;
    font-weight: 600;
    color: #6ad1c0;
}
#ladderNext {
    font-size: 11pt;
    color: #9a9a9a;
}
#practiceTotal {
    font-size: 11pt;
    color: #b0b0b0;
}
#currentSticking {
    font-size: 20pt;
    font-weight: 600;
}
#currentName {
    font-size: 16pt;
    font-weight: 600;
}
#nextName, #nextSticking {
    font-size: 12pt;
    color: #9a9a9a;
}
#resetButton {
    padding: 2px 10px;
}
#grooveName {
    font-size: 12pt;
    font-weight: 600;
}

QStatusBar {
    background: #151515;
    border-top: 1px solid #2c2c2c;
    color: #9a9a9a;
    padding: 4px 8px;
    font-size: 10pt;
}
"""


class RudimentWidget(QGroupBox):
    selectionChanged = pyqtSignal(list)
    leadHandChanged = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__("Rudiment Trainer", parent)
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(12, 16, 12, 12)
        self.layout.setSpacing(6)
        
        self.lbl_current_name = QLabel("Ready")
        self.lbl_current_name.setObjectName("currentName")
        self.lbl_current_sticking = QLabel("")
        self.lbl_current_sticking.setObjectName("currentSticking")
        
        self.lbl_next_name = QLabel("Next: ...")
        self.lbl_next_name.setObjectName("nextName")
        self.lbl_next_sticking = QLabel("")
        self.lbl_next_sticking.setObjectName("nextSticking")
        
        # Alignment
        self.lbl_current_sticking.setAlignment(Qt.AlignCenter)
        self.lbl_current_name.setAlignment(Qt.AlignCenter)
        self.lbl_next_sticking.setAlignment(Qt.AlignCenter)
        self.lbl_next_name.setAlignment(Qt.AlignCenter)

        self.layout.addWidget(self.lbl_current_name)
        self.layout.addWidget(self.lbl_current_sticking)
        self.layout.addSpacing(10)
        self.layout.addWidget(self.lbl_next_name)
        self.layout.addWidget(self.lbl_next_sticking)
        
        self.layout.addSpacing(8)

        # Lead Hand
        hb_hand = QHBoxLayout()
        hb_hand.addWidget(QLabel("Lead Hand:"))
        self.combo_hand = QComboBox()
        self.combo_hand.addItems(["Right (R)", "Left (L)", "Mixed"])
        self.combo_hand.currentTextChanged.connect(self._on_lead_hand_changed)
        hb_hand.addWidget(self.combo_hand)
        self.layout.addLayout(hb_hand)
        
        # Selection Toggles
        self.toggles_group = QGroupBox("Included Rudiments")
        self.toggles_group.setCheckable(False)
        self.toggles_layout = QGridLayout(self.toggles_group)
        self.toggles_layout.setSpacing(6)
        self.layout.addWidget(self.toggles_group)
        
        self.checkboxes = {}

    def _on_lead_hand_changed(self, text):
        val = "R"
        if "Left" in text:
            val = "L"
        elif "Mixed" in text:
            val = "Mixed"
        self.leadHandChanged.emit(val)

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
        self._pulse = 0.0
        self._accent_enabled = True
        self._accent_flash = False
        self._pulse_anim = QPropertyAnimation(self, b"pulse")
        self._pulse_anim.setDuration(240)
        self._pulse_anim.setStartValue(1.0)
        self._pulse_anim.setEndValue(0.0)
        self._pulse_anim.setEasingCurve(QEasingCurve.OutCubic)
        self.setMinimumHeight(120)

    def sizeHint(self):
        return QSize(300, 100)

    def set_beats(self, beats: int):
        self.beats_per_bar = max(1, beats)
        self.current_beat = min(self.current_beat, self.beats_per_bar - 1)
        self.update()

    def set_accent_enabled(self, enabled: bool):
        self._accent_enabled = bool(enabled)
        self.update()

    def _get_pulse(self):
        return self._pulse

    def _set_pulse(self, value):
        self._pulse = max(0.0, float(value))
        self.update()

    pulse = pyqtProperty(float, fget=_get_pulse, fset=_set_pulse)

    @staticmethod
    def _blend_color(color_a: QColor, color_b: QColor, t: float) -> QColor:
        t = max(0.0, min(1.0, t))
        inv = 1.0 - t
        return QColor(
            int(color_a.red() * inv + color_b.red() * t),
            int(color_a.green() * inv + color_b.green() * t),
            int(color_a.blue() * inv + color_b.blue() * t),
        )

    def set_current(self, beat_idx: int, flash: bool, accent: bool = False):
        self.current_beat = max(0, min(beat_idx, self.beats_per_bar - 1))
        self.flash = flash
        if flash:
            self._accent_flash = accent
            self._pulse_anim.stop()
            self._set_pulse(1.0)
            self._pulse_anim.start()
        self.update()

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w = self.width()
        h = self.height()
        if self.beats_per_bar <= 0 or w <= 0 or h <= 0:
            return
        margin = max(20, min(48, int(w * 0.06)))

        available_width = max(0.0, w - 2 * margin)
        if available_width <= 0:
            return
        slot_width = available_width / max(1, self.beats_per_bar)

        radius = min(slot_width * 0.38, h * 0.30)
        radius = max(radius, 10.0)
        radius = min(radius, slot_width * 0.45)

        cy = h * 0.5

        track_height = max(4.0, radius * 0.18)
        track_rect = QRectF(margin, cy - track_height * 0.5, available_width, track_height)
        track_grad = QLinearGradient(track_rect.topLeft(), track_rect.bottomLeft())
        track_grad.setColorAt(0.0, QColor("#1f1f1f"))
        track_grad.setColorAt(1.0, QColor("#121212"))
        p.setBrush(track_grad)
        p.setPen(QPen(QColor("#2a2a2a"), 1))
        p.drawRoundedRect(track_rect, track_height * 0.5, track_height * 0.5)

        base_center = QColor("#363636")
        base_edge = QColor("#1f1f1f")
        idle_center = QColor("#ffb3b3")
        idle_edge = QColor("#d16a6a")
        pulse_center = QColor("#ff5d5d")
        pulse_edge = QColor("#bf1f2c")
        ring_base = QColor("#262626")
        ring_active = QColor("#3f3f3f")
        glow_base = QColor("#ff5d5d")
        accent_ring = QColor("#4fb3a1")

        for i in range(self.beats_per_bar):
            cx = margin + (i + 0.5) * slot_width
            is_current = i == self.current_beat
            pulse = self._pulse if is_current else 0.0

            if is_current:
                center = self._blend_color(idle_center, pulse_center, pulse)
                edge = self._blend_color(idle_edge, pulse_edge, pulse)
                ring = self._blend_color(ring_active, pulse_center, min(1.0, pulse * 0.6))
            else:
                center = base_center
                edge = base_edge
                ring = ring_base

            if pulse > 0.0:
                glow_boost = 1.2 if self._accent_flash and is_current else 1.0
                glow_radius = radius * (1.25 + 0.6 * pulse) * glow_boost
                glow_color = QColor(glow_base)
                glow_alpha = int(180 * pulse)
                if self._accent_flash and is_current:
                    glow_alpha = min(255, int(210 * pulse))
                glow_color.setAlpha(glow_alpha)
                glow_edge = QColor(glow_color)
                glow_edge.setAlpha(0)
                glow_grad = QRadialGradient(QPointF(cx, cy), glow_radius)
                glow_grad.setColorAt(0.0, glow_color)
                glow_grad.setColorAt(1.0, glow_edge)
                p.setBrush(glow_grad)
                p.setPen(Qt.NoPen)
                p.drawEllipse(QPointF(cx, cy), glow_radius, glow_radius)

            fill_grad = QRadialGradient(QPointF(cx - radius * 0.3, cy - radius * 0.3), radius * 1.3)
            fill_grad.setColorAt(0.0, center)
            fill_grad.setColorAt(1.0, edge)
            p.setBrush(fill_grad)
            p.setPen(QPen(ring, 1))
            p.drawEllipse(QPointF(cx, cy), radius, radius)

            if self._accent_enabled and i == 0:
                accent = QColor(accent_ring)
                accent.setAlpha(120 if not is_current else 80)
                accent_radius = min(radius + 4.0, slot_width * 0.48)
                p.setBrush(Qt.NoBrush)
                p.setPen(QPen(accent, 2))
                p.drawEllipse(QPointF(cx, cy), accent_radius, accent_radius)


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
    sig_rudiment_lead_hand = pyqtSignal(str)
    sig_groove_start = pyqtSignal()
    sig_groove_stop = pyqtSignal()
    sig_groove_set = pyqtSignal(str)
    sig_groove_loop = pyqtSignal(int)
    sig_groove_midi = pyqtSignal(list)
    sig_init_audio = pyqtSignal()
    sig_init_engine = pyqtSignal()
    sig_update_sounds = pyqtSignal(str, str)
    sig_click_volume = pyqtSignal(float)
    sig_midi_init = pyqtSignal()
    sig_midi_set_port = pyqtSignal(str)
    sig_midi_set_voice = pyqtSignal(str, int, int)
    sig_remote_start = pyqtSignal()
    sig_remote_stop = pyqtSignal()
    sig_remote_set_bpm = pyqtSignal(int)

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Drum Metronome")
        self.setMinimumSize(900, 720)
        self.resize(1200, 1080)
        self.setStyleSheet(STYLESHEET)
        self._settings_path = Path(__file__).resolve().parent.parent / "drum_metronome.ini"
        self._settings = QSettings(str(self._settings_path), QSettings.IniFormat)
        self._preferred_audio_device = ""
        self._restore_flags = {}

        # Threading
        self.worker_thread = QThread()
        self.worker_thread.start()
        self.groove_audio_thread = QThread()
        self.groove_audio_thread.start()

        # Core (moved to thread)
        self.engine = MetronomeEngine()
        self.audio = ClickAudio()
        self.groove_audio = GrooveMidiAudio()
        self.midi_out = MidiOutput()
        # Make ladder a child of engine to ensure they share thread affinity
        self.ladder = TempoLadderRoutine(self.engine, parent=self.engine)
        self.rudiment_routine = RudimentPracticeRoutine(self.engine, parent=self.engine)

        # Groove system
        self.groove_library = GrooveLibrary()
        self.groove_routine = GrooveRoutine(self.engine, self.groove_library, parent=self.engine)

        self.engine.moveToThread(self.worker_thread)
        self.audio.moveToThread(self.worker_thread)
        self.groove_audio.moveToThread(self.groove_audio_thread)
        self.midi_out.moveToThread(self.worker_thread)
        # routines move with engine because they are children

        # Internal worker wiring
        self.engine.click.connect(self._on_engine_click)

        # Helpers
        self.tap = TapTempo()
        self.voice_announcer = BpmVoiceAnnouncer(self)

        # Local state tracking for UI
        self._running_state = False
        self._bar_index = 0
        self._groove_bars = 1
        self._groove_toggle_base_bar = 0
        self._metronome_toggle_base_bar = 0
        self._current_midi_port = ""
        self._current_bpm = self.engine.bpm
        self._ladder_running = False
        self._ladder_active_config = None
        self._ladder_bar_counter = 0
        self._ladder_bars_per_step = 0
        self._ladder_warning_active = False
        self._ladder_last_approach_bpm = None
        self._suppress_next_start_announcement = False
        self._timer_text_scale = 1.0
        self._ladder_text_scale = 1.0
        self._progress_text_scale = 1.0
        self._remote_http_port = HTTP_PORT
        self._remote_discovery_port = DISCOVERY_PORT
        self._groove_practice_running = False
        self._groove_practice_index = -1
        self._groove_practice_items = []
        self._groove_practice_order = []
        self._groove_practice_order_pos = -1
        self._groove_practice_phase = None
        self._groove_practice_target_ms = 0
        self._groove_practice_elapsed = QElapsedTimer()
        self._groove_practice_paused_ms = 0
        self._groove_practice_pause_started = None
        self._groove_practice_count_in_bars = 0
        self._groove_practice_count_in_remaining = 0
        self._groove_practice_rest_seconds = 0.0
        self._groove_practice_shuffle = False
        self._groove_practice_loop = False
        self._groove_practice_total_ms = 0
        self._groove_practice_completed_ms = 0
        self._groove_practice_current_count_in_ms = 0
        self._groove_practice_current_play_ms = 0
        self._groove_practice_current_rest_ms = 0
        self._groove_practice_active_name = ""
        self._groove_practice_presets = {}
        self._groove_practice_restore = {}
        self.remote_state = ControlState(
            "Drum Metronome",
            bpm=self.engine.bpm,
            running=self._running_state,
            http_port=self._remote_http_port,
        )
        self.control_server = None

        # UI
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QVBoxLayout(main_widget)
        main_layout.setContentsMargins(16, 0, 16, 12)
        main_layout.setSpacing(10)

        # Header with Session Time
        header_layout = QVBoxLayout()
        header_layout.setContentsMargins(0, 16, 0, 8)
        header_layout.setSpacing(6)

        self.lbl_workout_time = QLabel("00:00")
        self.lbl_workout_time.setObjectName("workoutTime")
        self.lbl_workout_time.setAlignment(Qt.AlignCenter)

        self.ladder_progress = QProgressBar()
        self.ladder_progress.setRange(0, 100)
        self.ladder_progress.setValue(0)
        self.ladder_progress.setFormat("Ladder Inactive")
        self.ladder_progress.setTextVisible(True)
        self.ladder_progress.setMinimumWidth(300)
        self.ladder_progress.setMaximumWidth(380)

        self.practice_progress = QProgressBar()
        self.practice_progress.setRange(0, 100)
        self.practice_progress.setValue(0)
        self.practice_progress.setFormat("Practice Inactive")
        self.practice_progress.setTextVisible(True)
        self.practice_progress.setMinimumWidth(240)
        self.practice_progress.setMaximumWidth(320)

        timer_row = QHBoxLayout()
        timer_row.addStretch(1)
        timer_row.addWidget(self.lbl_workout_time)
        timer_row.addSpacing(16)
        timer_row.addWidget(self.ladder_progress)
        timer_row.addSpacing(12)
        timer_row.addWidget(self.practice_progress)
        timer_row.addStretch(1)
        header_layout.addLayout(timer_row)

        ladder_status_row = QHBoxLayout()
        ladder_status_row.addStretch(1)
        self.lbl_ladder_current = QLabel("Ladder: -- BPM")
        self.lbl_ladder_current.setObjectName("ladderCurrent")
        self.lbl_ladder_next = QLabel("Next: -- BPM")
        self.lbl_ladder_next.setObjectName("ladderNext")
        ladder_status_row.addWidget(self.lbl_ladder_current)
        ladder_status_row.addSpacing(12)
        ladder_status_row.addWidget(self.lbl_ladder_next)
        ladder_status_row.addSpacing(16)
        self.lbl_practice_total = QLabel("Routine: --")
        self.lbl_practice_total.setObjectName("practiceTotal")
        ladder_status_row.addWidget(self.lbl_practice_total)
        ladder_status_row.addStretch(1)
        header_layout.addLayout(ladder_status_row)

        reset_row = QHBoxLayout()
        reset_row.addStretch(1)
        self.btn_reset_workout = QPushButton("Reset Clock")
        self.btn_reset_workout.setObjectName("resetButton")
        reset_row.addWidget(self.btn_reset_workout)
        reset_row.addStretch(1)
        header_layout.addLayout(reset_row)

        self.lbl_groove_name = QLabel("None")
        self.lbl_groove_name.setObjectName("grooveName")
        self.lbl_groove_name.setAlignment(Qt.AlignCenter)
        groove_name_row = QHBoxLayout()
        groove_name_row.addStretch(1)
        groove_name_row.addWidget(self.lbl_groove_name)
        groove_name_row.addStretch(1)
        header_layout.addLayout(groove_name_row)

        main_layout.addLayout(header_layout)

        # Beat indicator (fixed at top)
        self.indicator = BeatIndicator()
        main_layout.addWidget(self.indicator)

        # Drum staff widget (fixed below beat indicator)
        self.drum_staff = DrumStaffWidget()
        main_layout.addWidget(self.drum_staff)

        # Compact control panel
        control_panel = QFrame()
        control_panel.setObjectName("controlPanel")
        control_layout = QVBoxLayout(control_panel)
        control_layout.setContentsMargins(12, 10, 12, 10)
        control_layout.setSpacing(8)

        bpm_row = QHBoxLayout()
        bpm_row.setSpacing(10)
        bpm_row.addWidget(QLabel("BPM"))
        self.bpm_spin = QSpinBox()
        self.bpm_spin.setRange(20, 400)
        self.bpm_spin.setValue(self.engine.bpm)
        self.bpm_slider = QSlider(Qt.Horizontal)
        self.bpm_slider.setRange(20, 400)
        self.bpm_slider.setValue(self.engine.bpm)
        self.btn_tap = QPushButton("Tap")
        self.btn_start = QPushButton("Start")
        bpm_row.addWidget(self.bpm_spin)
        bpm_row.addWidget(self.bpm_slider, 1)
        bpm_row.addWidget(self.btn_tap)
        bpm_row.addWidget(self.btn_start)
        control_layout.addLayout(bpm_row)

        groove_row = QHBoxLayout()
        groove_row.setSpacing(10)
        groove_row.addWidget(QLabel("Groove"))
        self.groove_combo = QComboBox()
        self.groove_combo.addItems(self.groove_library.get_groove_names())
        groove_row.addWidget(self.groove_combo, 1)
        self._update_groove_label(self.groove_combo.currentText())
        self.btn_groove_controls = QPushButton("Options")
        groove_row.addWidget(self.btn_groove_controls)
        control_layout.addLayout(groove_row)

        toggle_row = QHBoxLayout()
        toggle_row.setSpacing(10)
        self.chk_toggle_groove_silence = QCheckBox("Toggle Groove Silence")
        self.chk_toggle_metronome_silence = QCheckBox("Toggle Metronome Silence")
        toggle_row.addWidget(self.chk_toggle_groove_silence)
        toggle_row.addWidget(self.chk_toggle_metronome_silence)
        toggle_row.addStretch(1)
        control_layout.addLayout(toggle_row)

        main_layout.addWidget(control_panel)

        # Settings widgets
        self.beats_spin = QSpinBox()
        self.beats_spin.setRange(1, 12)
        self.beats_spin.setValue(self.engine.beats_per_bar)
        self.subdiv_spin = QSpinBox()
        self.subdiv_spin.setRange(1, 12)
        self.subdiv_spin.setValue(self.engine.subdivision)
        self.click_subdiv_spin = QSpinBox()
        self.click_subdiv_spin.setRange(1, 12)
        self.click_subdiv_spin.setValue(self.engine.click_subdivision)
        self.click_subdiv_spin.setMaximum(self.subdiv_spin.value())
        self.chk_accent = QCheckBox("Accent on 1")
        self.chk_accent.setChecked(True)
        self._last_staff_subdiv = self.subdiv_spin.value()

        self.device_combo = QComboBox()
        self.btn_test = QPushButton("Test Click")

        self.normal_sound_combo = QComboBox()
        self.normal_sound_combo.addItems(self.audio.get_available_sounds())
        self.accent_sound_combo = QComboBox()
        self.accent_sound_combo.addItems(self.audio.get_available_sounds())

        default_sound = "Woodblock"
        idx = self.normal_sound_combo.findText(default_sound)
        if idx >= 0:
            self.normal_sound_combo.setCurrentIndex(idx)
        idx = self.accent_sound_combo.findText(default_sound)
        if idx >= 0:
            self.accent_sound_combo.setCurrentIndex(idx)

        self.click_volume_slider = QSlider(Qt.Horizontal)
        self.click_volume_slider.setRange(0, 100)
        self.click_volume_slider.setValue(100)

        self.chk_voice_announcements = QCheckBox("Voice Announcements")
        self.chk_voice_announcements.setChecked(True)
        self.voice_combo = QComboBox()
        self.voice_rate_slider = QSlider(Qt.Horizontal)
        self.voice_rate_slider.setRange(5, 15)
        self.voice_rate_slider.setValue(10)
        self.voice_rate_value = QLabel("")
        self._voice_map = {}

        # Settings dialog
        self.settings_dialog = QDialog(self)
        self.settings_dialog.setWindowTitle("Metronome Settings")
        self.settings_dialog.setModal(True)
        settings_layout = QVBoxLayout(self.settings_dialog)
        settings_layout.setContentsMargins(16, 16, 16, 12)
        settings_layout.setSpacing(10)

        meter_group = QGroupBox("Meter")
        meter_layout = QGridLayout(meter_group)
        meter_layout.setHorizontalSpacing(10)
        meter_layout.setVerticalSpacing(8)
        meter_layout.addWidget(QLabel("Beats/Bar"), 0, 0)
        meter_layout.addWidget(self.beats_spin, 0, 1)
        meter_layout.addWidget(QLabel("Staff Subdivision"), 1, 0)
        meter_layout.addWidget(self.subdiv_spin, 1, 1)
        meter_layout.addWidget(QLabel("Click Subdivision"), 2, 0)
        meter_layout.addWidget(self.click_subdiv_spin, 2, 1)
        meter_layout.addWidget(self.chk_accent, 3, 0, 1, 2)
        meter_layout.setColumnStretch(1, 1)
        settings_layout.addWidget(meter_group)

        audio_group = QGroupBox("Audio Output")
        audio_layout = QGridLayout(audio_group)
        audio_layout.setHorizontalSpacing(10)
        audio_layout.setVerticalSpacing(8)
        audio_layout.addWidget(QLabel("Device"), 0, 0)
        audio_layout.addWidget(self.device_combo, 0, 1)
        audio_layout.addWidget(self.btn_test, 0, 2)
        audio_layout.setColumnStretch(1, 1)
        settings_layout.addWidget(audio_group)

        sound_group = QGroupBox("Sounds")
        sound_layout = QGridLayout(sound_group)
        sound_layout.setHorizontalSpacing(10)
        sound_layout.setVerticalSpacing(8)
        sound_layout.addWidget(QLabel("Normal"), 0, 0)
        sound_layout.addWidget(self.normal_sound_combo, 0, 1)
        sound_layout.addWidget(QLabel("Accent"), 1, 0)
        sound_layout.addWidget(self.accent_sound_combo, 1, 1)
        sound_layout.addWidget(QLabel("Volume"), 2, 0)
        sound_layout.addWidget(self.click_volume_slider, 2, 1)
        sound_layout.setColumnStretch(1, 1)
        settings_layout.addWidget(sound_group)

        voice_group = QGroupBox("Voice Announcements")
        voice_layout = QGridLayout(voice_group)
        voice_layout.setHorizontalSpacing(10)
        voice_layout.setVerticalSpacing(8)
        voice_layout.addWidget(self.chk_voice_announcements, 0, 0, 1, 2)
        voice_layout.addWidget(QLabel("Voice"), 1, 0)
        voice_layout.addWidget(self.voice_combo, 1, 1, 1, 2)
        voice_layout.addWidget(QLabel("Rate"), 2, 0)
        voice_layout.addWidget(self.voice_rate_slider, 2, 1)
        voice_layout.addWidget(self.voice_rate_value, 2, 2)
        voice_layout.setColumnStretch(1, 1)
        settings_layout.addWidget(voice_group)

        if not self.voice_announcer.is_available():
            self.chk_voice_announcements.setChecked(False)
            self.chk_voice_announcements.setEnabled(False)
            self.voice_combo.setEnabled(False)
            self.voice_rate_slider.setEnabled(False)
            self.voice_rate_value.setEnabled(False)

        settings_buttons = QDialogButtonBox(QDialogButtonBox.Close)
        settings_buttons.rejected.connect(self.settings_dialog.reject)
        settings_layout.addWidget(settings_buttons)

        # Practice widgets
        self.r_start = QSpinBox()
        self.r_start.setRange(20, 400)
        self.r_start.setValue(80)
        self.r_end = QSpinBox()
        self.r_end.setRange(20, 400)
        self.r_end.setValue(120)
        self.r_step = QSpinBox()
        self.r_step.setRange(1, 50)
        self.r_step.setValue(5)
        self.r_bars = QSpinBox()
        self.r_bars.setRange(1, 32)
        self.r_bars.setValue(4)
        self.btn_routine = QPushButton("Start Ladder")

        ladder_group = QGroupBox("Tempo Ladder")
        ladder_layout = QGridLayout(ladder_group)
        ladder_layout.setHorizontalSpacing(10)
        ladder_layout.setVerticalSpacing(8)
        ladder_layout.addWidget(QLabel("Start"), 0, 0)
        ladder_layout.addWidget(self.r_start, 0, 1)
        ladder_layout.addWidget(QLabel("End"), 0, 2)
        ladder_layout.addWidget(self.r_end, 0, 3)
        ladder_layout.addWidget(QLabel("Step"), 0, 4)
        ladder_layout.addWidget(self.r_step, 0, 5)
        ladder_layout.addWidget(QLabel("Bars/Step"), 0, 6)
        ladder_layout.addWidget(self.r_bars, 0, 7)
        ladder_layout.addWidget(self.btn_routine, 0, 8)
        ladder_layout.setColumnStretch(9, 1)
        main_layout.addWidget(ladder_group)

        self.mute_on_spin = QSpinBox()
        self.mute_on_spin.setRange(1, 64)
        self.mute_on_spin.setValue(self.engine.mute_bars_on)
        self.mute_off_spin = QSpinBox()
        self.mute_off_spin.setRange(0, 64)
        self.mute_off_spin.setValue(self.engine.mute_bars_off)
        self.mute_off_spin.setSpecialValueText("Disabled")

        self.rudiment_widget = RudimentWidget()
        self.rud_bars = QSpinBox()
        self.rud_bars.setRange(1, 32)
        self.rud_bars.setValue(1)
        self.rud_bars.setPrefix("Switch every ")
        self.rud_bars.setSuffix(" bars")
        self.rud_bars.setMinimumWidth(220)
        self.btn_rudiment = QPushButton("Start Rudiments")

        self.practice_dialog = QDialog(self)
        self.practice_dialog.setWindowTitle("Practice & Routines")
        self.practice_dialog.setModal(True)
        practice_layout = QVBoxLayout(self.practice_dialog)
        practice_layout.setContentsMargins(16, 16, 16, 12)
        practice_layout.setSpacing(10)

        mute_group = QGroupBox("Mute Training")
        mute_layout = QGridLayout(mute_group)
        mute_layout.setHorizontalSpacing(10)
        mute_layout.setVerticalSpacing(8)
        mute_layout.addWidget(QLabel("Bars On"), 0, 0)
        mute_layout.addWidget(self.mute_on_spin, 0, 1)
        mute_layout.addWidget(QLabel("Bars Off"), 0, 2)
        mute_layout.addWidget(self.mute_off_spin, 0, 3)
        mute_layout.setColumnStretch(4, 1)
        practice_layout.addWidget(mute_group)

        practice_layout.addWidget(self.rudiment_widget)
        rud_controls = QHBoxLayout()
        rud_controls.addWidget(self.rud_bars)
        rud_controls.addStretch(1)
        rud_controls.addWidget(self.btn_rudiment)
        practice_layout.addLayout(rud_controls)

        practice_buttons = QDialogButtonBox(QDialogButtonBox.Close)
        practice_buttons.rejected.connect(self.practice_dialog.reject)
        practice_layout.addWidget(practice_buttons)

        # Groove practice routine widgets
        self.groove_practice_dialog = QDialog(self)
        self.groove_practice_dialog.setWindowTitle("Groove Practice Routine")
        self.groove_practice_dialog.setModal(True)
        groove_practice_layout = QVBoxLayout(self.groove_practice_dialog)
        groove_practice_layout.setContentsMargins(16, 16, 16, 12)
        groove_practice_layout.setSpacing(10)

        preset_row = QHBoxLayout()
        preset_row.addWidget(QLabel("Routine"))
        self.groove_practice_preset_combo = QComboBox()
        preset_row.addWidget(self.groove_practice_preset_combo, 1)
        self.btn_groove_practice_new = QPushButton("New")
        self.btn_groove_practice_save = QPushButton("Save")
        self.btn_groove_practice_save_as = QPushButton("Save As")
        self.btn_groove_practice_delete = QPushButton("Delete")
        preset_row.addWidget(self.btn_groove_practice_new)
        preset_row.addWidget(self.btn_groove_practice_save)
        preset_row.addWidget(self.btn_groove_practice_save_as)
        preset_row.addWidget(self.btn_groove_practice_delete)
        groove_practice_layout.addLayout(preset_row)

        preset_action_row = QHBoxLayout()
        preset_action_row.addStretch(1)
        self.btn_groove_practice_import = QPushButton("Import")
        self.btn_groove_practice_export = QPushButton("Export")
        preset_action_row.addWidget(self.btn_groove_practice_import)
        preset_action_row.addWidget(self.btn_groove_practice_export)
        groove_practice_layout.addLayout(preset_action_row)

        groove_practice_status = QGroupBox("Routine Status")
        groove_practice_status_layout = QVBoxLayout(groove_practice_status)
        self.lbl_groove_practice_current = QLabel("Ready")
        self.lbl_groove_practice_current.setAlignment(Qt.AlignCenter)
        self.lbl_groove_practice_next = QLabel("Next: --")
        self.lbl_groove_practice_next.setAlignment(Qt.AlignCenter)
        self.lbl_groove_practice_remaining = QLabel("Remaining: --")
        self.lbl_groove_practice_remaining.setAlignment(Qt.AlignCenter)
        groove_practice_status_layout.addWidget(self.lbl_groove_practice_current)
        groove_practice_status_layout.addWidget(self.lbl_groove_practice_next)
        groove_practice_status_layout.addWidget(self.lbl_groove_practice_remaining)
        groove_practice_layout.addWidget(groove_practice_status)

        groove_practice_options = QGroupBox("Routine Options")
        groove_practice_options_layout = QGridLayout(groove_practice_options)
        groove_practice_options_layout.setHorizontalSpacing(10)
        groove_practice_options_layout.setVerticalSpacing(8)
        self.groove_practice_count_in = QSpinBox()
        self.groove_practice_count_in.setRange(0, 16)
        self.groove_practice_count_in.setSuffix(" bars")
        self.groove_practice_rest = QDoubleSpinBox()
        self.groove_practice_rest.setRange(0.0, 60.0)
        self.groove_practice_rest.setDecimals(1)
        self.groove_practice_rest.setSingleStep(0.5)
        self.groove_practice_rest.setSuffix(" sec")
        self.chk_groove_practice_shuffle = QCheckBox("Shuffle order")
        self.chk_groove_practice_loop = QCheckBox("Loop routine")
        groove_practice_options_layout.addWidget(QLabel("Count-in"), 0, 0)
        groove_practice_options_layout.addWidget(self.groove_practice_count_in, 0, 1)
        groove_practice_options_layout.addWidget(QLabel("Rest gap"), 0, 2)
        groove_practice_options_layout.addWidget(self.groove_practice_rest, 0, 3)
        groove_practice_options_layout.addWidget(self.chk_groove_practice_shuffle, 1, 0, 1, 2)
        groove_practice_options_layout.addWidget(self.chk_groove_practice_loop, 1, 2, 1, 2)
        groove_practice_options_layout.setColumnStretch(4, 1)
        groove_practice_layout.addWidget(groove_practice_options)

        groove_practice_group = QGroupBox("Groove List")
        groove_practice_group_layout = QVBoxLayout(groove_practice_group)
        self.groove_practice_table = QTableWidget(0, 7)
        self.groove_practice_table.setHorizontalHeaderLabels(
            ["Groove", "BPM", "Minutes", "Loop", "Click Subdiv", "Mute On", "Mute Off"]
        )
        self.groove_practice_table.verticalHeader().setVisible(False)
        self.groove_practice_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.groove_practice_table.setSelectionMode(QAbstractItemView.SingleSelection)
        header = self.groove_practice_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Stretch)
        for col in range(1, 7):
            header.setSectionResizeMode(col, QHeaderView.ResizeToContents)
        groove_practice_group_layout.addWidget(self.groove_practice_table)
        groove_practice_layout.addWidget(groove_practice_group)

        groove_practice_controls = QHBoxLayout()
        self.btn_groove_practice_add = QPushButton("Add Groove")
        self.btn_groove_practice_remove = QPushButton("Remove Selected")
        self.btn_groove_practice_up = QPushButton("Move Up")
        self.btn_groove_practice_down = QPushButton("Move Down")
        groove_practice_controls.addWidget(self.btn_groove_practice_add)
        groove_practice_controls.addWidget(self.btn_groove_practice_remove)
        groove_practice_controls.addWidget(self.btn_groove_practice_up)
        groove_practice_controls.addWidget(self.btn_groove_practice_down)
        groove_practice_controls.addStretch(1)
        groove_practice_layout.addLayout(groove_practice_controls)

        groove_practice_action_row = QHBoxLayout()
        self.btn_groove_practice_prev = QPushButton("Previous")
        self.btn_groove_practice_restart = QPushButton("Restart")
        self.btn_groove_practice_skip = QPushButton("Skip")
        groove_practice_action_row.addWidget(self.btn_groove_practice_prev)
        groove_practice_action_row.addWidget(self.btn_groove_practice_restart)
        groove_practice_action_row.addWidget(self.btn_groove_practice_skip)
        groove_practice_action_row.addStretch(1)
        self.btn_groove_practice_start = QPushButton("Start Routine")
        groove_practice_action_row.addWidget(self.btn_groove_practice_start)
        groove_practice_layout.addLayout(groove_practice_action_row)

        self.lbl_groove_practice_total = QLabel("Total: --")
        self.lbl_groove_practice_total.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        groove_practice_layout.addWidget(self.lbl_groove_practice_total)

        groove_practice_buttons = QDialogButtonBox(QDialogButtonBox.Close)
        groove_practice_buttons.rejected.connect(self.groove_practice_dialog.reject)
        groove_practice_layout.addWidget(groove_practice_buttons)

        # Groove widgets
        self.btn_edit_groove = QPushButton("Edit Groove")
        self.groove_loop_spin = QSpinBox()
        self.groove_loop_spin.setRange(0, 999)
        self.groove_loop_spin.setValue(0)
        self.groove_loop_spin.setPrefix("Loop: ")
        self.groove_loop_spin.setSuffix(" times (0=inf)")
        self.groove_loop_spin.setMinimumWidth(220)
        self.chk_groove_midi = QCheckBox("Groove Audio")

        self.lbl_groove_current = QLabel(self.groove_combo.currentText() or "None")

        self.groove_dialog = QDialog(self)
        self.groove_dialog.setWindowTitle("Groove Controls")
        self.groove_dialog.setModal(True)
        groove_layout = QVBoxLayout(self.groove_dialog)
        groove_layout.setContentsMargins(16, 16, 16, 12)
        groove_layout.setSpacing(10)

        groove_current_row = QHBoxLayout()
        groove_current_row.addWidget(QLabel("Current Groove"))
        groove_current_row.addWidget(self.lbl_groove_current, 1)
        groove_layout.addLayout(groove_current_row)

        groove_options_row = QHBoxLayout()
        groove_options_row.addWidget(QLabel("Loop Count"))
        groove_options_row.addWidget(self.groove_loop_spin)
        groove_options_row.addSpacing(10)
        groove_options_row.addWidget(self.chk_groove_midi)
        groove_options_row.addStretch(1)
        groove_layout.addLayout(groove_options_row)

        groove_edit_row = QHBoxLayout()
        groove_edit_row.addStretch(1)
        groove_edit_row.addWidget(self.btn_edit_groove)
        groove_layout.addLayout(groove_edit_row)

        groove_buttons = QDialogButtonBox(QDialogButtonBox.Close)
        groove_buttons.rejected.connect(self.groove_dialog.reject)
        groove_layout.addWidget(groove_buttons)

        # MIDI widgets
        self.chk_midi_out = QCheckBox("Enable MIDI Out")
        self.midi_port_combo = QComboBox()
        self.btn_midi_refresh = QPushButton("Refresh")
        self.lbl_midi_status = QLabel("MIDI: not connected")

        self.midi_note_spins = {}
        self.midi_velocity_spins = {}
        voice_labels = [
            ("crash", "Crash"),
            ("ride", "Ride"),
            ("hihat_closed", "HH Closed"),
            ("hihat_open", "HH Open"),
            ("tom1", "Tom 1"),
            ("snare", "Snare"),
            ("tom2", "Tom 2"),
            ("tom3", "Tom 3"),
            ("kick", "Kick"),
        ]

        midi_map_group = QGroupBox("Drum Mapping")
        midi_map_layout = QGridLayout(midi_map_group)
        midi_map_layout.setHorizontalSpacing(10)
        midi_map_layout.setVerticalSpacing(6)
        midi_map_layout.addWidget(QLabel("Drum"), 0, 0)
        midi_map_layout.addWidget(QLabel("Note"), 0, 1)
        midi_map_layout.addWidget(QLabel("Velocity"), 0, 2)
        for row, (voice, label) in enumerate(voice_labels, start=1):
            midi_map_layout.addWidget(QLabel(label), row, 0)
            note_spin = QSpinBox()
            note_spin.setRange(0, 127)
            velocity_spin = QSpinBox()
            velocity_spin.setRange(1, 127)
            default_note, default_vel = DEFAULT_DRUM_MAPPING.get(voice, (36, 100))
            note_spin.setValue(default_note)
            velocity_spin.setValue(default_vel)
            midi_map_layout.addWidget(note_spin, row, 1)
            midi_map_layout.addWidget(velocity_spin, row, 2)
            self.midi_note_spins[voice] = note_spin
            self.midi_velocity_spins[voice] = velocity_spin

        self.midi_dialog = QDialog(self)
        self.midi_dialog.setWindowTitle("MIDI Output")
        self.midi_dialog.setModal(True)
        midi_layout = QVBoxLayout(self.midi_dialog)
        midi_layout.setContentsMargins(16, 16, 16, 12)
        midi_layout.setSpacing(10)

        midi_top_row = QHBoxLayout()
        midi_top_row.addWidget(self.chk_midi_out)
        midi_top_row.addSpacing(10)
        midi_top_row.addWidget(QLabel("Output Port"))
        midi_top_row.addWidget(self.midi_port_combo, 1)
        midi_top_row.addWidget(self.btn_midi_refresh)
        midi_layout.addLayout(midi_top_row)
        midi_layout.addWidget(self.lbl_midi_status)
        midi_layout.addWidget(midi_map_group)

        midi_buttons = QDialogButtonBox(QDialogButtonBox.Close)
        midi_buttons.rejected.connect(self.midi_dialog.reject)
        midi_layout.addWidget(midi_buttons)

        # Footer info
        self.info = QLabel("Ready")
        self.statusBar().addWidget(self.info)

        # Menu bar
        self._build_menu()

        # Connections
        # -- Control (UI -> Worker via Auto-Queued Slots or Signals) --
        self.bpm_spin.valueChanged.connect(self.engine.set_bpm)
        self.bpm_spin.valueChanged.connect(self.bpm_slider.setValue)
        self.bpm_slider.valueChanged.connect(self.bpm_spin.setValue)
        
        self.beats_spin.valueChanged.connect(self.engine.set_beats_per_bar)
        self.beats_spin.valueChanged.connect(lambda v: self.indicator.set_beats(v))
        self.beats_spin.valueChanged.connect(self._on_meter_changed)
        
        self.subdiv_spin.valueChanged.connect(self._on_staff_subdivision_changed)
        self.click_subdiv_spin.valueChanged.connect(self.engine.set_click_subdivision)
        self.chk_accent.toggled.connect(self.engine.set_accent_on_one)
        self.chk_accent.toggled.connect(self.indicator.set_accent_enabled)
        
        self.mute_on_spin.valueChanged.connect(self.engine.set_mute_bars_on)
        self.mute_off_spin.valueChanged.connect(self.engine.set_mute_bars_off)

        self.sig_start.connect(self.engine.start)
        self.sig_stop.connect(self.engine.stop)
        self.sig_change_device.connect(self.audio.set_output_device_by_name)
        self.sig_change_device.connect(self.groove_audio.set_output_device_by_name)
        self.sig_audio_play.connect(self.audio.play)
        
        self.sig_ladder_start.connect(self.ladder.start)
        self.sig_ladder_stop.connect(self.ladder.stop)
        self.sig_ladder_configure.connect(self.ladder.configure)
        
        self.sig_rudiment_start.connect(self.rudiment_routine.start)
        self.sig_rudiment_stop.connect(self.rudiment_routine.stop)
        self.sig_rudiment_configure.connect(self.rudiment_routine.set_bars_per_rudiment)
        self.sig_rudiment_enable_list.connect(self.rudiment_routine.set_enabled_rudiments)
        self.sig_rudiment_lead_hand.connect(self.rudiment_routine.set_lead_hand)

        self.sig_groove_start.connect(self.groove_routine.start)
        self.sig_groove_stop.connect(self.groove_routine.stop)
        self.sig_groove_set.connect(self.groove_routine.set_groove)
        self.sig_groove_loop.connect(self.groove_routine.set_loop_count)

        self.sig_init_audio.connect(self.audio.initialize)
        self.sig_init_audio.connect(self.groove_audio.initialize)
        self.sig_init_engine.connect(self.engine.initialize)
        self.sig_update_sounds.connect(self.audio.set_sounds)
        self.sig_click_volume.connect(self.audio.set_volume)
        self.sig_midi_init.connect(self.midi_out.initialize)
        self.sig_midi_set_port.connect(self.midi_out.set_output_port_by_name)
        self.sig_midi_set_voice.connect(self.midi_out.set_voice_mapping)
        self.sig_groove_midi.connect(self.midi_out.play_notes)
        self.sig_remote_start.connect(self._remote_start)
        self.sig_remote_stop.connect(self._remote_stop)
        self.sig_remote_set_bpm.connect(self._remote_set_bpm)

        # -- Feedback (Worker -> UI) --
        self.engine.tick.connect(self._on_tick)
        self.engine.barAdvanced.connect(self._on_bar_advanced)
        self.engine.bpmChanged.connect(self._on_bpm_changed)
        self.engine.runningChanged.connect(self._on_running_changed)
        self.audio.deviceChanged.connect(self._on_device_changed_info)
        
        self.ladder.stateChanged.connect(self._routine_state)
        self.ladder.routineFinished.connect(self._routine_finished)
        
        self.rudiment_routine.activeChanged.connect(self._rudiment_active_changed)
        self.rudiment_routine.rudimentChanged.connect(self._rudiment_update)

        self.groove_routine.activeChanged.connect(self._groove_active_changed)
        self.groove_routine.grooveChanged.connect(self._groove_changed)
        self.groove_routine.positionChanged.connect(self.drum_staff.set_position)
        self.groove_routine.notesPlaying.connect(self.drum_staff.set_active_notes)
        self.groove_routine.notesPlaying.connect(self.groove_audio.play_notes)
        self.groove_routine.notesPlaying.connect(self._on_groove_notes)
        self.midi_out.statusChanged.connect(self._on_midi_status_changed)

        # -- Local UI Logic --
        self.btn_start.clicked.connect(self._toggle_start)
        self.btn_tap.clicked.connect(self._tap_tempo)
        self.btn_routine.clicked.connect(self._toggle_routine)
        self.r_start.valueChanged.connect(lambda _: self._update_ladder_status())
        self.r_end.valueChanged.connect(lambda _: self._update_ladder_status())
        self.r_step.valueChanged.connect(lambda _: self._update_ladder_status())
        self.r_bars.valueChanged.connect(lambda _: self._update_ladder_status())
        self.btn_rudiment.clicked.connect(self._toggle_rudiment)
        self.rud_bars.valueChanged.connect(self.sig_rudiment_configure.emit)
        self.rudiment_widget.selectionChanged.connect(self.sig_rudiment_enable_list.emit)
        self.rudiment_widget.leadHandChanged.connect(self.sig_rudiment_lead_hand.emit)
        self.groove_practice_preset_combo.currentTextChanged.connect(self._on_groove_practice_preset_selected)
        self.btn_groove_practice_new.clicked.connect(self._new_groove_practice_preset)
        self.btn_groove_practice_save.clicked.connect(self._save_groove_practice_preset)
        self.btn_groove_practice_save_as.clicked.connect(self._save_groove_practice_preset_as)
        self.btn_groove_practice_delete.clicked.connect(self._delete_groove_practice_preset)
        self.btn_groove_practice_import.clicked.connect(self._import_groove_practice_preset)
        self.btn_groove_practice_export.clicked.connect(self._export_groove_practice_preset)
        self.groove_practice_count_in.valueChanged.connect(lambda _: self._update_groove_practice_totals())
        self.groove_practice_rest.valueChanged.connect(lambda _: self._update_groove_practice_totals())
        self.chk_groove_practice_shuffle.toggled.connect(lambda _: self._update_groove_practice_totals())
        self.chk_groove_practice_loop.toggled.connect(lambda _: self._update_groove_practice_totals())
        self.btn_groove_practice_add.clicked.connect(self._add_groove_practice_row)
        self.btn_groove_practice_remove.clicked.connect(self._remove_groove_practice_row)
        self.btn_groove_practice_up.clicked.connect(lambda: self._move_groove_practice_row(-1))
        self.btn_groove_practice_down.clicked.connect(lambda: self._move_groove_practice_row(1))
        self.btn_groove_practice_start.clicked.connect(self._toggle_groove_practice)
        self.btn_groove_practice_prev.clicked.connect(self._previous_groove_practice)
        self.btn_groove_practice_restart.clicked.connect(self._restart_groove_practice)
        self.btn_groove_practice_skip.clicked.connect(self._skip_groove_practice)
        self.btn_groove_controls.clicked.connect(self._open_groove_dialog)
        self.btn_edit_groove.clicked.connect(self._edit_groove)
        self.groove_combo.currentTextChanged.connect(self._on_groove_selected)
        self.groove_combo.currentTextChanged.connect(self._update_groove_label)
        self.groove_loop_spin.valueChanged.connect(self.sig_groove_loop.emit)
        self.chk_groove_midi.toggled.connect(self.groove_audio.set_enabled)
        self.chk_groove_midi.setChecked(True)
        self.chk_midi_out.toggled.connect(self.midi_out.set_enabled)
        self.chk_toggle_groove_silence.toggled.connect(self._on_toggle_groove_silence)
        self.chk_toggle_metronome_silence.toggled.connect(self._on_toggle_metronome_silence)
        self.midi_port_combo.currentTextChanged.connect(self._on_midi_port_changed)
        self.btn_midi_refresh.clicked.connect(self._populate_midi_ports)
        self.btn_reset_workout.clicked.connect(self._reset_workout_time)
        self.device_combo.currentTextChanged.connect(self._device_changed)
        self.normal_sound_combo.currentTextChanged.connect(self._on_sound_settings_changed)
        self.accent_sound_combo.currentTextChanged.connect(self._on_sound_settings_changed)
        self.click_volume_slider.valueChanged.connect(self._on_click_volume_changed)
        self.chk_voice_announcements.toggled.connect(self._on_voice_enabled_changed)
        self.voice_combo.currentIndexChanged[int].connect(self._on_voice_selected)
        self.voice_rate_slider.valueChanged.connect(self._on_voice_rate_changed)
        self.btn_test.clicked.connect(lambda: self.sig_audio_play.emit(False))
        for voice in self.midi_note_spins:
            self.midi_note_spins[voice].valueChanged.connect(
                lambda _, v=voice: self._on_midi_mapping_changed(v)
            )
            self.midi_velocity_spins[voice].valueChanged.connect(
                lambda _, v=voice: self._on_midi_mapping_changed(v)
            )

        self.indicator.set_beats(self.beats_spin.value())
        self.indicator.set_accent_enabled(self.chk_accent.isChecked())

        self.control_server = ControlServer(
            self.remote_state,
            on_start=self.sig_remote_start.emit,
            on_stop=self.sig_remote_stop.emit,
            on_set_bpm=self.sig_remote_set_bpm.emit,
        )
        self.control_server.start(
            http_port=self._remote_http_port,
            discovery_port=self._remote_discovery_port,
        )
        
        # Workout timer
        self.workout_timer = QTimer()
        self.workout_timer.setInterval(1000)
        self.workout_timer.timeout.connect(self._update_workout_time)
        self.workout_seconds = 0
        
        # Populate rudiments
        self.rudiment_widget.set_available_rudiments(self.rudiment_routine.get_rudiment_names())

        # Load saved settings before initial setup
        self._populate_voice_options()
        self._load_settings()
        self._on_voice_rate_changed(self.voice_rate_slider.value())
        self._on_voice_enabled_changed(self.chk_voice_announcements.isChecked())
        self._update_ladder_status()
        self._update_ladder_progress()
        self._update_groove_practice_totals()
        self._update_practice_progress()

        # Initialize drum staff with first groove
        if self.groove_library.grooves:
            groove = self._configure_selected_groove()
            if groove:
                self.drum_staff.set_groove(groove)

        # Populate audio devices
        self._populate_devices()
        self._update_info_device_label()
        self._populate_midi_ports()
        self._apply_midi_mapping()
        self._on_click_volume_changed(self.click_volume_slider.value())

        # Start audio engine in worker thread
        self.sig_init_audio.emit()
        self.sig_init_engine.emit()
        self.sig_midi_init.emit()
        self._restore_running_state()

    def _build_menu(self):
        self.menuBar().setNativeMenuBar(False)

        session_menu = self.menuBar().addMenu("Session")
        self.action_toggle_start = QAction("Start", self)
        self.action_toggle_start.triggered.connect(self._toggle_start)
        session_menu.addAction(self.action_toggle_start)

        action_tap = QAction("Tap Tempo", self)
        action_tap.triggered.connect(self._tap_tempo)
        session_menu.addAction(action_tap)

        action_reset = QAction("Reset Clock", self)
        action_reset.triggered.connect(self._reset_workout_time)
        session_menu.addAction(action_reset)

        action_test = QAction("Test Click", self)
        action_test.triggered.connect(lambda: self.sig_audio_play.emit(False))
        session_menu.addAction(action_test)

        settings_menu = self.menuBar().addMenu("Settings")
        action_settings = QAction("Metronome Settings...", self)
        action_settings.triggered.connect(self._open_settings_dialog)
        settings_menu.addAction(action_settings)

        practice_menu = self.menuBar().addMenu("Practice")
        action_practice = QAction("Practice & Routines...", self)
        action_practice.triggered.connect(self._open_practice_dialog)
        practice_menu.addAction(action_practice)
        action_groove_practice = QAction("Groove Practice Routine...", self)
        action_groove_practice.triggered.connect(self._open_groove_practice_dialog)
        practice_menu.addAction(action_groove_practice)

        groove_menu = self.menuBar().addMenu("Groove")
        action_groove = QAction("Groove Controls...", self)
        action_groove.triggered.connect(self._open_groove_dialog)
        groove_menu.addAction(action_groove)

        action_edit = QAction("Edit Current Groove...", self)
        action_edit.triggered.connect(self._edit_groove)
        groove_menu.addAction(action_edit)

        staff_menu = self.menuBar().addMenu("Staff Adjustments")
        self.staff_scale_slider = QSlider(Qt.Horizontal)
        self.staff_scale_slider.setRange(10, 30)
        self.staff_scale_slider.setValue(int(round(self.drum_staff.ui_scale * 10)))
        self.staff_scale_slider.setMinimumWidth(220)
        self.staff_scale_value = QLabel("")
        self.staff_scale_slider.valueChanged.connect(self._on_staff_scale_changed)

        self.groove_scale_slider = QSlider(Qt.Horizontal)
        self.groove_scale_slider.setRange(5, 20)
        self.groove_scale_slider.setValue(int(round(self.drum_staff.note_scale * 10)))
        self.groove_scale_slider.setMinimumWidth(220)
        self.groove_scale_value = QLabel("")
        self.groove_scale_slider.valueChanged.connect(self._on_groove_scale_changed)

        staff_widget = QWidget()
        staff_layout = QVBoxLayout(staff_widget)
        staff_layout.setContentsMargins(12, 10, 12, 10)
        staff_layout.setSpacing(10)
        staff_layout.addWidget(
            self._build_staff_adjustment_row("Staff Scale", self.staff_scale_slider, self.staff_scale_value)
        )
        staff_layout.addWidget(
            self._build_staff_adjustment_row("Note Scale", self.groove_scale_slider, self.groove_scale_value)
        )
        self.chk_staff_scroll = QCheckBox("Scroll Staff (Center Playhead)")
        self.chk_staff_scroll.setChecked(self.drum_staff.is_scroll_staff())
        self.chk_staff_scroll.toggled.connect(self._on_staff_scroll_mode_changed)
        staff_layout.addWidget(self.chk_staff_scroll)
        self.header_timer_slider = QSlider(Qt.Horizontal)
        self.header_timer_slider.setRange(8, 20)
        self.header_timer_slider.setValue(10)
        self.header_timer_slider.setMinimumWidth(220)
        self.header_timer_value = QLabel("")
        self.header_timer_slider.valueChanged.connect(self._on_header_timer_scale_changed)
        staff_layout.addWidget(
            self._build_staff_adjustment_row("Timer Text", self.header_timer_slider, self.header_timer_value)
        )

        self.header_ladder_slider = QSlider(Qt.Horizontal)
        self.header_ladder_slider.setRange(8, 20)
        self.header_ladder_slider.setValue(10)
        self.header_ladder_slider.setMinimumWidth(220)
        self.header_ladder_value = QLabel("")
        self.header_ladder_slider.valueChanged.connect(self._on_header_ladder_scale_changed)
        staff_layout.addWidget(
            self._build_staff_adjustment_row("Ladder Text", self.header_ladder_slider, self.header_ladder_value)
        )

        self.header_progress_slider = QSlider(Qt.Horizontal)
        self.header_progress_slider.setRange(8, 20)
        self.header_progress_slider.setValue(10)
        self.header_progress_slider.setMinimumWidth(220)
        self.header_progress_value = QLabel("")
        self.header_progress_slider.valueChanged.connect(self._on_header_progress_scale_changed)
        staff_layout.addWidget(
            self._build_staff_adjustment_row("Progress Text", self.header_progress_slider, self.header_progress_value)
        )
        separator = QFrame()
        separator.setFrameShape(QFrame.HLine)
        separator.setFrameShadow(QFrame.Sunken)
        staff_layout.addWidget(separator)
        staff_layout.addWidget(QLabel("Rhythm Text Offset (0 = default, step = 0.5, + = down)"))
        rhythm_row = QWidget()
        rhythm_layout = QHBoxLayout(rhythm_row)
        rhythm_layout.setContentsMargins(0, 0, 0, 0)
        rhythm_layout.setSpacing(6)
        rhythm_layout.addWidget(QLabel("Rhythm Text"))
        rhythm_layout.addStretch(1)
        self.rhythm_text_offset_spin = QSpinBox()
        self.rhythm_text_offset_spin.setRange(-12, 12)
        self.rhythm_text_offset_spin.setSingleStep(1)
        self.rhythm_text_offset_spin.setValue(
            int(round(self.drum_staff.get_rhythm_text_offset() * 2))
        )
        self.rhythm_text_offset_spin.valueChanged.connect(
            lambda v: self._on_staff_rhythm_offset_changed(v / 2.0)
        )
        rhythm_layout.addWidget(self.rhythm_text_offset_spin)
        staff_layout.addWidget(rhythm_row)
        staff_layout.addWidget(QLabel("Voice Positions (0 = middle line, step = 0.5, + = down)"))

        mapping_widget = QWidget()
        mapping_layout = QGridLayout(mapping_widget)
        mapping_layout.setContentsMargins(0, 0, 0, 0)
        mapping_layout.setHorizontalSpacing(10)
        mapping_layout.setVerticalSpacing(6)
        self.staff_voice_position_spins = {}

        voice_rows = [
            ("crash", "Crash"),
            ("ride", "Ride"),
            ("hihat_closed", "HH Closed"),
            ("hihat_open", "HH Open"),
            ("tom1", "Tom 1"),
            ("snare", "Snare"),
            ("tom2", "Tom 2"),
            ("tom3", "Tom 3"),
            ("kick", "Kick"),
        ]
        for row, (voice, label) in enumerate(voice_rows):
            mapping_layout.addWidget(QLabel(label), row, 0)
            spin = QSpinBox()
            spin.setRange(-12, 12)
            spin.setSingleStep(1)
            spin.setValue(int(round(self.drum_staff.get_voice_position(voice) * 2)))
            spin.valueChanged.connect(lambda v, name=voice: self._on_staff_voice_position_changed(name, v / 2.0))
            mapping_layout.addWidget(spin, row, 1)
            self.staff_voice_position_spins[voice] = spin
        staff_layout.addWidget(mapping_widget)

        staff_action = QWidgetAction(self)
        staff_action.setDefaultWidget(staff_widget)
        staff_menu.addAction(staff_action)

        self._on_staff_scale_changed(self.staff_scale_slider.value())
        self._on_groove_scale_changed(self.groove_scale_slider.value())
        self._on_header_timer_scale_changed(self.header_timer_slider.value())
        self._on_header_ladder_scale_changed(self.header_ladder_slider.value())
        self._on_header_progress_scale_changed(self.header_progress_slider.value())

        midi_menu = self.menuBar().addMenu("MIDI")
        action_midi = QAction("MIDI Output...", self)
        action_midi.triggered.connect(self._open_midi_dialog)
        midi_menu.addAction(action_midi)

    def _build_staff_adjustment_row(self, label: str, slider: QSlider, value_label: QLabel) -> QWidget:
        row = QWidget()
        layout = QVBoxLayout(row)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(4)
        header = QHBoxLayout()
        header.addWidget(QLabel(label))
        header.addStretch(1)
        value_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        header.addWidget(value_label)
        layout.addLayout(header)
        layout.addWidget(slider)
        return row

    def _on_staff_scale_changed(self, value: int):
        scale = max(0.5, min(3.0, value / 10.0))
        if hasattr(self, "staff_scale_value"):
            self.staff_scale_value.setText(f"{scale:.1f}x")
        if hasattr(self, "drum_staff"):
            self.drum_staff.set_ui_scale(scale)

    def _on_groove_scale_changed(self, value: int):
        scale = max(0.5, min(2.5, value / 10.0))
        if hasattr(self, "groove_scale_value"):
            self.groove_scale_value.setText(f"{scale:.1f}x")
        if hasattr(self, "drum_staff"):
            self.drum_staff.set_note_scale(scale)

    def _on_staff_scroll_mode_changed(self, enabled: bool):
        if hasattr(self, "drum_staff"):
            self.drum_staff.set_scroll_staff(enabled)

    def _on_header_timer_scale_changed(self, value: int):
        scale = max(0.8, min(2.0, value / 10.0))
        self._timer_text_scale = scale
        if hasattr(self, "header_timer_value"):
            self.header_timer_value.setText(f"{scale:.1f}x")
        self._apply_header_text_scales()

    def _on_header_ladder_scale_changed(self, value: int):
        scale = max(0.8, min(2.0, value / 10.0))
        self._ladder_text_scale = scale
        if hasattr(self, "header_ladder_value"):
            self.header_ladder_value.setText(f"{scale:.1f}x")
        self._apply_header_text_scales()

    def _on_header_progress_scale_changed(self, value: int):
        scale = max(0.8, min(2.0, value / 10.0))
        self._progress_text_scale = scale
        if hasattr(self, "header_progress_value"):
            self.header_progress_value.setText(f"{scale:.1f}x")
        self._apply_header_text_scales()

    def _apply_header_text_scales(self):
        timer_size = max(12, int(round(30 * self._timer_text_scale)))
        ladder_size = max(8, int(round(11 * self._ladder_text_scale)))
        progress_size = max(8, int(round(11 * self._progress_text_scale)))
        if hasattr(self, "lbl_workout_time"):
            self.lbl_workout_time.setStyleSheet(
                f"font-size: {timer_size}pt; font-weight: 700; color: #e6e6e6;"
            )
        if hasattr(self, "lbl_ladder_current"):
            self.lbl_ladder_current.setStyleSheet(
                f"font-size: {ladder_size}pt; font-weight: 600; color: #6ad1c0;"
            )
        if hasattr(self, "lbl_ladder_next"):
            self.lbl_ladder_next.setStyleSheet(
                f"font-size: {ladder_size}pt; color: #9a9a9a;"
            )
        if hasattr(self, "lbl_practice_total"):
            self.lbl_practice_total.setStyleSheet(
                f"font-size: {ladder_size}pt; color: #b0b0b0;"
            )
        if hasattr(self, "ladder_progress"):
            font = self.ladder_progress.font()
            font.setPointSize(progress_size)
            self.ladder_progress.setFont(font)
            self.ladder_progress.setMinimumHeight(int(round(progress_size * 2.2)))
        if hasattr(self, "practice_progress"):
            font = self.practice_progress.font()
            font.setPointSize(progress_size)
            self.practice_progress.setFont(font)
            self.practice_progress.setMinimumHeight(int(round(progress_size * 2.2)))

    def _on_staff_rhythm_offset_changed(self, offset: float):
        if hasattr(self, "drum_staff"):
            self.drum_staff.set_rhythm_text_offset(offset)

    def _on_staff_voice_position_changed(self, voice: str, position: int):
        if hasattr(self, "drum_staff"):
            self.drum_staff.set_voice_position(voice, position)

    def _open_settings_dialog(self):
        self.settings_dialog.exec_()

    def _open_practice_dialog(self):
        self.practice_dialog.exec_()

    def _open_groove_practice_dialog(self):
        self._refresh_groove_practice_presets()
        self._refresh_groove_practice_options()
        self._update_groove_practice_status()
        self._update_groove_practice_button()
        self._update_groove_practice_totals()
        self.groove_practice_dialog.exec_()

    def _open_groove_dialog(self):
        self.groove_dialog.exec_()

    def _open_midi_dialog(self):
        self.midi_dialog.exec_()

    def _update_groove_label(self, name: str):
        label_text = name or "None"
        if hasattr(self, "lbl_groove_current"):
            self.lbl_groove_current.setText(label_text)
        if hasattr(self, "lbl_groove_name"):
            self.lbl_groove_name.setText(label_text)

    def _selected_groove_practice_row(self) -> int:
        if not hasattr(self, "groove_practice_table"):
            return -1
        selection = self.groove_practice_table.selectionModel().selectedRows()
        if not selection:
            return -1
        return selection[0].row()

    def _add_groove_practice_row(
        self,
        groove_name: str = None,
        bpm: int = None,
        minutes: float = None,
        loop_count: int = None,
        click_subdiv: int = None,
        mute_on: int = None,
        mute_off: int = None,
    ):
        if not hasattr(self, "groove_practice_table"):
            return
        row = self.groove_practice_table.rowCount()
        self.groove_practice_table.insertRow(row)

        combo = QComboBox()
        groove_names = self.groove_library.get_groove_names()
        if groove_names:
            combo.addItems(groove_names)
        else:
            combo.addItem("(no grooves)")
            combo.setEnabled(False)
        if groove_name:
            idx = combo.findText(groove_name)
        else:
            idx = combo.findText(self.groove_combo.currentText())
        if idx >= 0:
            combo.setCurrentIndex(idx)
        self.groove_practice_table.setCellWidget(row, 0, combo)

        bpm_spin = QSpinBox()
        bpm_spin.setRange(20, 400)
        bpm_spin.setValue(int(bpm) if bpm is not None else int(self.bpm_spin.value()))
        self.groove_practice_table.setCellWidget(row, 1, bpm_spin)

        minutes_spin = QDoubleSpinBox()
        minutes_spin.setRange(0.1, 240.0)
        minutes_spin.setDecimals(1)
        minutes_spin.setSingleStep(0.5)
        minutes_spin.setValue(float(minutes) if minutes is not None else 5.0)
        self.groove_practice_table.setCellWidget(row, 2, minutes_spin)

        loop_spin = QSpinBox()
        loop_spin.setRange(0, 999)
        loop_spin.setValue(int(loop_count) if loop_count is not None else self.groove_loop_spin.value())
        self.groove_practice_table.setCellWidget(row, 3, loop_spin)

        click_spin = QSpinBox()
        click_spin.setRange(1, 12)
        click_spin.setValue(int(click_subdiv) if click_subdiv is not None else self.click_subdiv_spin.value())
        self.groove_practice_table.setCellWidget(row, 4, click_spin)

        mute_on_spin = QSpinBox()
        mute_on_spin.setRange(1, 64)
        mute_on_spin.setValue(int(mute_on) if mute_on is not None else self.mute_on_spin.value())
        self.groove_practice_table.setCellWidget(row, 5, mute_on_spin)

        mute_off_spin = QSpinBox()
        mute_off_spin.setRange(0, 64)
        mute_off_spin.setSpecialValueText("Disabled")
        mute_off_spin.setValue(int(mute_off) if mute_off is not None else self.mute_off_spin.value())
        self.groove_practice_table.setCellWidget(row, 6, mute_off_spin)

        combo.currentIndexChanged.connect(lambda _: self._update_groove_practice_totals())
        bpm_spin.valueChanged.connect(lambda _: self._update_groove_practice_totals())
        minutes_spin.valueChanged.connect(lambda _: self._update_groove_practice_totals())
        loop_spin.valueChanged.connect(lambda _: self._update_groove_practice_totals())
        click_spin.valueChanged.connect(lambda _: self._update_groove_practice_totals())
        mute_on_spin.valueChanged.connect(lambda _: self._update_groove_practice_totals())
        mute_off_spin.valueChanged.connect(lambda _: self._update_groove_practice_totals())
        self._update_groove_practice_totals()

    def _remove_groove_practice_row(self):
        if not hasattr(self, "groove_practice_table"):
            return
        row = self._selected_groove_practice_row()
        if row >= 0:
            self.groove_practice_table.removeRow(row)
            self._update_groove_practice_totals()

    def _move_groove_practice_row(self, offset: int):
        if not hasattr(self, "groove_practice_table"):
            return
        row = self._selected_groove_practice_row()
        if row < 0:
            return
        items = self._get_groove_practice_items()
        new_row = row + int(offset)
        if new_row < 0 or new_row >= len(items):
            return
        items[row], items[new_row] = items[new_row], items[row]
        self._set_groove_practice_items(items)
        self.groove_practice_table.selectRow(new_row)
        self._update_groove_practice_totals()

    def _get_groove_practice_items(self):
        items = []
        if not hasattr(self, "groove_practice_table"):
            return items
        for row in range(self.groove_practice_table.rowCount()):
            combo = self.groove_practice_table.cellWidget(row, 0)
            bpm_spin = self.groove_practice_table.cellWidget(row, 1)
            minutes_spin = self.groove_practice_table.cellWidget(row, 2)
            loop_spin = self.groove_practice_table.cellWidget(row, 3)
            click_spin = self.groove_practice_table.cellWidget(row, 4)
            mute_on_spin = self.groove_practice_table.cellWidget(row, 5)
            mute_off_spin = self.groove_practice_table.cellWidget(row, 6)
            if not combo or not bpm_spin or not minutes_spin:
                continue
            groove_name = combo.currentText()
            if not groove_name or groove_name == "(no grooves)":
                continue
            items.append({
                "groove": groove_name,
                "bpm": int(bpm_spin.value()),
                "minutes": float(minutes_spin.value()),
                "loop_count": int(loop_spin.value()) if loop_spin else 0,
                "click_subdiv": int(click_spin.value()) if click_spin else self.click_subdiv_spin.value(),
                "mute_on": int(mute_on_spin.value()) if mute_on_spin else self.mute_on_spin.value(),
                "mute_off": int(mute_off_spin.value()) if mute_off_spin else self.mute_off_spin.value(),
            })
        return items

    def _set_groove_practice_items(self, items):
        if not hasattr(self, "groove_practice_table"):
            return
        self.groove_practice_table.setRowCount(0)
        for item in items or []:
            groove_name = item.get("groove") if isinstance(item, dict) else None
            bpm = item.get("bpm") if isinstance(item, dict) else None
            minutes = item.get("minutes") if isinstance(item, dict) else None
            loop_count = item.get("loop_count") if isinstance(item, dict) else None
            click_subdiv = item.get("click_subdiv") if isinstance(item, dict) else None
            mute_on = item.get("mute_on") if isinstance(item, dict) else None
            mute_off = item.get("mute_off") if isinstance(item, dict) else None
            self._add_groove_practice_row(
                groove_name, bpm, minutes, loop_count, click_subdiv, mute_on, mute_off
            )
        self._update_groove_practice_totals()

    def _refresh_groove_practice_options(self):
        if not hasattr(self, "groove_practice_table"):
            return
        groove_names = self.groove_library.get_groove_names()
        for row in range(self.groove_practice_table.rowCount()):
            combo = self.groove_practice_table.cellWidget(row, 0)
            if not isinstance(combo, QComboBox):
                continue
            current = combo.currentText()
            combo.blockSignals(True)
            combo.clear()
            if groove_names:
                combo.addItems(groove_names)
                idx = combo.findText(current)
                if idx >= 0:
                    combo.setCurrentIndex(idx)
            else:
                combo.addItem("(no grooves)")
                combo.setEnabled(False)
            combo.blockSignals(False)

    def _update_groove_practice_button(self):
        if hasattr(self, "btn_groove_practice_start"):
            label = "Stop Routine" if self._groove_practice_running else "Start Routine"
            self.btn_groove_practice_start.setText(label)
        if hasattr(self, "btn_groove_practice_prev"):
            enable_prev = self._groove_practice_running and self._groove_practice_order_pos > 0
            self.btn_groove_practice_prev.setEnabled(enable_prev)
        if hasattr(self, "btn_groove_practice_restart"):
            self.btn_groove_practice_restart.setEnabled(self._groove_practice_running)
        if hasattr(self, "btn_groove_practice_skip"):
            enable_skip = self._groove_practice_running and self._has_groove_practice_next()
            self.btn_groove_practice_skip.setEnabled(enable_skip)

    def _set_groove_practice_controls_enabled(self, enabled: bool):
        if hasattr(self, "groove_practice_table"):
            self.groove_practice_table.setEnabled(enabled)
        if hasattr(self, "btn_groove_practice_add"):
            self.btn_groove_practice_add.setEnabled(enabled)
        if hasattr(self, "btn_groove_practice_remove"):
            self.btn_groove_practice_remove.setEnabled(enabled)
        if hasattr(self, "btn_groove_practice_up"):
            self.btn_groove_practice_up.setEnabled(enabled)
        if hasattr(self, "btn_groove_practice_down"):
            self.btn_groove_practice_down.setEnabled(enabled)
        if hasattr(self, "groove_practice_preset_combo"):
            self.groove_practice_preset_combo.setEnabled(enabled)
        if hasattr(self, "btn_groove_practice_new"):
            self.btn_groove_practice_new.setEnabled(enabled)
        if hasattr(self, "btn_groove_practice_save"):
            self.btn_groove_practice_save.setEnabled(enabled)
        if hasattr(self, "btn_groove_practice_save_as"):
            self.btn_groove_practice_save_as.setEnabled(enabled)
        if hasattr(self, "btn_groove_practice_delete"):
            self.btn_groove_practice_delete.setEnabled(enabled)
        if hasattr(self, "btn_groove_practice_import"):
            self.btn_groove_practice_import.setEnabled(enabled)
        if hasattr(self, "btn_groove_practice_export"):
            self.btn_groove_practice_export.setEnabled(enabled)
        if hasattr(self, "groove_practice_count_in"):
            self.groove_practice_count_in.setEnabled(enabled)
        if hasattr(self, "groove_practice_rest"):
            self.groove_practice_rest.setEnabled(enabled)
        if hasattr(self, "chk_groove_practice_shuffle"):
            self.chk_groove_practice_shuffle.setEnabled(enabled)
        if hasattr(self, "chk_groove_practice_loop"):
            self.chk_groove_practice_loop.setEnabled(enabled)

    def _update_groove_practice_status(self):
        if not hasattr(self, "lbl_groove_practice_current"):
            return
        if not self._groove_practice_running or self._groove_practice_index < 0:
            self.lbl_groove_practice_current.setText("Ready")
            self.lbl_groove_practice_next.setText("Next: --")
            if hasattr(self, "lbl_groove_practice_remaining"):
                self.lbl_groove_practice_remaining.setText("Remaining: --")
            return
        if self._groove_practice_index >= len(self._groove_practice_items):
            self.lbl_groove_practice_current.setText("Finished")
            self.lbl_groove_practice_next.setText("Next: --")
            if hasattr(self, "lbl_groove_practice_remaining"):
                self.lbl_groove_practice_remaining.setText("Remaining: --")
            return
        current = self._groove_practice_items[self._groove_practice_index]
        groove = current.get("groove", "None")
        bpm = current.get("bpm", self.bpm_spin.value())
        minutes = current.get("minutes", 0)
        self.lbl_groove_practice_current.setText(f"{groove} @ {bpm} BPM ({minutes:.1f} min)")
        next_item = None
        if self._groove_practice_order and self._groove_practice_order_pos >= 0:
            next_pos = self._groove_practice_order_pos + 1
            if next_pos < len(self._groove_practice_order):
                next_idx = self._groove_practice_order[next_pos]
                if 0 <= next_idx < len(self._groove_practice_items):
                    next_item = self._groove_practice_items[next_idx]
            elif self._groove_practice_loop and self._groove_practice_order:
                next_idx = self._groove_practice_order[0]
                if 0 <= next_idx < len(self._groove_practice_items):
                    next_item = self._groove_practice_items[next_idx]
        if next_item:
            next_text = f"Next: {next_item.get('groove', 'None')} @ {next_item.get('bpm', '')} BPM"
        else:
            next_text = "Next: Finish"
        self.lbl_groove_practice_next.setText(next_text)
        self._update_groove_practice_remaining_label()
        self._update_groove_practice_button()

    def _format_duration(self, seconds: float) -> str:
        total = max(0, int(round(seconds)))
        hours = total // 3600
        minutes = (total % 3600) // 60
        secs = total % 60
        if hours > 0:
            return f"{hours}:{minutes:02d}:{secs:02d}"
        return f"{minutes:02d}:{secs:02d}"

    def _update_groove_practice_remaining_label(self):
        if not hasattr(self, "lbl_groove_practice_remaining"):
            return
        if not self._groove_practice_running or self._groove_practice_index < 0:
            self.lbl_groove_practice_remaining.setText("Remaining: --")
            return
        phase = self._groove_practice_phase or "play"
        if phase == "count_in":
            bars = max(0, int(self._groove_practice_count_in_remaining))
            self.lbl_groove_practice_remaining.setText(f"Count-in: {bars} bars")
            return
        remaining_ms = self._groove_practice_remaining_ms()
        if remaining_ms is None:
            self.lbl_groove_practice_remaining.setText("Remaining: --")
            return
        remaining_text = self._format_duration(remaining_ms / 1000.0)
        if phase == "rest":
            self.lbl_groove_practice_remaining.setText(f"Rest: {remaining_text}")
        else:
            self.lbl_groove_practice_remaining.setText(f"Remaining: {remaining_text}")

    def _update_practice_total_label(self, total_ms: int, options: dict = None):
        text = "Routine: --"
        if total_ms and total_ms > 0:
            total_text = self._format_duration(total_ms / 1000.0)
            suffix = ""
            if options and options.get("loop"):
                suffix = " (loop)"
            text = f"Routine: {total_text}{suffix}"
        if hasattr(self, "lbl_practice_total"):
            self.lbl_practice_total.setText(text)
        if hasattr(self, "lbl_groove_practice_total"):
            if total_ms and total_ms > 0:
                self.lbl_groove_practice_total.setText(f"Total: {self._format_duration(total_ms / 1000.0)}")
            else:
                self.lbl_groove_practice_total.setText("Total: --")

    def _collect_groove_practice_options(self) -> dict:
        return {
            "count_in_bars": int(self.groove_practice_count_in.value()),
            "rest_seconds": float(self.groove_practice_rest.value()),
            "shuffle": self.chk_groove_practice_shuffle.isChecked(),
            "loop": self.chk_groove_practice_loop.isChecked(),
        }

    def _apply_groove_practice_options(self, options: dict):
        if not options:
            return
        self.groove_practice_count_in.setValue(
            self._coerce_int(options.get("count_in_bars"), self.groove_practice_count_in.value())
        )
        self.groove_practice_rest.setValue(
            self._coerce_float(options.get("rest_seconds"), self.groove_practice_rest.value())
        )
        self.chk_groove_practice_shuffle.setChecked(
            self._coerce_bool(options.get("shuffle"), self.chk_groove_practice_shuffle.isChecked())
        )
        self.chk_groove_practice_loop.setChecked(
            self._coerce_bool(options.get("loop"), self.chk_groove_practice_loop.isChecked())
        )

    def _estimate_groove_practice_total_ms(self, items, options: dict) -> int:
        if not items:
            return 0
        count_in_bars = int(options.get("count_in_bars", 0)) if options else 0
        rest_seconds = float(options.get("rest_seconds", 0.0)) if options else 0.0
        total_ms = 0.0
        for item in items:
            minutes = float(item.get("minutes", 0.0))
            total_ms += minutes * 60_000.0
            if count_in_bars > 0:
                bpm = max(1, int(item.get("bpm", self.bpm_spin.value())))
                groove_name = item.get("groove")
                beats = self.beats_spin.value()
                groove = self.groove_library.get_groove_by_name(groove_name) if groove_name else None
                if groove:
                    beats = groove.beats_per_bar
                bar_ms = (60_000.0 / bpm) * max(1, int(beats))
                total_ms += bar_ms * count_in_bars
        if len(items) > 1 and rest_seconds > 0:
            total_ms += (len(items) - 1) * rest_seconds * 1000.0
        return max(0, int(round(total_ms)))

    def _update_groove_practice_totals(self):
        items = self._get_groove_practice_items()
        options = self._collect_groove_practice_options()
        estimated_ms = self._estimate_groove_practice_total_ms(items, options)
        if not self._groove_practice_running:
            self._groove_practice_total_ms = estimated_ms
        self._update_practice_total_label(estimated_ms, options)

    def _refresh_groove_practice_presets(self):
        if not hasattr(self, "groove_practice_preset_combo"):
            return
        names = sorted(self._groove_practice_presets.keys())
        self.groove_practice_preset_combo.blockSignals(True)
        self.groove_practice_preset_combo.clear()
        self.groove_practice_preset_combo.addItem("(unsaved)")
        for name in names:
            self.groove_practice_preset_combo.addItem(name)
        if self._groove_practice_active_name in self._groove_practice_presets:
            idx = self.groove_practice_preset_combo.findText(self._groove_practice_active_name)
            if idx >= 0:
                self.groove_practice_preset_combo.setCurrentIndex(idx)
        else:
            self.groove_practice_preset_combo.setCurrentIndex(0)
        self.groove_practice_preset_combo.blockSignals(False)

    def _on_groove_practice_preset_selected(self, name: str):
        if not name or name == "(unsaved)":
            self._groove_practice_active_name = ""
            return
        preset = self._groove_practice_presets.get(name)
        if not preset:
            return
        self._load_groove_practice_preset(name, preset)

    def _load_groove_practice_preset(self, name: str, preset: dict):
        items = preset.get("items", []) if isinstance(preset, dict) else []
        options = preset.get("options", {}) if isinstance(preset, dict) else {}
        self._groove_practice_active_name = name
        self._set_groove_practice_items(items)
        self._apply_groove_practice_options(options)
        self._update_groove_practice_totals()

    def _new_groove_practice_preset(self):
        self._groove_practice_active_name = ""
        self._set_groove_practice_items([])
        self._apply_groove_practice_options({
            "count_in_bars": 0,
            "rest_seconds": 0.0,
            "shuffle": False,
            "loop": False,
        })
        self._refresh_groove_practice_presets()
        self._update_groove_practice_totals()

    def _prompt_groove_practice_name(self, title: str, default: str = "") -> str:
        text, ok = QInputDialog.getText(self, title, "Routine name:", text=default)
        if not ok:
            return ""
        return text.strip()

    def _save_groove_practice_preset(self):
        name = self._groove_practice_active_name
        if not name or name not in self._groove_practice_presets:
            name = self._prompt_groove_practice_name("Save Routine", name or "New Routine")
        if not name:
            return
        items = self._get_groove_practice_items()
        options = self._collect_groove_practice_options()
        self._groove_practice_presets[name] = {"items": items, "options": options}
        self._groove_practice_active_name = name
        self._refresh_groove_practice_presets()
        self.info.setText(f"Saved routine: {name}")

    def _save_groove_practice_preset_as(self):
        name = self._prompt_groove_practice_name("Save Routine As", self._groove_practice_active_name or "New Routine")
        if not name:
            return
        items = self._get_groove_practice_items()
        options = self._collect_groove_practice_options()
        self._groove_practice_presets[name] = {"items": items, "options": options}
        self._groove_practice_active_name = name
        self._refresh_groove_practice_presets()
        self.info.setText(f"Saved routine: {name}")

    def _delete_groove_practice_preset(self):
        name = self._groove_practice_active_name
        if not name or name not in self._groove_practice_presets:
            return
        reply = QMessageBox.question(
            self,
            "Delete Routine",
            f"Delete routine '{name}'?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return
        self._groove_practice_presets.pop(name, None)
        self._groove_practice_active_name = ""
        self._refresh_groove_practice_presets()
        self.info.setText(f"Deleted routine: {name}")

    def _unique_groove_practice_name(self, base: str) -> str:
        candidate = base.strip() or "Imported Routine"
        if candidate not in self._groove_practice_presets:
            return candidate
        idx = 2
        while True:
            name = f"{candidate} ({idx})"
            if name not in self._groove_practice_presets:
                return name
            idx += 1

    def _import_groove_practice_preset(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Import Routine",
            str(Path.home()),
            "JSON Files (*.json)",
        )
        if not path:
            return
        try:
            with open(path, "r") as f:
                data = json.load(f)
        except Exception as exc:
            QMessageBox.warning(self, "Import Failed", f"Could not read file:\n{exc}")
            return
        routines = []
        if isinstance(data, dict) and "routines" in data:
            routines = data.get("routines", [])
        elif isinstance(data, dict) and data.get("name") and data.get("items") is not None:
            routines = [data]
        elif isinstance(data, list):
            routines = data
        imported_any = False
        for routine in routines:
            if not isinstance(routine, dict):
                continue
            name = str(routine.get("name", "")).strip()
            items = routine.get("items", [])
            options = routine.get("options", {})
            if not name:
                name = "Imported Routine"
            name = self._unique_groove_practice_name(name)
            if not isinstance(items, list):
                items = []
            if not isinstance(options, dict):
                options = {}
            self._groove_practice_presets[name] = {"items": items, "options": options}
            imported_any = True
        if not imported_any:
            QMessageBox.warning(self, "Import Failed", "No valid routines found.")
            return
        self._refresh_groove_practice_presets()
        self.info.setText("Imported routine(s)")

    def _export_groove_practice_preset(self):
        name = self._groove_practice_active_name or "Routine"
        items = self._get_groove_practice_items()
        options = self._collect_groove_practice_options()
        if not items:
            QMessageBox.information(self, "Export Routine", "No groove items to export.")
            return
        if not self._groove_practice_active_name:
            name = self._prompt_groove_practice_name("Export Routine", name)
            if not name:
                return
        filename = "".join(c for c in name if c.isalnum() or c in (" ", "_", "-")).rstrip()
        if not filename:
            filename = "routine"
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Export Routine",
            str(Path.home() / f"{filename}.json"),
            "JSON Files (*.json)",
        )
        if not path:
            return
        payload = {"name": name, "items": items, "options": options}
        try:
            with open(path, "w") as f:
                json.dump(payload, f, indent=2)
        except Exception as exc:
            QMessageBox.warning(self, "Export Failed", f"Could not write file:\n{exc}")
            return
        self.info.setText(f"Exported routine: {name}")
    def _groove_practice_elapsed_ms(self):
        if (
            not self._groove_practice_running
            or self._groove_practice_index < 0
            or not self._groove_practice_phase
        ):
            return None
        if hasattr(self._groove_practice_elapsed, "isValid") and not self._groove_practice_elapsed.isValid():
            return 0
        if self._groove_practice_pause_started is None:
            elapsed = self._groove_practice_elapsed.elapsed() - self._groove_practice_paused_ms
        else:
            elapsed = self._groove_practice_pause_started - self._groove_practice_paused_ms
        return max(0, int(elapsed))

    def _groove_practice_remaining_ms(self):
        elapsed = self._groove_practice_elapsed_ms()
        if elapsed is None:
            return None
        remaining = int(self._groove_practice_target_ms) - elapsed
        return max(0, int(remaining))

    def _toggle_groove_practice(self):
        if self._groove_practice_running:
            self._stop_groove_practice()
        else:
            self._start_groove_practice()

    def _start_groove_practice(self):
        items = self._get_groove_practice_items()
        if not items:
            self.info.setText("Groove routine: add at least one groove.")
            return
        options = self._collect_groove_practice_options()
        self._groove_practice_items = items
        self._groove_practice_running = True
        self._groove_practice_shuffle = options.get("shuffle", False)
        self._groove_practice_loop = options.get("loop", False)
        self._groove_practice_count_in_bars = int(options.get("count_in_bars", 0))
        self._groove_practice_rest_seconds = float(options.get("rest_seconds", 0.0))
        self._groove_practice_completed_ms = 0
        self._groove_practice_phase = None
        self._groove_practice_current_count_in_ms = 0
        self._groove_practice_current_play_ms = 0
        self._groove_practice_current_rest_ms = 0
        self._groove_practice_total_ms = self._estimate_groove_practice_total_ms(items, options)
        self._groove_practice_order = list(range(len(items)))
        if self._groove_practice_shuffle:
            random.shuffle(self._groove_practice_order)
        self._groove_practice_order_pos = 0
        self._groove_practice_index = self._groove_practice_order[0]
        self._groove_practice_paused_ms = 0
        self._groove_practice_pause_started = None
        self._start_groove_practice_item(self._groove_practice_index)
        self._set_groove_practice_controls_enabled(False)
        self._update_groove_practice_button()
        self._update_groove_practice_totals()
        self._update_practice_progress()

    def _stop_groove_practice(self):
        self._groove_practice_running = False
        self._groove_practice_index = -1
        self._groove_practice_items = []
        self._groove_practice_order = []
        self._groove_practice_order_pos = -1
        self._groove_practice_phase = None
        self._groove_practice_target_ms = 0
        self._groove_practice_pause_started = None
        self._groove_practice_paused_ms = 0
        self._groove_practice_count_in_remaining = 0
        self._groove_practice_completed_ms = 0
        self._groove_practice_current_count_in_ms = 0
        self._groove_practice_current_play_ms = 0
        self._groove_practice_current_rest_ms = 0
        if hasattr(self._groove_practice_elapsed, "invalidate"):
            self._groove_practice_elapsed.invalidate()
        self.sig_groove_stop.emit()
        self._set_groove_practice_controls_enabled(True)
        self._update_groove_practice_button()
        self._update_groove_practice_status()
        self._update_workout_display()
        self._update_practice_progress()
        self.info.setText("Groove routine stopped")

    def _start_groove_practice_item(self, index: int):
        if index < 0 or index >= len(self._groove_practice_items):
            return
        item = self._groove_practice_items[index]
        self._apply_groove_practice_item_settings(item)
        self._groove_practice_current_play_ms = max(
            100, int(round(float(item.get("minutes", 1.0)) * 60_000))
        )
        self._groove_practice_current_count_in_ms = self._groove_practice_count_in_target_ms(item)
        if self._groove_practice_count_in_bars > 0:
            self._start_groove_practice_phase("count_in", self._groove_practice_current_count_in_ms)
        else:
            self._begin_groove_practice_play(item)
        self._update_groove_practice_status()
        self._update_workout_display()

    def _apply_groove_practice_item_settings(self, item: dict):
        groove_name = item.get("groove") if isinstance(item, dict) else None
        bpm = item.get("bpm") if isinstance(item, dict) else None
        loop_count = item.get("loop_count") if isinstance(item, dict) else None
        click_subdiv = item.get("click_subdiv") if isinstance(item, dict) else None
        mute_on = item.get("mute_on") if isinstance(item, dict) else None
        mute_off = item.get("mute_off") if isinstance(item, dict) else None
        if groove_name:
            self._set_combo_text(self.groove_combo, groove_name)
        if bpm is not None:
            self.bpm_spin.setValue(int(bpm))
        if loop_count is not None:
            self.groove_loop_spin.setValue(int(loop_count))
        if click_subdiv is not None:
            self.click_subdiv_spin.setValue(int(click_subdiv))
        if mute_on is not None:
            self.mute_on_spin.setValue(int(mute_on))
        if mute_off is not None:
            self.mute_off_spin.setValue(int(mute_off))

    def _groove_practice_count_in_target_ms(self, item: dict) -> int:
        if self._groove_practice_count_in_bars <= 0:
            return 0
        bpm = max(1, int(item.get("bpm", self.bpm_spin.value())))
        groove_name = item.get("groove")
        beats = self.beats_spin.value()
        groove = self.groove_library.get_groove_by_name(groove_name) if groove_name else None
        if groove:
            beats = groove.beats_per_bar
        bar_ms = (60_000.0 / bpm) * max(1, int(beats))
        return max(0, int(round(bar_ms * self._groove_practice_count_in_bars)))

    def _start_groove_practice_phase(self, phase: str, target_ms: int):
        self._groove_practice_phase = phase
        self._groove_practice_target_ms = max(0, int(target_ms))
        self._groove_practice_elapsed.start()
        self._groove_practice_paused_ms = 0
        self._groove_practice_pause_started = None
        if phase == "count_in":
            self._groove_practice_count_in_remaining = int(self._groove_practice_count_in_bars)
            self.sig_groove_stop.emit()
            if not self._running_state:
                self.sig_start.emit()
        elif phase == "rest":
            self.sig_groove_stop.emit()

    def _begin_groove_practice_play(self, item: dict):
        self._start_groove_practice_phase("play", self._groove_practice_current_play_ms)
        if not self._running_state:
            self.sig_start.emit()
        if item.get("groove"):
            self.sig_groove_stop.emit()
            self.sig_groove_start.emit()
        groove_name = item.get("groove", "Groove")
        self.info.setText(f"Routine: {groove_name} @ {self.bpm_spin.value()} BPM")
        self._update_groove_practice_status()

    def _check_groove_practice_advance(self):
        if not self._groove_practice_running:
            return
        if self._groove_practice_index < 0:
            return
        if self._groove_practice_pause_started is not None:
            return
        phase = self._groove_practice_phase
        if phase not in ("play", "rest"):
            return
        remaining_ms = self._groove_practice_remaining_ms()
        if remaining_ms is None:
            return
        if remaining_ms > 0:
            return
        if phase == "play":
            self._groove_practice_completed_ms += int(self._groove_practice_current_play_ms)
            if self._should_start_groove_practice_rest():
                self._groove_practice_current_rest_ms = int(round(self._groove_practice_rest_seconds * 1000))
                self._start_groove_practice_phase("rest", self._groove_practice_current_rest_ms)
            else:
                self._advance_groove_practice()
        elif phase == "rest":
            self._groove_practice_completed_ms += int(self._groove_practice_current_rest_ms)
            self._advance_groove_practice()
        self._update_groove_practice_status()
        self._update_workout_display()
        self._update_practice_progress()

    def _advance_groove_practice(self):
        if not self._groove_practice_order:
            return
        next_pos = self._groove_practice_order_pos + 1
        if next_pos >= len(self._groove_practice_order):
            if self._groove_practice_loop:
                if self._groove_practice_shuffle:
                    random.shuffle(self._groove_practice_order)
                next_pos = 0
                self._groove_practice_completed_ms = 0
            else:
                self._finish_groove_practice()
                return
        self._groove_practice_order_pos = next_pos
        self._groove_practice_index = self._groove_practice_order[next_pos]
        self._groove_practice_phase = None
        self._groove_practice_current_count_in_ms = 0
        self._groove_practice_current_play_ms = 0
        self._groove_practice_current_rest_ms = 0
        self._recalculate_groove_practice_completed_ms()
        self._start_groove_practice_item(self._groove_practice_index)

    def _finish_groove_practice(self):
        self._groove_practice_running = False
        self._groove_practice_index = -1
        self._groove_practice_order_pos = -1
        self._groove_practice_phase = None
        self._groove_practice_target_ms = 0
        self._groove_practice_pause_started = None
        self._groove_practice_paused_ms = 0
        self._groove_practice_count_in_remaining = 0
        self._groove_practice_completed_ms = 0
        self._groove_practice_current_count_in_ms = 0
        self._groove_practice_current_play_ms = 0
        self._groove_practice_current_rest_ms = 0
        self.sig_groove_stop.emit()
        self._update_groove_practice_button()
        self._set_groove_practice_controls_enabled(True)
        self._update_groove_practice_status()
        self._update_workout_display()
        self._update_practice_progress()
        self.info.setText("Groove routine finished")

    def _should_start_groove_practice_rest(self) -> bool:
        if self._groove_practice_rest_seconds <= 0:
            return False
        if self._groove_practice_order_pos + 1 < len(self._groove_practice_order):
            return True
        return bool(self._groove_practice_loop)

    def _has_groove_practice_next(self) -> bool:
        if not self._groove_practice_order:
            return False
        if self._groove_practice_order_pos + 1 < len(self._groove_practice_order):
            return True
        return bool(self._groove_practice_loop)

    def _groove_practice_item_total_ms(self, item: dict) -> int:
        play_ms = max(0, int(round(float(item.get("minutes", 0.0)) * 60_000)))
        count_in_ms = self._groove_practice_count_in_target_ms(item)
        return play_ms + count_in_ms

    def _recalculate_groove_practice_completed_ms(self):
        completed = 0
        if not self._groove_practice_order:
            self._groove_practice_completed_ms = 0
            return
        rest_ms = int(round(self._groove_practice_rest_seconds * 1000))
        for pos in range(max(0, self._groove_practice_order_pos)):
            idx = self._groove_practice_order[pos]
            if 0 <= idx < len(self._groove_practice_items):
                completed += self._groove_practice_item_total_ms(self._groove_practice_items[idx])
                if rest_ms > 0:
                    completed += rest_ms
        if self._groove_practice_phase in ("play", "rest") and self._groove_practice_current_count_in_ms:
            completed += int(self._groove_practice_current_count_in_ms)
        if self._groove_practice_phase == "rest" and self._groove_practice_current_play_ms:
            completed += int(self._groove_practice_current_play_ms)
        self._groove_practice_completed_ms = completed

    def _update_practice_progress(self):
        if not hasattr(self, "practice_progress"):
            return
        if not self._groove_practice_running or self._groove_practice_total_ms <= 0:
            self.practice_progress.setValue(0)
            self.practice_progress.setFormat("Practice Inactive")
            return
        elapsed_phase = self._groove_practice_elapsed_ms() or 0
        phase_target = max(1, int(self._groove_practice_target_ms or 1))
        phase_elapsed = min(elapsed_phase, phase_target)
        progress_ms = max(0, int(self._groove_practice_completed_ms + phase_elapsed))
        total_ms = max(1, int(self._groove_practice_total_ms))
        percent = int(round((progress_ms / total_ms) * 100))
        percent = max(0, min(100, percent))
        self.practice_progress.setValue(percent)
        self.practice_progress.setFormat(f"Practice {percent}%")

    def _skip_groove_practice(self):
        if not self._groove_practice_running:
            return
        self._advance_groove_practice()

    def _previous_groove_practice(self):
        if not self._groove_practice_running:
            return
        if self._groove_practice_order_pos <= 0:
            return
        self._groove_practice_order_pos -= 1
        self._groove_practice_index = self._groove_practice_order[self._groove_practice_order_pos]
        self._groove_practice_phase = None
        self._groove_practice_current_count_in_ms = 0
        self._groove_practice_current_play_ms = 0
        self._groove_practice_current_rest_ms = 0
        self._recalculate_groove_practice_completed_ms()
        self._start_groove_practice_item(self._groove_practice_index)

    def _restart_groove_practice(self):
        if not self._groove_practice_running:
            return
        if self._groove_practice_order_pos < 0:
            return
        self._groove_practice_phase = None
        self._groove_practice_current_count_in_ms = 0
        self._groove_practice_current_play_ms = 0
        self._groove_practice_current_rest_ms = 0
        self._recalculate_groove_practice_completed_ms()
        self._start_groove_practice_item(self._groove_practice_index)

    # Slots / handlers
    def _sync_metronome_to_groove(self, groove: DrumGroove):
        if self.beats_spin.value() != groove.beats_per_bar:
            self.beats_spin.setValue(groove.beats_per_bar)
        if self.subdiv_spin.value() != groove.subdivision:
            self.subdiv_spin.setValue(groove.subdivision)

    def _configure_selected_groove(self, groove_name=None):
        name = groove_name or self.groove_combo.currentText()
        if not name:
            return None
        groove = self.groove_library.get_groove_by_name(name)
        if not groove:
            return None
        self._set_groove_bars(groove)
        self._sync_metronome_to_groove(groove)
        self.sig_groove_set.emit(name)
        self.sig_groove_loop.emit(self.groove_loop_spin.value())
        return groove

    def _on_staff_subdivision_changed(self, value: int):
        was_synced = self.click_subdiv_spin.value() == self._last_staff_subdiv
        self.engine.set_subdivision(value)
        self.click_subdiv_spin.setMaximum(value)
        if was_synced:
            self.click_subdiv_spin.setValue(value)
        elif self.click_subdiv_spin.value() > value:
            self.click_subdiv_spin.setValue(value)
        self._last_staff_subdiv = value
        self._on_meter_changed(value)

    def _on_meter_changed(self, value: int):
        self._reset_loop_tracking()
        self.drum_staff.reset_position()

    def _reset_loop_tracking(self):
        self._bar_index = 0
        self._groove_toggle_base_bar = 0
        self._metronome_toggle_base_bar = 0

    def _set_groove_bars(self, groove: DrumGroove):
        bars = 1
        if groove is not None:
            try:
                bars = max(1, int(groove.bars))
            except (TypeError, ValueError):
                bars = 1
        self._groove_bars = bars
        self._groove_toggle_base_bar = self._bar_index
        self._metronome_toggle_base_bar = self._bar_index

    def _current_loop_base(self) -> int:
        bars = max(1, self._groove_bars)
        return self._bar_index - (self._bar_index % bars)

    def _loop_index_from_base(self, base_bar: int) -> int:
        bars = max(1, self._groove_bars)
        bar_offset = self._bar_index - base_bar
        if bar_offset < 0:
            bar_offset = 0
        return bar_offset // bars

    def _toggle_loop_allows_output(self, base_bar: int) -> bool:
        return (self._loop_index_from_base(base_bar) % 2) == 0

    def _allow_groove_midi_output(self) -> bool:
        if not self.chk_toggle_groove_silence.isChecked():
            return True
        return self._toggle_loop_allows_output(self._groove_toggle_base_bar)

    def _allow_metronome_clicks(self) -> bool:
        if not self.chk_toggle_metronome_silence.isChecked():
            return True
        return self._toggle_loop_allows_output(self._metronome_toggle_base_bar)

    def _on_toggle_groove_silence(self, enabled: bool):
        if enabled:
            self._groove_toggle_base_bar = self._current_loop_base()

    def _on_toggle_metronome_silence(self, enabled: bool):
        if enabled:
            self._metronome_toggle_base_bar = self._current_loop_base()

    def _on_engine_click(self, accent: bool):
        if not self._allow_metronome_clicks():
            return
        self.sig_audio_play.emit(accent)

    def _on_groove_notes(self, notes):
        if not notes:
            return
        if not self._allow_groove_midi_output():
            return
        self.sig_groove_midi.emit(notes)

    def _on_tick(self, step_idx: int, beat_idx: int, is_beat: bool, is_accent: bool):
        # Audio is handled by worker thread now.
        # Update visual on beats
        if is_beat:
            self.indicator.set_current(beat_idx, True, is_accent)
            if self._ladder_warning_active:
                bpm = max(1, int(self._current_bpm))
                duration_ms = int(round(60000 / bpm))
                self.drum_staff.trigger_ladder_pulse(duration_ms)
        else:
            # turn off flash between steps
            self.indicator.set_current(self.indicator.current_beat, False)
        if self._ladder_running:
            self._update_ladder_progress(step_idx)

    def _on_bar_advanced(self, bar_idx: int):
        self._bar_index += 1
        if self._ladder_running:
            if self._ladder_bars_per_step <= 0:
                self._ladder_bars_per_step = max(1, int(self.r_bars.value()))
            self._ladder_bar_counter += 1
            if self._ladder_bar_counter >= self._ladder_bars_per_step:
                self._ladder_bar_counter = 0
            self._update_ladder_warning()
            self._update_ladder_progress(0)
        if self._groove_practice_running:
            if self._groove_practice_phase == "count_in":
                self._groove_practice_count_in_remaining -= 1
                if self._groove_practice_count_in_remaining <= 0:
                    self._groove_practice_completed_ms += int(self._groove_practice_current_count_in_ms)
                    item = None
                    if 0 <= self._groove_practice_index < len(self._groove_practice_items):
                        item = self._groove_practice_items[self._groove_practice_index]
                    if item:
                        self._begin_groove_practice_play(item)
                self._update_groove_practice_remaining_label()
            else:
                self._check_groove_practice_advance()
            self._update_practice_progress()

    def _update_workout_time(self):
        self.workout_seconds += 1
        self._update_workout_display()
        if self._groove_practice_running:
            self._update_groove_practice_remaining_label()
            self._update_practice_progress()

    def _update_workout_display(self):
        if self._groove_practice_running and self._groove_practice_index >= 0:
            phase = self._groove_practice_phase or "play"
            if phase == "count_in":
                bars = max(0, int(self._groove_practice_count_in_remaining))
                self.lbl_workout_time.setText(f"Count-in {bars} bars")
                return
            remaining_ms = self._groove_practice_remaining_ms()
            if remaining_ms is None:
                remaining_ms = max(0, int(self._groove_practice_target_ms))
            remaining_sec = max(0, int((remaining_ms + 999) // 1000))
            m = remaining_sec // 60
            s = remaining_sec % 60
            if phase == "rest":
                self.lbl_workout_time.setText(f"Rest {m:02d}:{s:02d}")
            else:
                self.lbl_workout_time.setText(f"Practice {m:02d}:{s:02d}")
            return
        m = self.workout_seconds // 60
        s = self.workout_seconds % 60
        self.lbl_workout_time.setText(f"{m:02d}:{s:02d}")

    def _reset_workout_time(self):
        self.workout_seconds = 0
        self._update_workout_display()

    def _on_running_changed(self, running: bool):
        self._running_state = running
        if running:
            self._reset_loop_tracking()
            self.btn_start.setText("Stop")
            if hasattr(self, "action_toggle_start"):
                self.action_toggle_start.setText("Stop")
            self.info.setText("Running")
            self.workout_timer.start()
            if self._suppress_next_start_announcement:
                self._suppress_next_start_announcement = False
            else:
                self.voice_announcer.say_starting(int(self._current_bpm))
            if self._groove_practice_running and self._groove_practice_pause_started is not None:
                paused = self._groove_practice_elapsed.elapsed() - self._groove_practice_pause_started
                if paused > 0:
                    self._groove_practice_paused_ms += paused
                self._groove_practice_pause_started = None
        else:
            self.btn_start.setText("Start")
            if hasattr(self, "action_toggle_start"):
                self.action_toggle_start.setText("Start")
            self.info.setText("Stopped")
            self.workout_timer.stop()
            if self._groove_practice_running and self._groove_practice_pause_started is None:
                if not hasattr(self._groove_practice_elapsed, "isValid") or self._groove_practice_elapsed.isValid():
                    self._groove_practice_pause_started = self._groove_practice_elapsed.elapsed()
        if hasattr(self, "remote_state"):
            self.remote_state.set_running(running)
        if self._groove_practice_running:
            self._update_workout_display()
            self._update_groove_practice_remaining_label()
            self._update_practice_progress()

    @pyqtSlot()
    def _remote_start(self):
        if not self._running_state:
            self._toggle_start()

    @pyqtSlot()
    def _remote_stop(self):
        if self._running_state:
            self._toggle_start()

    @pyqtSlot(int)
    def _remote_set_bpm(self, bpm: int):
        self.bpm_spin.setValue(int(bpm))

    def _toggle_start(self):
        if self._running_state:
            self.sig_groove_stop.emit()
            self.sig_stop.emit()
        else:
            if self._configure_selected_groove():
                self.sig_groove_start.emit()
            self.sig_start.emit()

    def _tap_tempo(self):
        bpm = self.tap.tap()
        if bpm is not None:
            self.bpm_spin.setValue(bpm)
            self.info.setText(f"Tapped {bpm} BPM")

    # Removed _change_beats / _change_subdiv as they are direct connects now

    def _on_bpm_changed(self, bpm: int):
        self._current_bpm = bpm
        self.info.setText(f"BPM: {bpm}")
        if self._ladder_running:
            self._update_ladder_status(bpm)
        self._update_ladder_final_staff()
        if hasattr(self, "remote_state"):
            self.remote_state.set_bpm(bpm)

    def _active_ladder_config(self):
        if self._ladder_running and self._ladder_active_config:
            return self._ladder_active_config
        return (self.r_start.value(), self.r_end.value(), self.r_step.value())

    def _next_ladder_bpm(self, current_bpm: int, start_bpm: int, end_bpm: int, step_bpm: int):
        if start_bpm == end_bpm:
            return None
        if start_bpm <= end_bpm:
            if current_bpm >= end_bpm:
                return None
            return min(current_bpm + step_bpm, end_bpm)
        if current_bpm <= end_bpm:
            return None
        return max(current_bpm - step_bpm, end_bpm)

    def _update_ladder_status(self, bpm_override: int = None):
        if not hasattr(self, "lbl_ladder_current"):
            return
        start_bpm, end_bpm, step_bpm = self._active_ladder_config()
        if self._ladder_running:
            current_bpm = int(bpm_override if bpm_override is not None else self._current_bpm)
        else:
            current_bpm = int(start_bpm)
        self.lbl_ladder_current.setText(f"Ladder: {current_bpm} BPM")
        next_bpm = self._next_ladder_bpm(current_bpm, start_bpm, end_bpm, step_bpm)
        if self._ladder_running and current_bpm == end_bpm:
            next_text = "Next: Finish"
        elif next_bpm is None:
            next_text = "Next: --"
        else:
            next_text = f"Next: {next_bpm} BPM"
        self.lbl_ladder_next.setText(next_text)

    def _update_ladder_final_staff(self):
        if not hasattr(self, "drum_staff"):
            return
        is_final = False
        if self._ladder_running:
            _, end_bpm, _ = self._active_ladder_config()
            is_final = int(self._current_bpm) == int(end_bpm)
        self.drum_staff.set_ladder_final(is_final)

    def _update_ladder_progress(self, step_idx: int = None):
        if not hasattr(self, "ladder_progress"):
            return
        if not self._ladder_running:
            self.ladder_progress.setValue(0)
            self.ladder_progress.setFormat("Ladder Inactive")
            return
        bars_per_step = max(1, int(self._ladder_bars_per_step or self.r_bars.value()))
        beats_per_bar = max(1, int(self.beats_spin.value()))
        subdiv = max(1, int(self.subdiv_spin.value()))
        steps_per_bar = beats_per_bar * subdiv
        bar_counter = max(0, int(self._ladder_bar_counter))
        if step_idx is None or step_idx < 0:
            step_idx = 0
        step_idx = min(step_idx, steps_per_bar - 1)
        total_steps = max(1, int(bars_per_step * steps_per_bar))
        global_step = bar_counter * steps_per_bar + step_idx
        if total_steps <= 1:
            progress = 1.0
        else:
            progress = max(0.0, min(1.0, float(global_step) / (total_steps - 1)))
        progress = max(0.0, min(1.0, progress))
        percent = int(round(progress * 100))
        bpm = max(1, int(self._current_bpm))
        step_duration = 60.0 / (bpm * subdiv)
        steps_left_in_bar = max(0, steps_per_bar - step_idx)
        time_left = steps_left_in_bar * step_duration
        self.ladder_progress.setValue(percent)
        self.ladder_progress.setFormat(f"{percent}% - {time_left:.1f}s left in bar")

    def _update_ladder_warning(self):
        if not hasattr(self, "drum_staff"):
            return
        if not self._ladder_running:
            self._ladder_warning_active = False
            self.drum_staff.set_ladder_warning(False)
            return
        bars_per_step = max(1, int(self._ladder_bars_per_step or 1))
        prev_warning = self._ladder_warning_active
        if bars_per_step <= 1:
            warning_active = True
        else:
            warning_active = self._ladder_bar_counter == bars_per_step - 1
        self._ladder_warning_active = warning_active
        self.drum_staff.set_ladder_warning(warning_active)
        self._maybe_announce_ladder_approach(prev_warning, warning_active, bars_per_step)

    def _maybe_announce_ladder_approach(self, prev_warning: bool, warning_active: bool, bars_per_step: int):
        if not warning_active:
            return
        start_bpm, end_bpm, step_bpm = self._active_ladder_config()
        current_bpm = int(self._current_bpm)
        next_bpm = self._next_ladder_bpm(current_bpm, start_bpm, end_bpm, step_bpm)
        if next_bpm is None:
            return
        if bars_per_step > 1 and prev_warning:
            return
        if next_bpm == self._ladder_last_approach_bpm:
            return
        self._ladder_last_approach_bpm = next_bpm
        self.voice_announcer.say_approaching(next_bpm)

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
        start_bpm = int(self.r_start.value())
        self.voice_announcer.say_starting(start_bpm)
        self._ladder_last_approach_bpm = None
        self._ladder_active_config = (self.r_start.value(), self.r_end.value(), self.r_step.value())
        self._ladder_bar_counter = 0
        self._ladder_bars_per_step = max(1, int(self.r_bars.value()))
        self.sig_ladder_configure.emit(
            self.r_start.value(), self.r_end.value(), self.r_step.value(), self.r_bars.value()
        )
        if not self._running_state:
            self._suppress_next_start_announcement = True
            self.sig_start.emit()
        self.sig_ladder_start.emit()

    def _routine_state(self, running: bool):
        self._ladder_running = running
        if running and not self._ladder_active_config:
            self._ladder_active_config = (self.r_start.value(), self.r_end.value(), self.r_step.value())
        if running:
            self._ladder_bar_counter = 0
            if self._ladder_bars_per_step <= 0:
                self._ladder_bars_per_step = max(1, int(self.r_bars.value()))
            self._ladder_last_approach_bpm = None
        else:
            self._ladder_bar_counter = 0
            self._ladder_bars_per_step = 0
            self._ladder_last_approach_bpm = None
        if not running:
            self._ladder_active_config = None
        self.btn_routine.setText("Stop Ladder" if running else "Start Ladder")
        if not running:
            self.info.setText("Ladder stopped")
        else:
            self.info.setText("Ladder running")
        self._update_ladder_status()
        self._update_ladder_progress()
        self._update_ladder_warning()
        self._update_ladder_final_staff()

    def _routine_finished(self):
        self.info.setText("Ladder finished")

    def _voice_key(self, voice) -> str:
        if voice is None:
            return ""
        try:
            name = voice.name()
        except Exception:
            name = ""
        try:
            locale_name = voice.locale().name()
        except Exception:
            locale_name = ""
        if locale_name:
            return f"{name}|{locale_name}"
        return name

    def _voice_label(self, voice) -> str:
        if voice is None:
            return "(unknown)"
        try:
            name = voice.name()
        except Exception:
            name = ""
        try:
            locale_name = voice.locale().name()
        except Exception:
            locale_name = ""
        if locale_name:
            return f"{name} ({locale_name})"
        return name or "(unknown)"

    def _populate_voice_options(self):
        self._voice_map = {}
        self.voice_combo.blockSignals(True)
        self.voice_combo.clear()
        voices = self.voice_announcer.available_voices()
        for voice in voices:
            key = self._voice_key(voice)
            label = self._voice_label(voice)
            self._voice_map[key] = voice
            self.voice_combo.addItem(label, key)
        if not voices:
            self.voice_combo.addItem("(no voices)")
            self.voice_combo.setEnabled(False)
        else:
            self.voice_combo.setEnabled(True)
            current = self.voice_announcer.current_voice()
            current_key = self._voice_key(current)
            if current_key:
                idx = self.voice_combo.findData(current_key)
                if idx >= 0:
                    self.voice_combo.setCurrentIndex(idx)
        self.voice_combo.blockSignals(False)

    def _set_voice_by_key(self, key: str):
        if not key:
            return
        idx = self.voice_combo.findData(key)
        if idx >= 0:
            self.voice_combo.setCurrentIndex(idx)

    def _on_voice_enabled_changed(self, enabled: bool):
        self.voice_announcer.set_enabled(enabled)

    def _on_voice_selected(self, idx: int):
        if idx < 0:
            return
        key = self.voice_combo.itemData(idx)
        voice = self._voice_map.get(key)
        if voice is None:
            return
        self.voice_announcer.set_voice(voice)

    def _on_voice_rate_changed(self, value: int):
        rate = (int(value) - 10) / 10.0
        self.voice_rate_value.setText(f"{value / 10:.1f}x")
        self.voice_announcer.set_rate(rate)

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
            self.device_combo.setEnabled(True)
            preferred = self._preferred_audio_device
            applied_name = ""
            if preferred:
                idx = self.device_combo.findText(preferred)
                if idx >= 0:
                    self.device_combo.setCurrentIndex(idx)
                    applied_name = preferred
            if not applied_name:
                # We can't easily ask audio for 'current_device_name' synchronously if we want to be 100% pure.
                # But reading _device_info (internal) is low risk.
                cur = self.audio.current_device_name()
                idx = self.device_combo.findText(cur)
                if idx >= 0:
                    self.device_combo.setCurrentIndex(idx)
                    applied_name = cur
        self.device_combo.blockSignals(False)
        if self.device_combo.isEnabled():
            selected = self.device_combo.currentText()
            if selected and selected != "(no devices)":
                if selected != self.audio.current_device_name():
                    self._device_changed(selected)

    def _populate_midi_ports(self):
        self.midi_port_combo.blockSignals(True)
        self.midi_port_combo.clear()
        try:
            ports = self.midi_out.list_output_ports()
        except Exception:
            ports = []
        if not ports:
            self.midi_port_combo.addItem("(no ports)")
            self.midi_port_combo.setEnabled(False)
            self._current_midi_port = ""
        else:
            self.midi_port_combo.setEnabled(True)
            for name in ports:
                self.midi_port_combo.addItem(name)
            if self._current_midi_port:
                idx = self.midi_port_combo.findText(self._current_midi_port)
                if idx >= 0:
                    self.midi_port_combo.setCurrentIndex(idx)
                else:
                    self._current_midi_port = self.midi_port_combo.itemText(0)
                    self.midi_port_combo.setCurrentIndex(0)
            else:
                self._current_midi_port = self.midi_port_combo.itemText(0)
                self.midi_port_combo.setCurrentIndex(0)
        self.midi_port_combo.blockSignals(False)
        if ports and self._current_midi_port:
            self._on_midi_port_changed(self._current_midi_port)

    def _on_midi_port_changed(self, name: str):
        if not name or name == "(no ports)":
            return
        self._current_midi_port = name
        self.sig_midi_set_port.emit(name)

    def _on_midi_status_changed(self, text: str):
        self.lbl_midi_status.setText(text)

    def _on_midi_mapping_changed(self, voice: str):
        note_spin = self.midi_note_spins.get(voice)
        vel_spin = self.midi_velocity_spins.get(voice)
        if not note_spin or not vel_spin:
            return
        self.sig_midi_set_voice.emit(voice, note_spin.value(), vel_spin.value())

    def _apply_midi_mapping(self):
        for voice in self.midi_note_spins:
            self._on_midi_mapping_changed(voice)

    def _device_changed(self, name: str):
        if not name or name == "(no devices)":
            return
        self._preferred_audio_device = name
        self.sig_change_device.emit(name)
        # We can't verify success synchronously. Rely on signal back.

    def _on_device_changed_info(self, name: str, fmt: str):
        self.info.setText(f"Device: {name}  •  {fmt}")
        # Trigger test click
        self.sig_audio_play.emit(False)

    def _on_sound_settings_changed(self):
        self.sig_update_sounds.emit(
            self.normal_sound_combo.currentText(),
            self.accent_sound_combo.currentText()
        )

    def _on_click_volume_changed(self, value: int):
        self.sig_click_volume.emit(max(0.0, min(1.0, value / 100.0)))

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

    def _groove_active_changed(self, active: bool):
        self.drum_staff.set_playing(active)
        if not active:
            self.info.setText("Groove stopped")

    def _groove_changed(self, groove: DrumGroove):
        if groove:
            self._set_groove_bars(groove)
            self._sync_metronome_to_groove(groove)
            self.drum_staff.set_groove(groove)
            self._update_groove_label(groove.name)
            self.info.setText(f"Groove: {groove.name}")

    def _on_groove_selected(self, name: str):
        # Update the drum staff display when a new groove is selected
        if name:
            groove = self._configure_selected_groove(name)
            if groove:
                self.drum_staff.set_groove(groove)
                # Force immediate repaint
                self.drum_staff.repaint()

    def _edit_groove(self):
        dialog = GrooveEditorDialog(self.groove_library, self)

        # Load current groove if one is selected
        current_name = self.groove_combo.currentText()
        if current_name:
            groove = self.groove_library.get_groove_by_name(current_name)
            if groove:
                dialog.load_groove_for_editing(groove)

        # Handle groove saved
        def on_groove_saved(groove: DrumGroove):
            # Refresh combo box
            self.groove_combo.clear()
            self.groove_combo.addItems(self.groove_library.get_groove_names())
            # Select the newly saved groove
            idx = self.groove_combo.findText(groove.name)
            if idx >= 0:
                self.groove_combo.setCurrentIndex(idx)
            self._refresh_groove_practice_options()

        dialog.grooveSaved.connect(on_groove_saved)
        dialog.exec_()

    def _coerce_bool(self, value, default=False) -> bool:
        if value is None:
            return default
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)):
            return bool(value)
        if isinstance(value, str):
            return value.strip().lower() in ("1", "true", "yes", "on")
        return default

    def _coerce_int(self, value, default: int) -> int:
        try:
            return int(value)
        except (TypeError, ValueError):
            return int(default)

    def _coerce_port(self, value, default: int) -> int:
        port = self._coerce_int(value, default)
        if 1 <= port <= 65535:
            return port
        return int(default)

    def _coerce_float(self, value, default: float) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return float(default)

    def _lead_hand_from_combo(self) -> str:
        text = self.rudiment_widget.combo_hand.currentText()
        if "Left" in text:
            return "L"
        if "Mixed" in text:
            return "Mixed"
        return "R"

    def _set_combo_text(self, combo, text: str):
        if not text:
            return
        idx = combo.findText(text)
        if idx >= 0:
            combo.setCurrentIndex(idx)

    def _set_rudiment_checkboxes(self, enabled_names):
        if enabled_names is None:
            return
        enabled_set = {str(name) for name in enabled_names}
        for name, cb in self.rudiment_widget.checkboxes.items():
            cb.blockSignals(True)
            cb.setChecked(name in enabled_set)
            cb.blockSignals(False)
        self.rudiment_widget._on_selection_changed()

    def _load_settings(self):
        settings = self._settings
        try:
            geometry = settings.value("window/geometry")
            if geometry:
                self.restoreGeometry(geometry)
            state = settings.value("window/state")
            if state:
                self.restoreState(state)
        except Exception:
            pass

        audio_device = settings.value("audio/device_name", "")
        if audio_device:
            self._preferred_audio_device = str(audio_device)

        midi_port = settings.value("midi/port_name", "")
        if midi_port:
            self._current_midi_port = str(midi_port)

        self._remote_http_port = self._coerce_port(
            settings.value("remote/http_port"), self._remote_http_port
        )
        self._remote_discovery_port = self._coerce_port(
            settings.value("remote/discovery_port"), self._remote_discovery_port
        )

        self.bpm_spin.setValue(self._coerce_int(settings.value("session/bpm"), self.bpm_spin.value()))
        self.beats_spin.setValue(self._coerce_int(settings.value("meter/beats_per_bar"), self.beats_spin.value()))
        self.subdiv_spin.setValue(self._coerce_int(settings.value("meter/subdivision"), self.subdiv_spin.value()))
        self.click_subdiv_spin.setValue(self._coerce_int(
            settings.value("meter/click_subdivision"), self.click_subdiv_spin.value()
        ))
        self.chk_accent.setChecked(
            self._coerce_bool(settings.value("meter/accent_on_one"), self.chk_accent.isChecked())
        )
        self.mute_on_spin.setValue(self._coerce_int(settings.value("mute/bars_on"), self.mute_on_spin.value()))
        self.mute_off_spin.setValue(self._coerce_int(settings.value("mute/bars_off"), self.mute_off_spin.value()))

        self.r_start.setValue(self._coerce_int(settings.value("ladder/start_bpm"), self.r_start.value()))
        self.r_end.setValue(self._coerce_int(settings.value("ladder/end_bpm"), self.r_end.value()))
        self.r_step.setValue(self._coerce_int(settings.value("ladder/step_bpm"), self.r_step.value()))
        self.r_bars.setValue(self._coerce_int(settings.value("ladder/bars_per_step"), self.r_bars.value()))

        self.rud_bars.setValue(
            self._coerce_int(settings.value("rudiments/bars_per_rudiment"), self.rud_bars.value())
        )
        if settings.contains("rudiments/lead_hand"):
            lead = settings.value("rudiments/lead_hand", "")
            lead = str(lead) if lead is not None else ""
            if lead:
                if lead in ("R", "Right", "Right (R)"):
                    lead_text = "Right (R)"
                elif lead in ("L", "Left", "Left (L)"):
                    lead_text = "Left (L)"
                elif lead.lower().startswith("mix"):
                    lead_text = "Mixed"
                else:
                    lead_text = lead
                self._set_combo_text(self.rudiment_widget.combo_hand, lead_text)
        if settings.contains("rudiments/enabled_list"):
            enabled_raw = settings.value("rudiments/enabled_list")
            enabled_list = []
            if isinstance(enabled_raw, str):
                try:
                    parsed = json.loads(enabled_raw)
                    if isinstance(parsed, list):
                        enabled_list = [str(name) for name in parsed]
                except Exception:
                    if enabled_raw:
                        enabled_list = [str(enabled_raw)]
            elif isinstance(enabled_raw, list):
                enabled_list = [str(name) for name in enabled_raw]
            self._set_rudiment_checkboxes(enabled_list)

        groove_name = settings.value("groove/selected", "")
        if groove_name:
            self._set_combo_text(self.groove_combo, str(groove_name))
        self.groove_loop_spin.setValue(
            self._coerce_int(settings.value("groove/loop_count"), self.groove_loop_spin.value())
        )
        self.chk_groove_midi.setChecked(
            self._coerce_bool(settings.value("groove/audio_enabled"), self.chk_groove_midi.isChecked())
        )
        self.chk_toggle_groove_silence.setChecked(
            self._coerce_bool(
                settings.value("groove/toggle_silence"),
                self.chk_toggle_groove_silence.isChecked()
            )
        )
        self.chk_toggle_metronome_silence.setChecked(
            self._coerce_bool(
                settings.value("metronome/toggle_silence"),
                self.chk_toggle_metronome_silence.isChecked()
            )
        )

        self._groove_practice_presets = {}
        self._groove_practice_active_name = ""
        presets_raw = settings.value("groove_practice/presets", "")
        if presets_raw:
            try:
                if isinstance(presets_raw, str):
                    presets_data = json.loads(presets_raw)
                else:
                    presets_data = presets_raw
            except Exception:
                presets_data = {}
            if isinstance(presets_data, dict):
                self._groove_practice_presets = presets_data
        active_name = settings.value("groove_practice/active_name", "")
        if active_name:
            self._groove_practice_active_name = str(active_name)

        loaded = False
        if self._groove_practice_active_name in self._groove_practice_presets:
            preset = self._groove_practice_presets.get(self._groove_practice_active_name, {})
            self._load_groove_practice_preset(self._groove_practice_active_name, preset)
            loaded = True

        if not loaded and settings.contains("groove_practice/last_items"):
            last_items_raw = settings.value("groove_practice/last_items")
            last_options_raw = settings.value("groove_practice/last_options")
            last_items = []
            if isinstance(last_items_raw, str):
                try:
                    last_items = json.loads(last_items_raw)
                except Exception:
                    last_items = []
            elif isinstance(last_items_raw, list):
                last_items = last_items_raw
            if isinstance(last_items, list):
                self._set_groove_practice_items(last_items)
                if last_options_raw:
                    if isinstance(last_options_raw, str):
                        try:
                            last_options = json.loads(last_options_raw)
                        except Exception:
                            last_options = {}
                    elif isinstance(last_options_raw, dict):
                        last_options = last_options_raw
                    else:
                        last_options = {}
                    self._apply_groove_practice_options(last_options)
                loaded = True

        if not loaded and settings.contains("groove_practice/items"):
            raw_items = settings.value("groove_practice/items")
            parsed = []
            if isinstance(raw_items, str):
                try:
                    parsed = json.loads(raw_items)
                except Exception:
                    parsed = []
            elif isinstance(raw_items, list):
                parsed = raw_items
            if isinstance(parsed, list) and parsed:
                self._set_groove_practice_items(parsed)

        normal_sound = settings.value("sounds/normal", "")
        if normal_sound:
            self._set_combo_text(self.normal_sound_combo, str(normal_sound))
        accent_sound = settings.value("sounds/accent", "")
        if accent_sound:
            self._set_combo_text(self.accent_sound_combo, str(accent_sound))
        self.click_volume_slider.setValue(
            self._coerce_int(settings.value("sounds/volume"), self.click_volume_slider.value())
        )

        if self.voice_announcer.is_available():
            self.chk_voice_announcements.setChecked(
                self._coerce_bool(settings.value("voice/enabled"), self.chk_voice_announcements.isChecked())
            )
        else:
            self.chk_voice_announcements.setChecked(False)
        self.voice_rate_slider.setValue(
            self._coerce_int(settings.value("voice/rate_tenth"), self.voice_rate_slider.value())
        )
        voice_key = settings.value("voice/selected", "")
        if voice_key:
            self._set_voice_by_key(str(voice_key))

        self.staff_scale_slider.setValue(
            self._coerce_int(settings.value("staff/ui_scale_tenth"), self.staff_scale_slider.value())
        )
        self.groove_scale_slider.setValue(
            self._coerce_int(settings.value("staff/note_scale_tenth"), self.groove_scale_slider.value())
        )
        if hasattr(self, "chk_staff_scroll"):
            default_scroll = self.chk_staff_scroll.isChecked()
            self.chk_staff_scroll.setChecked(
                self._coerce_bool(settings.value("staff/scroll_staff"), default_scroll)
            )
        if hasattr(self, "header_timer_slider"):
            self.header_timer_slider.setValue(
                self._coerce_int(
                    settings.value("display/header_timer_scale_tenth"),
                    self.header_timer_slider.value()
                )
            )
        if hasattr(self, "header_ladder_slider"):
            self.header_ladder_slider.setValue(
                self._coerce_int(
                    settings.value("display/header_ladder_scale_tenth"),
                    self.header_ladder_slider.value()
                )
            )
        if hasattr(self, "header_progress_slider"):
            self.header_progress_slider.setValue(
                self._coerce_int(
                    settings.value("display/header_progress_scale_tenth"),
                    self.header_progress_slider.value()
                )
            )
        if (
            settings.contains("display/header_text_scale_tenth")
            and not settings.contains("display/header_timer_scale_tenth")
            and not settings.contains("display/header_ladder_scale_tenth")
            and not settings.contains("display/header_progress_scale_tenth")
        ):
            legacy_scale = self._coerce_int(settings.value("display/header_text_scale_tenth"), 10)
            if hasattr(self, "header_timer_slider"):
                self.header_timer_slider.setValue(legacy_scale)
            if hasattr(self, "header_ladder_slider"):
                self.header_ladder_slider.setValue(legacy_scale)
            if hasattr(self, "header_progress_slider"):
                self.header_progress_slider.setValue(legacy_scale)
        if hasattr(self, "rhythm_text_offset_spin"):
            default_offset = self.rhythm_text_offset_spin.value() / 2.0
            offset = self._coerce_float(settings.value("staff/rhythm_text_offset"), default_offset)
            self.rhythm_text_offset_spin.setValue(int(round(offset * 2)))
        for voice, spin in self.staff_voice_position_spins.items():
            default_pos = spin.value() / 2.0
            pos = self._coerce_float(settings.value(f"staff/voice_position/{voice}"), default_pos)
            spin.setValue(int(round(pos * 2)))

        self.chk_midi_out.setChecked(
            self._coerce_bool(settings.value("midi/enabled"), self.chk_midi_out.isChecked())
        )
        for voice, note_spin in self.midi_note_spins.items():
            note_value = self._coerce_int(
                settings.value(f"midi/map/{voice}/note"), note_spin.value()
            )
            note_spin.setValue(note_value)
            vel_spin = self.midi_velocity_spins.get(voice)
            if vel_spin:
                vel_value = self._coerce_int(
                    settings.value(f"midi/map/{voice}/velocity"), vel_spin.value()
                )
                vel_spin.setValue(vel_value)

        self.workout_seconds = self._coerce_int(
            settings.value("session/workout_seconds"), self.workout_seconds
        )
        self._update_workout_display()

        self._restore_flags = {
            "engine": self._coerce_bool(settings.value("session/running"), False),
            "ladder": self._coerce_bool(settings.value("ladder/running"), False),
            "rudiments": self._coerce_bool(settings.value("rudiments/running"), False),
            "groove": self._coerce_bool(settings.value("groove/running"), False),
        }

    def _save_settings(self):
        settings = self._settings
        settings.setValue("meta/version", 1)
        settings.setValue("window/geometry", self.saveGeometry())
        settings.setValue("window/state", self.saveState())
        settings.setValue("remote/http_port", self._remote_http_port)
        settings.setValue("remote/discovery_port", self._remote_discovery_port)

        settings.setValue("session/bpm", self.bpm_spin.value())
        settings.setValue("session/running", self._running_state)
        settings.setValue("session/workout_seconds", self.workout_seconds)

        settings.setValue("meter/beats_per_bar", self.beats_spin.value())
        settings.setValue("meter/subdivision", self.subdiv_spin.value())
        settings.setValue("meter/click_subdivision", self.click_subdiv_spin.value())
        settings.setValue("meter/accent_on_one", self.chk_accent.isChecked())
        settings.setValue("metronome/toggle_silence", self.chk_toggle_metronome_silence.isChecked())

        settings.setValue("mute/bars_on", self.mute_on_spin.value())
        settings.setValue("mute/bars_off", self.mute_off_spin.value())

        normal_sound = self.normal_sound_combo.currentText()
        if normal_sound:
            settings.setValue("sounds/normal", normal_sound)
        accent_sound = self.accent_sound_combo.currentText()
        if accent_sound:
            settings.setValue("sounds/accent", accent_sound)
        settings.setValue("sounds/volume", self.click_volume_slider.value())

        settings.setValue("voice/enabled", self.chk_voice_announcements.isChecked())
        settings.setValue("voice/rate_tenth", self.voice_rate_slider.value())
        voice_key = self.voice_combo.currentData()
        if voice_key:
            settings.setValue("voice/selected", str(voice_key))

        settings.setValue("staff/ui_scale_tenth", self.staff_scale_slider.value())
        settings.setValue("staff/note_scale_tenth", self.groove_scale_slider.value())
        if hasattr(self, "chk_staff_scroll"):
            settings.setValue("staff/scroll_staff", self.chk_staff_scroll.isChecked())
        if hasattr(self, "rhythm_text_offset_spin"):
            settings.setValue("staff/rhythm_text_offset", self.rhythm_text_offset_spin.value() / 2.0)
        if hasattr(self, "header_timer_slider"):
            settings.setValue("display/header_timer_scale_tenth", self.header_timer_slider.value())
        if hasattr(self, "header_ladder_slider"):
            settings.setValue("display/header_ladder_scale_tenth", self.header_ladder_slider.value())
        if hasattr(self, "header_progress_slider"):
            settings.setValue("display/header_progress_scale_tenth", self.header_progress_slider.value())
        for voice, spin in self.staff_voice_position_spins.items():
            settings.setValue(f"staff/voice_position/{voice}", spin.value() / 2.0)

        if self.device_combo.isEnabled():
            device_name = self.device_combo.currentText()
            if device_name and device_name != "(no devices)":
                settings.setValue("audio/device_name", device_name)

        groove_name = self.groove_combo.currentText()
        if groove_name:
            settings.setValue("groove/selected", groove_name)
        settings.setValue("groove/loop_count", self.groove_loop_spin.value())
        settings.setValue("groove/audio_enabled", self.chk_groove_midi.isChecked())
        settings.setValue("groove/toggle_silence", self.chk_toggle_groove_silence.isChecked())
        settings.setValue("groove/running", self.groove_routine.running)
        settings.setValue(
            "groove_practice/presets",
            json.dumps(self._groove_practice_presets),
        )
        settings.setValue("groove_practice/active_name", self._groove_practice_active_name)
        settings.setValue(
            "groove_practice/last_items",
            json.dumps(self._get_groove_practice_items()),
        )
        settings.setValue(
            "groove_practice/last_options",
            json.dumps(self._collect_groove_practice_options()),
        )

        settings.setValue("ladder/start_bpm", self.r_start.value())
        settings.setValue("ladder/end_bpm", self.r_end.value())
        settings.setValue("ladder/step_bpm", self.r_step.value())
        settings.setValue("ladder/bars_per_step", self.r_bars.value())
        settings.setValue("ladder/running", self.ladder.is_running())

        settings.setValue("rudiments/bars_per_rudiment", self.rud_bars.value())
        settings.setValue("rudiments/lead_hand", self._lead_hand_from_combo())
        enabled_rudiments = [
            name for name, cb in self.rudiment_widget.checkboxes.items() if cb.isChecked()
        ]
        settings.setValue("rudiments/enabled_list", json.dumps(enabled_rudiments))
        settings.setValue("rudiments/running", self.rudiment_routine.running)

        settings.setValue("midi/enabled", self.chk_midi_out.isChecked())
        midi_port = self._current_midi_port or self.midi_port_combo.currentText()
        if self.midi_port_combo.isEnabled() and midi_port and midi_port != "(no ports)":
            settings.setValue("midi/port_name", midi_port)
        for voice, note_spin in self.midi_note_spins.items():
            settings.setValue(f"midi/map/{voice}/note", note_spin.value())
            vel_spin = self.midi_velocity_spins.get(voice)
            if vel_spin:
                settings.setValue(f"midi/map/{voice}/velocity", vel_spin.value())

        settings.sync()

    def _restore_running_state(self):
        flags = self._restore_flags or {}
        if not flags:
            return
        engine_should_run = (
            flags.get("engine", False)
            or flags.get("ladder", False)
            or flags.get("rudiments", False)
            or flags.get("groove", False)
        )
        if flags.get("ladder", False):
            self._ladder_active_config = (self.r_start.value(), self.r_end.value(), self.r_step.value())
            self._ladder_bar_counter = 0
            self._ladder_bars_per_step = max(1, int(self.r_bars.value()))
            self.sig_ladder_configure.emit(
                self.r_start.value(), self.r_end.value(), self.r_step.value(), self.r_bars.value()
            )
        if engine_should_run and not self._running_state:
            self.sig_start.emit()
        if flags.get("groove", False):
            self._configure_selected_groove()
            self.sig_groove_start.emit()
        if flags.get("ladder", False):
            self.sig_ladder_start.emit()
        if flags.get("rudiments", False):
            self.sig_rudiment_start.emit()

    def _shutdown_worker(self):
        if not hasattr(self, "worker_thread") or self.worker_thread is None:
            return
        try:
            self.sig_ladder_stop.emit()
            self.sig_rudiment_stop.emit()
            self.sig_groove_stop.emit()
            self.sig_stop.emit()
        except Exception:
            pass
        for obj in (self.engine, self.audio, self.groove_audio, self.midi_out):
            try:
                obj.deleteLater()
            except Exception:
                pass
        if self.worker_thread.isRunning():
            self.worker_thread.quit()
            self.worker_thread.wait(2000)
        if hasattr(self, "groove_audio_thread") and self.groove_audio_thread.isRunning():
            self.groove_audio_thread.quit()
            self.groove_audio_thread.wait(2000)

    def closeEvent(self, event):
        self._save_settings()
        if hasattr(self, "control_server") and self.control_server:
            self.control_server.stop()
        self._shutdown_worker()
        super().closeEvent(event)


if __name__ == "__main__":
    # for quick local run
    import sys
    app = QApplication(sys.argv)
    w = MainWindow()
    w.show()
    sys.exit(app.exec_())
