from PyQt5.QtCore import (
    Qt,
    QRect,
    QTimer,
    QElapsedTimer,
    pyqtSlot,
    QPoint,
    pyqtProperty,
    QPropertyAnimation,
    QEasingCurve,
)
from PyQt5.QtWidgets import QWidget
from PyQt5.QtGui import QPainter, QColor, QFont, QPen, QBrush, QPolygon, QPixmap
from typing import List, Optional
from .groove import DrumGroove, DrumNote


class DrumStaffWidget(QWidget):
    """
    A widget that displays a scrolling drum staff notation.
    Shows drum notation with different voices on appropriate staff positions.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.voice_positions = {
            'crash': 4.0,
            'ride': 3.0,
            'hihat_closed': 3.0,
            'hihat_open': 3.0,
            'hihat': 3.0,
            'tom1': 2.0,
            'snare': 0.0,
            'tom2': -1.0,
            'tom3': -2.0,
            'kick': -3.0,
        }
        self.ui_scale = 2.0
        self.note_scale = 1.0
        self.rhythm_text_offset = 0.0
        self._update_scaled_metrics()

        # Current groove being displayed
        self.current_groove: Optional[DrumGroove] = None

        # Playback state
        self.current_bar = 0
        self.current_beat = 0
        self.current_subdivision = 0
        self.is_playing = False

        # Visual settings
        self.staff_color = QColor("#444444")
        self.ladder_final_staff_color = QColor(0, 255, 0, 128)
        self.note_color = QColor("#0d6efd")
        self.accent_color = QColor("#ff4d4d")
        self.playhead_color = QColor("#00ff00")
        self.base_bg_color = QColor("#1a1a1a")
        self.warning_bg_color = QColor("#2a1c1c")
        self.warning_pulse_color = QColor("#3a2626")
        self._ladder_warning = False
        self._ladder_final = False
        self._ladder_pulse = 0.0
        self._ladder_pulse_anim = QPropertyAnimation(self, b"ladderPulse")
        self._ladder_pulse_anim.setDuration(300)
        self._ladder_pulse_anim.setStartValue(1.0)
        self._ladder_pulse_anim.setEndValue(0.0)
        self._ladder_pulse_anim.setEasingCurve(QEasingCurve.OutCubic)
        self.text_color = QColor("#e0e0e0")
        self.rhythm_beat_color = QColor("#e0e0e0")
        self.rhythm_subdiv_color = QColor("#8a8a8a")
        self.triplet_line_color = QColor("#6ad1c0")
        self.thirty_second_line_color = QColor("#f28e2b")
        self.thirty_second_dot_color = QColor("#ff4d4d")
        self.bar_range_color = QColor("#8a8a8a")
        self.voice_styles = {
            'crash': {'color': QColor("#edc949"), 'shape': 'x'},
            'ride': {'color': QColor("#f28e2b"), 'shape': 'ring'},
            'hihat_closed': {'color': QColor("#59a14f"), 'shape': 'triangle_up'},
            'hihat_open': {'color': QColor("#86bc7c"), 'shape': 'x'},
            'hihat': {'color': QColor("#59a14f"), 'shape': 'triangle_up'},
            'tom1': {'color': QColor("#76b7b2"), 'shape': 'diamond'},
            'snare': {'color': QColor("#4e79a7"), 'shape': 'circle'},
            'tom2': {'color': QColor("#af7aa1"), 'shape': 'square'},
            'tom3': {'color': QColor("#ff9da7"), 'shape': 'hexagon'},
            'kick': {'color': QColor("#e15759"), 'shape': 'triangle_down'},
        }

        # Layout settings
        self.bars_visible = 2  # How many bars to show at once
        self._scroll_staff = True

        # Active notes (currently playing)
        self.active_notes: List[DrumNote] = []

        # Animation timer for smooth scrolling
        self.animation_timer = QTimer()
        self.animation_timer.timeout.connect(self.update)
        self._animation_interval_ms = 16  # ~60 FPS
        self._update_animation_timer()

        # Timing state for smooth playhead/staff motion
        self._position_timer = QElapsedTimer()
        self._position_timer.start()
        self._last_position_time_ms = None
        self._step_duration_ms = None
        self._scroll_cache = None
        self._scroll_cache_key = None

    def _reset_animation_timing(self):
        self._last_position_time_ms = None
        self._step_duration_ms = None
        self._position_timer.restart()

    def _update_animation_timer(self):
        should_run = self.is_playing and self._scroll_staff
        if should_run:
            if not self.animation_timer.isActive():
                self.animation_timer.start(self._animation_interval_ms)
        else:
            if self.animation_timer.isActive():
                self.animation_timer.stop()

    def _invalidate_scroll_cache(self):
        self._scroll_cache = None
        self._scroll_cache_key = None

    @pyqtSlot(object)
    def set_groove(self, groove: DrumGroove):
        """Set the groove to display."""
        self.current_groove = groove
        self.current_bar = 0
        self.current_beat = 0
        self.current_subdivision = 0
        self._reset_animation_timing()
        self._invalidate_scroll_cache()
        self.update()

    @pyqtSlot(int, int, int)
    def set_position(self, bar: int, beat: int, subdivision: int):
        """Update the current playback position."""
        if self.current_groove:
            self.current_bar = bar
            self.current_beat = beat
            self.current_subdivision = subdivision
            if self.is_playing:
                now_ms = self._position_timer.elapsed()
                if self._last_position_time_ms is not None:
                    delta_ms = now_ms - self._last_position_time_ms
                    if delta_ms > 0:
                        if self._step_duration_ms is None:
                            self._step_duration_ms = float(delta_ms)
                        else:
                            alpha = 0.25
                            self._step_duration_ms = (
                                (1.0 - alpha) * self._step_duration_ms + alpha * delta_ms
                            )
                self._last_position_time_ms = now_ms
            self.update()

    @pyqtSlot(list)
    def set_active_notes(self, notes: List[DrumNote]):
        """Set which notes are currently playing (for highlighting)."""
        self.active_notes = notes
        self.update()

    @pyqtSlot(bool)
    def set_playing(self, playing: bool):
        """Set whether the groove is playing."""
        if playing and not self.is_playing:
            self.current_bar = 0
            self._reset_animation_timing()
        elif not playing and self.is_playing:
            self._reset_animation_timing()
        self.is_playing = playing
        self._update_animation_timer()
        self.update()

    @pyqtSlot()
    def reset_position(self):
        """Reset the playhead position tracking."""
        self.current_bar = 0
        self.current_beat = 0
        self.current_subdivision = 0
        self._reset_animation_timing()
        self.update()

    def _get_ladder_pulse(self) -> float:
        return self._ladder_pulse

    def _set_ladder_pulse(self, value: float):
        self._ladder_pulse = max(0.0, min(1.0, float(value)))
        self.update()

    ladderPulse = pyqtProperty(float, fget=_get_ladder_pulse, fset=_set_ladder_pulse)

    @pyqtSlot(bool)
    def set_ladder_warning(self, enabled: bool):
        enabled = bool(enabled)
        if enabled == self._ladder_warning:
            return
        self._ladder_warning = enabled
        if not enabled:
            self._ladder_pulse_anim.stop()
            self._set_ladder_pulse(0.0)
        self.update()

    @pyqtSlot(bool)
    def set_ladder_final(self, enabled: bool):
        enabled = bool(enabled)
        if enabled == self._ladder_final:
            return
        self._ladder_final = enabled
        self._invalidate_scroll_cache()
        self.update()

    @pyqtSlot(int)
    def trigger_ladder_pulse(self, duration_ms: int = 300):
        if not self._ladder_warning:
            return
        duration = max(60, int(duration_ms))
        self._ladder_pulse_anim.stop()
        self._ladder_pulse_anim.setDuration(duration)
        self._ladder_pulse_anim.setStartValue(1.0)
        self._ladder_pulse_anim.setEndValue(0.0)
        self._ladder_pulse_anim.start()

    @staticmethod
    def _blend_color(color_a: QColor, color_b: QColor, t: float) -> QColor:
        t = max(0.0, min(1.0, t))
        inv = 1.0 - t
        return QColor(
            int(color_a.red() * inv + color_b.red() * t),
            int(color_a.green() * inv + color_b.green() * t),
            int(color_a.blue() * inv + color_b.blue() * t),
        )

    def _scaled(self, value: float) -> int:
        return int(round(value * self.ui_scale))

    def _update_scaled_metrics(self):
        self.setMinimumHeight(self._scaled(270))
        self.setMaximumHeight(self._scaled(450))
        self.staff_line_spacing = self._scaled(18)
        base_note = self._scaled(7)
        self.note_size = max(2, int(round(base_note * self.note_scale)))

    def set_ui_scale(self, scale: float):
        self.ui_scale = max(0.5, min(3.0, float(scale)))
        self._update_scaled_metrics()
        self.updateGeometry()
        self._invalidate_scroll_cache()
        self.update()

    def set_note_scale(self, scale: float):
        self.note_scale = max(0.5, min(2.5, float(scale)))
        self._update_scaled_metrics()
        self._invalidate_scroll_cache()
        self.update()

    def _get_voice_position(self, voice: str) -> float:
        """
        Get the vertical position for a drum voice.
        Returns a position relative to the staff (0 = middle line).
        """
        if voice in self.voice_positions:
            return self.voice_positions[voice]
        if voice == "hihat" and "hihat_closed" in self.voice_positions:
            return self.voice_positions["hihat_closed"]
        return 0

    def _get_voice_style(self, voice: str) -> dict:
        """Get color + shape for each voice."""
        return self.voice_styles.get(voice, {'color': self.note_color, 'shape': 'circle'})

    def get_voice_position(self, voice: str) -> float:
        return self._get_voice_position(voice)

    def set_voice_position(self, voice: str, position: float):
        if not voice:
            return
        pos = float(position)
        pos = max(-6.0, min(6.0, pos))
        self.voice_positions[voice] = pos
        if voice == "hihat_closed":
            self.voice_positions["hihat"] = pos
        self._invalidate_scroll_cache()
        self.update()

    def set_voice_positions(self, positions: dict):
        if not isinstance(positions, dict):
            return
        for voice, position in positions.items():
            self.set_voice_position(str(voice), position)

    def get_rhythm_text_offset(self) -> float:
        return self.rhythm_text_offset

    def set_rhythm_text_offset(self, offset: float):
        self.rhythm_text_offset = max(-6.0, min(6.0, float(offset)))
        self._invalidate_scroll_cache()
        self.update()

    def is_scroll_staff(self) -> bool:
        return self._scroll_staff

    @pyqtSlot(bool)
    def set_scroll_staff(self, enabled: bool):
        enabled = bool(enabled)
        if enabled == self._scroll_staff:
            return
        self._scroll_staff = enabled
        self._invalidate_scroll_cache()
        self._update_animation_timer()
        self.update()

    def resizeEvent(self, event):
        self._invalidate_scroll_cache()
        super().resizeEvent(event)

    def _normalize_hand(self, hand: Optional[str]) -> Optional[str]:
        if not hand:
            return None
        hand = hand.upper()
        return hand if hand in ("L", "R") else None

    def _draw_staff_lines(self, painter: QPainter, x: int, y_center: int, width: int):
        """Draw the 5-line staff."""
        painter.setPen(QPen(self._staff_pen_color(), self._scaled(1)))

        for i in range(-2, 3):  # 5 lines: -2, -1, 0, 1, 2
            y = y_center + i * self.staff_line_spacing
            painter.drawLine(x, y, x + width, y)

    def _draw_voice_labels(self, painter: QPainter, x: int, y_center: int):
        """Draw labels for drum voices on the left side."""
        font = QFont("Arial", self._scaled(9))
        painter.setFont(font)

        label_offset_x = self._scaled(50)
        label_offset_y = self._scaled(8)
        label_width = self._scaled(45)
        label_height = self._scaled(16)

        labels = [
            ('HH C/O', self._get_voice_position('hihat_closed'),
             self.voice_styles.get('hihat_closed', {}).get('color', self.text_color)),
            ('Snare', self._get_voice_position('snare'),
             self.voice_styles.get('snare', {}).get('color', self.text_color)),
            ('Kick', self._get_voice_position('kick'),
             self.voice_styles.get('kick', {}).get('color', self.text_color)),
        ]

        for label, position, color in labels:
            y = int(round(y_center + position * self.staff_line_spacing))
            painter.setPen(color)
            painter.drawText(
                x - label_offset_x,
                y - label_offset_y,
                label_width,
                label_height,
                Qt.AlignRight | Qt.AlignVCenter,
                label
            )

    def _draw_note_shape(self, painter: QPainter, x: int, y: int, shape: str, color: QColor, is_active: bool):
        size = self.note_size

        if is_active:
            painter.setPen(QPen(self.playhead_color, self._scaled(2)))
            painter.setBrush(Qt.NoBrush)
            highlight_size = size + self._scaled(4)
            painter.drawEllipse(x - highlight_size, y - highlight_size,
                                highlight_size * 2, highlight_size * 2)

        painter.setPen(QPen(color, self._scaled(2)))
        painter.setBrush(QBrush(color))

        if shape == 'ring':
            painter.setBrush(Qt.NoBrush)
            painter.drawEllipse(x - size, y - size, size * 2, size * 2)
            return

        if shape == 'circle':
            painter.drawEllipse(x - size, y - size, size * 2, size * 2)
            return

        if shape == 'square':
            painter.drawRect(x - size, y - size, size * 2, size * 2)
            return

        if shape == 'diamond':
            points = QPolygon([
                QPoint(x, y - size),
                QPoint(x + size, y),
                QPoint(x, y + size),
                QPoint(x - size, y),
            ])
            painter.drawPolygon(points)
            return

        if shape == 'triangle_up':
            points = QPolygon([
                QPoint(x, y - size),
                QPoint(x + size, y + size),
                QPoint(x - size, y + size),
            ])
            painter.drawPolygon(points)
            return

        if shape == 'triangle_down':
            points = QPolygon([
                QPoint(x - size, y - size),
                QPoint(x + size, y - size),
                QPoint(x, y + size),
            ])
            painter.drawPolygon(points)
            return

        if shape == 'hexagon':
            half = size // 2
            points = QPolygon([
                QPoint(x - size, y),
                QPoint(x - half, y - size),
                QPoint(x + half, y - size),
                QPoint(x + size, y),
                QPoint(x + half, y + size),
                QPoint(x - half, y + size),
            ])
            painter.drawPolygon(points)
            return

        if shape == 'x':
            painter.setBrush(Qt.NoBrush)
            painter.drawLine(x - size, y - size, x + size, y + size)
            painter.drawLine(x - size, y + size, x + size, y - size)
            return

        painter.drawEllipse(x - size, y - size, size * 2, size * 2)

    def _draw_hand_marker(self, painter: QPainter, x: int, y: int, hand: str):
        base_size = max(6, int(round(self.note_size * 0.8)))
        font_size = base_size * 2
        font = QFont("Arial", font_size, QFont.Bold)
        painter.setFont(font)
        painter.setPen(self.text_color)
        rect = QRect(x - self.note_size, y - self.note_size, self.note_size * 2, self.note_size * 2)
        painter.drawText(rect, Qt.AlignCenter, hand)

    def _draw_note(self, painter: QPainter, x: int, y_center: int, note: DrumNote, is_active: bool = False):
        """Draw a single note on the staff."""
        y_pos = self._get_voice_position(note.voice)
        y = int(round(y_center + y_pos * self.staff_line_spacing))

        style = self._get_voice_style(note.voice)
        color = style['color']
        shape = style['shape']

        self._draw_note_shape(painter, x, y, shape, color, is_active)

        # Draw accent mark if needed (> symbol above note)
        if note.accent and not is_active:
            accent_font_size = max(8, int(round(self._scaled(10) * self.note_scale)))
            accent_font = QFont("Arial", accent_font_size, QFont.Bold)
            painter.setPen(self.accent_color)
            painter.setFont(accent_font)
            accent_offset_x = int(round(self._scaled(5) * self.note_scale))
            accent_offset_y = int(round(self._scaled(15) * self.note_scale))
            accent_width = int(round(self._scaled(10) * self.note_scale))
            accent_height = int(round(self._scaled(12) * self.note_scale))
            painter.drawText(
                x - accent_offset_x,
                y - (self.note_size + accent_offset_y),
                accent_width,
                accent_height,
                Qt.AlignCenter,
                ">"
            )

        hand = self._normalize_hand(getattr(note, "hand", None))
        if hand:
            self._draw_hand_marker(painter, x, y, hand)

        if self._is_thirty_second_note(note):
            dot_radius = max(2, int(round(self.note_size * 0.35)))
            painter.setPen(Qt.NoPen)
            painter.setBrush(self.thirty_second_dot_color)
            painter.drawEllipse(x - dot_radius, y - dot_radius, dot_radius * 2, dot_radius * 2)

    def _draw_time_signature(self, painter: QPainter, x: int, y_center: int):
        """Draw time signature at the beginning."""
        if not self.current_groove:
            return

        painter.setPen(self.text_color)
        font = QFont("Arial", self._scaled(14), QFont.Bold)
        painter.setFont(font)

        # Draw as fraction (4/4, 3/4, etc.)
        num_width = self._scaled(20)
        num_height = self._scaled(15)
        top_offset = self._scaled(20)
        bottom_offset = self._scaled(5)
        painter.drawText(
            x,
            y_center - top_offset,
            num_width,
            num_height,
            Qt.AlignCenter,
            str(self.current_groove.beats_per_bar)
        )
        painter.drawText(
            x,
            y_center + bottom_offset,
            num_width,
            num_height,
            Qt.AlignCenter,
            "4"
        )

    def _draw_bar_range(self, painter: QPainter, w: int, bars_in_groove: int, display_bars: int, base_bar: int):
        """Draw which bars of the groove are currently visible."""
        if bars_in_groove <= 1:
            return

        if display_bars <= 1:
            label = f"Bar {base_bar + 1}"
        else:
            start = base_bar + 1
            end = base_bar + display_bars
            label = f"Bars {start}-{end}"

        font = QFont("Arial", self._scaled(9), QFont.Bold)
        painter.setFont(font)
        painter.setPen(self.bar_range_color)

        metrics = painter.fontMetrics()
        text_width = metrics.horizontalAdvance(label)
        text_height = metrics.height()
        padding = self._scaled(8)
        rect = QRect(
            max(self._scaled(10), w - text_width - padding),
            self._scaled(6),
            text_width + padding,
            text_height
        )
        painter.drawText(rect, Qt.AlignRight | Qt.AlignVCenter, label)

    def _get_subdivision_label(self, subdivision: int, subdivisions_per_beat: int,
                               grid_subdivision: int) -> str:
        if subdivision <= 0:
            return ""

        label_map = {
            2: {1: "+"},
            3: {1: "trip", 2: "let"},
            4: {1: "e", 2: "+", 3: "a"},
        }
        if grid_subdivision <= 0:
            grid_subdivision = subdivisions_per_beat
        if subdivisions_per_beat % grid_subdivision != 0:
            grid_subdivision = subdivisions_per_beat

        step = subdivisions_per_beat // grid_subdivision if grid_subdivision > 0 else 0
        if step <= 0 or subdivision % step != 0:
            return ""

        grid_index = subdivision // step
        labels = label_map.get(grid_subdivision)
        if labels:
            return labels.get(grid_index, "")
        return ""

    def _beat_has_triplet_overlay(self, groove_bar: int, beat: int,
                                  subdivisions_per_beat: int, grid_subdivision: int) -> bool:
        overlays = getattr(self.current_groove, "triplet_overlays", None) or []
        if (groove_bar, beat) in overlays:
            return True

        if grid_subdivision <= 0:
            grid_subdivision = subdivisions_per_beat
        if subdivisions_per_beat % grid_subdivision != 0:
            grid_subdivision = subdivisions_per_beat
        grid_step = subdivisions_per_beat // grid_subdivision if grid_subdivision > 0 else 0
        triplet_step = subdivisions_per_beat // 3 if subdivisions_per_beat % 3 == 0 else 0
        if grid_step <= 0 or triplet_step <= 0:
            return False

        for note in self.current_groove.get_notes_for_beat(groove_bar, beat):
            if note.subdivision % triplet_step == 0 and note.subdivision % grid_step != 0:
                return True
        return False

    def _beat_has_thirty_second_overlay(self, groove_bar: int, beat: int,
                                        subdivisions_per_beat: int, grid_subdivision: int) -> bool:
        overlays = getattr(self.current_groove, "thirty_second_overlays", None) or []
        if (groove_bar, beat) in overlays:
            return True

        if grid_subdivision <= 0:
            grid_subdivision = subdivisions_per_beat
        if subdivisions_per_beat % grid_subdivision != 0:
            grid_subdivision = subdivisions_per_beat
        sixteenth_step = subdivisions_per_beat // 4 if subdivisions_per_beat % 4 == 0 else 0
        thirty_second_step = subdivisions_per_beat // 8 if subdivisions_per_beat % 8 == 0 else 0
        if sixteenth_step <= 0 or thirty_second_step <= 0:
            return False

        for note in self.current_groove.get_notes_for_beat(groove_bar, beat):
            if note.subdivision % thirty_second_step == 0 and note.subdivision % sixteenth_step != 0:
                return True
        return False

    def _is_thirty_second_note(self, note: DrumNote) -> bool:
        if not self.current_groove:
            return False
        subdivisions_per_beat = self.current_groove.subdivision
        if subdivisions_per_beat <= 0:
            return False
        sixteenth_step = subdivisions_per_beat // 4 if subdivisions_per_beat % 4 == 0 else 0
        thirty_second_step = subdivisions_per_beat // 8 if subdivisions_per_beat % 8 == 0 else 0
        if sixteenth_step <= 0 or thirty_second_step <= 0:
            return False
        if note.subdivision % thirty_second_step != 0:
            return False
        return note.subdivision % sixteenth_step != 0

    def _draw_triplet_divisions(self, painter: QPainter, staff_x: int, y_center: int,
                                subdivision_width: float, display_bars: int, base_bar: int):
        if not self.current_groove:
            return

        subdivisions_per_beat = self.current_groove.subdivision
        grid_subdivision = getattr(self.current_groove, "grid_subdivision", None) or subdivisions_per_beat
        show_all = grid_subdivision == 3
        if subdivisions_per_beat <= 0:
            return
        beat_width = subdivisions_per_beat * subdivision_width
        if beat_width <= 0:
            return
        triplet_offset = beat_width / 3.0
        subdivisions_per_bar = self.current_groove.beats_per_bar * subdivisions_per_beat
        bars_in_groove = max(1, self.current_groove.bars)

        y_top = y_center - 2 * self.staff_line_spacing
        y_bottom = y_center + 2 * self.staff_line_spacing

        painter.setPen(QPen(self.triplet_line_color, self._scaled(1), Qt.DashLine))

        for bar in range(display_bars):
            if bars_in_groove == 1:
                groove_bar = 0
            else:
                groove_bar = base_bar + bar
            for beat in range(self.current_groove.beats_per_bar):
                if not show_all:
                    if not self._beat_has_triplet_overlay(
                        groove_bar, beat, subdivisions_per_beat, grid_subdivision
                    ):
                        continue
                beat_x = staff_x + (
                    (bar * subdivisions_per_bar + beat * subdivisions_per_beat) * subdivision_width
                )
                x0 = beat_x
                x1 = beat_x + triplet_offset
                x2 = beat_x + triplet_offset * 2
                painter.drawLine(int(round(x0)), y_top, int(round(x0)), y_bottom)
                painter.drawLine(int(round(x1)), y_top, int(round(x1)), y_bottom)
                painter.drawLine(int(round(x2)), y_top, int(round(x2)), y_bottom)

    def _draw_thirty_second_divisions(self, painter: QPainter, staff_x: int, y_center: int,
                                      subdivision_width: float, display_bars: int, base_bar: int):
        if not self.current_groove:
            return

        subdivisions_per_beat = self.current_groove.subdivision
        if subdivisions_per_beat <= 0:
            return
        subdivisions_per_bar = self.current_groove.beats_per_bar * subdivisions_per_beat
        bars_in_groove = max(1, self.current_groove.bars)

        y_top = y_center - 2 * self.staff_line_spacing
        y_bottom = y_center + 2 * self.staff_line_spacing

        painter.setPen(QPen(self.thirty_second_line_color, self._scaled(1), Qt.DotLine))

        for bar in range(display_bars):
            if bars_in_groove == 1:
                groove_bar = 0
            else:
                groove_bar = base_bar + bar
            for beat in range(self.current_groove.beats_per_bar):
                note_subdivs = []
                for note in self.current_groove.get_notes_for_beat(groove_bar, beat):
                    if not self._is_thirty_second_note(note):
                        continue
                    note_subdivs.append(note.subdivision)

                if not note_subdivs:
                    continue

                beat_x = staff_x + (
                    (bar * subdivisions_per_bar + beat * subdivisions_per_beat) * subdivision_width
                )
                for subdiv in sorted(set(note_subdivs)):
                    x = beat_x + subdiv * subdivision_width
                    painter.drawLine(int(round(x)), y_top, int(round(x)), y_bottom)

    def _draw_rhythmic_notation(self, painter: QPainter, staff_x: int, y_center: int,
                                subdivision_width: float, bars_visible: int = None):
        """Draw beat counts and subdivision labels above the staff."""
        if not self.current_groove:
            return
        if bars_visible is None:
            bars_visible = self.bars_visible

        beat_font = QFont("Arial", self._scaled(10), QFont.Bold)
        subdiv_font = QFont("Arial", self._scaled(8))
        painter.setFont(beat_font)
        beat_height = painter.fontMetrics().height()
        painter.setFont(subdiv_font)
        subdiv_height = painter.fontMetrics().height()
        text_height = max(beat_height, subdiv_height)

        y_top = y_center - 2 * self.staff_line_spacing
        label_y = y_top - text_height - self._scaled(6)
        label_y += int(round(self.rhythm_text_offset * self.staff_line_spacing))
        min_label_y = self._scaled(6)
        if label_y < min_label_y:
            label_y = min_label_y

        subdivisions_per_beat = self.current_groove.subdivision
        grid_subdivision = getattr(self.current_groove, "grid_subdivision", None) or subdivisions_per_beat
        subdivisions_per_bar = self.current_groove.beats_per_bar * subdivisions_per_beat

        for bar in range(bars_visible):
            for beat in range(self.current_groove.beats_per_bar):
                for subdiv in range(subdivisions_per_beat):
                    position = bar * subdivisions_per_bar + beat * subdivisions_per_beat + subdiv
                    x = staff_x + position * subdivision_width + subdivision_width / 2
                    rect = QRect(int(x - subdivision_width / 2), int(label_y),
                                 int(subdivision_width), int(text_height))

                    if subdiv == 0:
                        painter.setPen(self.rhythm_beat_color)
                        painter.setFont(beat_font)
                        painter.drawText(rect, Qt.AlignCenter, str(beat + 1))
                        continue

                    label = self._get_subdivision_label(subdiv, subdivisions_per_beat, grid_subdivision)
                    if label:
                        painter.setPen(self.rhythm_subdiv_color)
                        painter.setFont(subdiv_font)
                        painter.drawText(rect, Qt.AlignCenter, label)
                    else:
                        painter.setPen(self.rhythm_subdiv_color)
                        tick_y = int(label_y + text_height // 2)
                        tick_half = self._scaled(2)
                        painter.drawLine(int(x), tick_y - tick_half, int(x), tick_y + tick_half)

    def _draw_bar_lines(self, painter: QPainter, x: int, y_center: int):
        """Draw a bar line."""
        painter.setPen(QPen(self._staff_pen_color(), self._scaled(2)))
        y_top = y_center - 2 * self.staff_line_spacing
        y_bottom = y_center + 2 * self.staff_line_spacing
        painter.drawLine(x, y_top, x, y_bottom)

    def _draw_playhead(self, painter: QPainter, x: int, y_center: int):
        """Draw the playhead indicator."""
        painter.setPen(QPen(self.playhead_color, self._scaled(3)))
        playhead_pad = self._scaled(10)
        y_top = y_center - 2 * self.staff_line_spacing - playhead_pad
        y_bottom = y_center + 2 * self.staff_line_spacing + playhead_pad
        painter.drawLine(x, y_top, x, y_bottom)

    def _scroll_cache_signature(
        self,
        render_bars: int,
        base_bar: int,
        staff_width: int,
        y_center: int,
        total_subdivisions: int,
    ) -> tuple:
        groove = self.current_groove
        grid_subdivision = getattr(groove, "grid_subdivision", None) if groove else None
        return (
            id(groove),
            self.width(),
            self.height(),
            self.ui_scale,
            self.note_scale,
            self.rhythm_text_offset,
            self._scroll_staff,
            self.bars_visible,
            render_bars,
            base_bar,
            staff_width,
            y_center,
            total_subdivisions,
            groove.beats_per_bar if groove else 0,
            groove.subdivision if groove else 0,
            groove.bars if groove else 0,
            grid_subdivision,
            self._ladder_final,
        )

    def _build_scroll_cache(
        self,
        render_bars: int,
        base_bar: int,
        y_center: int,
        subdivision_width: float,
        subdivisions_per_bar: int,
        bars_in_groove: int,
    ) -> QPixmap:
        width = int(round(render_bars * subdivisions_per_bar * subdivision_width))
        height = max(1, self.height())
        width = max(1, width)

        pixmap = QPixmap(width, height)
        pixmap.fill(Qt.transparent)

        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)

        self._draw_time_signature(painter, int(round(self._scaled(5))), y_center)
        self._draw_rhythmic_notation(painter, 0, y_center, subdivision_width, render_bars)
        self._draw_triplet_divisions(painter, 0, y_center, subdivision_width, render_bars, base_bar)
        self._draw_thirty_second_divisions(painter, 0, y_center, subdivision_width, render_bars, base_bar)

        for bar in range(render_bars + 1):
            bar_x = int(round(bar * subdivisions_per_bar * subdivision_width))
            self._draw_bar_lines(painter, bar_x, y_center)

        subdivisions_per_beat = self.current_groove.subdivision
        if bars_in_groove == 1:
            for display_bar in range(render_bars):
                for note in self.current_groove.notes:
                    position = (
                        display_bar * subdivisions_per_bar +
                        note.beat * subdivisions_per_beat +
                        note.subdivision
                    )
                    note_x = int(round(position * subdivision_width + subdivision_width / 2.0))
                    self._draw_note(painter, note_x, y_center, note, False)
        else:
            for note in self.current_groove.notes:
                note_bar = getattr(note, "bar", 0)
                rel_bar = note_bar - base_bar
                if rel_bar < 0 or rel_bar >= render_bars:
                    continue
                position = (
                    rel_bar * subdivisions_per_bar +
                    note.beat * subdivisions_per_beat +
                    note.subdivision
                )
                note_x = int(round(position * subdivision_width + subdivision_width / 2.0))
                self._draw_note(painter, note_x, y_center, note, False)

        painter.end()
        return pixmap

    def _draw_active_notes(
        self,
        painter: QPainter,
        staff_content_x: float,
        y_center: int,
        subdivisions_per_bar: int,
        subdivision_width: float,
        render_bars: int,
        base_bar: int,
        bars_in_groove: int,
        active_bar: int,
    ):
        if not self.current_groove or not self.active_notes or not self.is_playing:
            return

        subdivisions_per_beat = self.current_groove.subdivision
        if bars_in_groove == 1:
            if active_bar < 0 or active_bar >= render_bars:
                return
            for note in self.active_notes:
                position = (
                    active_bar * subdivisions_per_bar +
                    note.beat * subdivisions_per_beat +
                    note.subdivision
                )
                note_x = int(round(
                    staff_content_x + position * subdivision_width + subdivision_width / 2.0
                ))
                self._draw_note(painter, note_x, y_center, note, True)
        else:
            for note in self.active_notes:
                note_bar = getattr(note, "bar", 0)
                rel_bar = note_bar - base_bar
                if rel_bar < 0 or rel_bar >= render_bars:
                    continue
                position = (
                    rel_bar * subdivisions_per_bar +
                    note.beat * subdivisions_per_beat +
                    note.subdivision
                )
                note_x = int(round(
                    staff_content_x + position * subdivision_width + subdivision_width / 2.0
                ))
                self._draw_note(painter, note_x, y_center, note, True)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        # Fill background
        bg_color = self.base_bg_color
        if self._ladder_warning:
            if self._ladder_pulse > 0.0:
                bg_color = self._blend_color(self.warning_bg_color, self.warning_pulse_color, self._ladder_pulse)
            else:
                bg_color = self.warning_bg_color
        painter.fillRect(self.rect(), bg_color)

        if not self.current_groove:
            # Draw "No groove loaded" message
            painter.setPen(self.text_color)
            font = QFont("Arial", self._scaled(16))
            painter.setFont(font)
            painter.drawText(self.rect(), Qt.AlignCenter, "No groove loaded")
            return

        # Calculate layout
        w = self.width()

        # Top-align the staff while reserving room for rhythm labels.
        beat_font = QFont("Arial", self._scaled(10), QFont.Bold)
        subdiv_font = QFont("Arial", self._scaled(8))
        painter.setFont(beat_font)
        beat_height = painter.fontMetrics().height()
        painter.setFont(subdiv_font)
        subdiv_height = painter.fontMetrics().height()
        label_height = max(beat_height, subdiv_height)
        label_gap = self._scaled(6)
        top_margin = self._scaled(6)
        rhythm_offset_px = int(round(self.rhythm_text_offset * self.staff_line_spacing))

        min_voice_pos = min(self.voice_positions.values()) if self.voice_positions else 0.0
        note_head_clearance = 0
        if min_voice_pos <= -2.0:
            note_up = (-2.0 - min_voice_pos) * self.staff_line_spacing
            note_head_clearance = int(round(note_up + self.note_size))

        label_clearance = label_height + label_gap - min(0, rhythm_offset_px)
        required_above = max(label_clearance, note_head_clearance)
        y_center = int(round(top_margin + required_above + 2 * self.staff_line_spacing))

        # Center the staff horizontally while preserving space for labels.
        label_offset_x = self._scaled(50)
        min_edge_padding = max(label_offset_x, self._scaled(20))
        staff_width = max(1, w - 2 * min_edge_padding)
        staff_x = int(round((w - staff_width) / 2))

        # Calculate spacing
        bars_in_groove = max(1, self.current_groove.bars)
        if bars_in_groove == 1:
            visible_bars = self.bars_visible
        else:
            visible_bars = min(self.bars_visible, bars_in_groove)

        render_bars = (
            bars_in_groove if (self._scroll_staff and bars_in_groove > 1) else visible_bars
        )

        total_subdivisions = self.current_groove.beats_per_bar * self.current_groove.subdivision * visible_bars
        if total_subdivisions == 0:
            total_subdivisions = 1
        subdivision_width = staff_width / total_subdivisions  # Use float division for accuracy

        # Current position in subdivisions (relative to rendered bars)
        base_bar = 0
        which_display_bar = 0
        if self.is_playing:
            if bars_in_groove == 1:
                which_display_bar = self.current_bar % visible_bars
            else:
                bar_in_groove = self.current_bar % bars_in_groove
                if not self._scroll_staff and bars_in_groove > visible_bars:
                    base_bar = min(
                        (bar_in_groove // visible_bars) * visible_bars,
                        bars_in_groove - visible_bars
                    )
                which_display_bar = bar_in_groove - base_bar

        current_position = (
            which_display_bar * self.current_groove.beats_per_bar * self.current_groove.subdivision +
            self.current_beat * self.current_groove.subdivision +
            self.current_subdivision
        ) if self.is_playing else 0

        progress = 0.0
        if (
            self.is_playing
            and self._step_duration_ms
            and self._last_position_time_ms is not None
        ):
            elapsed_ms = self._position_timer.elapsed() - self._last_position_time_ms
            if elapsed_ms > 0 and self._step_duration_ms > 0:
                progress = max(0.0, min(1.0, elapsed_ms / self._step_duration_ms))
        if not self._scroll_staff:
            progress = 0.0

        visual_position = current_position + progress if self.is_playing else current_position

        scroll_offset = 0.0
        if self.is_playing and self._scroll_staff:
            scroll_offset = (
                visual_position * subdivision_width +
                subdivision_width / 2.0 -
                staff_width / 2.0
            )
        staff_content_x = staff_x - scroll_offset

        # Draw staff lines
        self._draw_staff_lines(painter, staff_x, y_center, staff_width)

        # Draw voice labels
        self._draw_voice_labels(painter, staff_x, y_center)

        subdivisions_per_bar = self.current_groove.beats_per_bar * self.current_groove.subdivision
        cache_key = self._scroll_cache_signature(
            render_bars, base_bar, staff_width, y_center, total_subdivisions
        )
        if cache_key != self._scroll_cache_key:
            self._scroll_cache = self._build_scroll_cache(
                render_bars,
                base_bar,
                y_center,
                subdivision_width,
                subdivisions_per_bar,
                bars_in_groove,
            )
            self._scroll_cache_key = cache_key

        painter.save()
        painter.setClipRect(QRect(staff_x, 0, staff_width, self.height()))

        if self._scroll_cache:
            painter.drawPixmap(int(round(staff_content_x)), 0, self._scroll_cache)

        active_bar = which_display_bar if self.is_playing else -1
        self._draw_active_notes(
            painter,
            staff_content_x,
            y_center,
            subdivisions_per_bar,
            subdivision_width,
            render_bars,
            base_bar,
            bars_in_groove,
            active_bar,
        )

        painter.restore()

        # Draw playhead
        if self.is_playing:
            if self._scroll_staff:
                playhead_x = int(round(staff_x + staff_width / 2.0))
            else:
                playhead_x = int(round(
                    staff_content_x +
                    visual_position * subdivision_width +
                    subdivision_width / 2.0
                ))
            self._draw_playhead(painter, playhead_x, y_center)

        # Draw bar range indicator (top-right)
        self._draw_bar_range(painter, w, bars_in_groove, render_bars, base_bar)

    def _staff_pen_color(self) -> QColor:
        if self._ladder_final:
            return self.ladder_final_staff_color
        return self.staff_color
