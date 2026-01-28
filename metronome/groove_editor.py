import math

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QPushButton,
    QComboBox, QSpinBox, QGroupBox, QWidget, QCheckBox, QScrollArea,
    QLineEdit, QMessageBox
)
from PyQt5.QtGui import QPainter, QColor, QPen, QBrush, QMouseEvent
from typing import Dict, Tuple, Optional, List, Set
from .groove import DrumGroove, DrumNote, GrooveLibrary


class NoteGridWidget(QWidget):
    """
    A grid widget for programming drum notes.
    Rows = drum voices, Columns = subdivisions
    """

    noteToggled = pyqtSignal(str, int, int, int, bool)  # voice, bar, beat, tick, state

    def __init__(self, parent=None):
        super().__init__(parent)
        self.base_min_width = 800
        self.base_min_height = 400

        # Grid data: Dict[(voice, bar, beat, tick)] = (accent, hand)
        self.notes: Dict[Tuple[str, int, int, int], Tuple[bool, Optional[str]]] = {}

        # Grid settings
        self.voices = [
            'crash', 'ride', 'hihat_closed', 'hihat_open',
            'tom1', 'snare', 'tom2', 'tom3', 'kick'
        ]
        self.voice_labels = [
            'Crash', 'Ride', 'HH Closed', 'HH Open',
            'Tom 1', 'Snare', 'Tom 2', 'Tom 3', 'Kick'
        ]
        self.beats_per_bar = 4
        self.subdivision = 4  # Grid subdivisions per beat (16th notes by default)
        self.ticks_per_beat = self.subdivision
        self.bars = 1
        self.triplet_overlays: Set[Tuple[int, int]] = set()
        self.thirty_second_overlays: Set[Tuple[int, int]] = set()
        self.triplet_edit_mode = False
        self.thirty_second_edit_mode = False

        # Colors
        self.bg_color = QColor("#1a1a1a")
        self.grid_color = QColor("#333333")
        self.note_color = QColor("#0d6efd")
        self.accent_color = QColor("#ff4d4d")
        self.beat_line_color = QColor("#555555")
        self.bar_line_color = QColor("#666666")
        self.text_color = QColor("#e0e0e0")
        self.triplet_line_color = QColor("#6ad1c0")
        self.thirty_second_line_color = QColor("#f28e2b")
        self.thirty_second_dot_color = QColor("#ff4d4d")

        # Interaction
        self.cell_width = 30
        self.cell_height = 40
        self.label_width = 80
        self._sync_minimum_size()

    def set_grid_size(self, beats: int, subdivision: int, bars: int = 1):
        """Set the grid dimensions."""
        self.beats_per_bar = beats
        self.subdivision = subdivision
        self.ticks_per_beat = subdivision
        self.bars = max(1, bars)
        self.notes.clear()
        self.triplet_overlays.clear()
        self.thirty_second_overlays.clear()
        self.update()
        self.updateGeometry()
        self._sync_minimum_size()

    def load_groove(self, groove: DrumGroove):
        """Load notes from a groove."""
        self.beats_per_bar = groove.beats_per_bar
        grid_subdiv = groove.grid_subdivision or groove.subdivision
        if groove.subdivision % max(1, grid_subdiv) != 0:
            grid_subdiv = groove.subdivision
        self.subdivision = grid_subdiv
        self.ticks_per_beat = groove.subdivision
        self.bars = max(1, groove.bars)
        self.notes.clear()
        self.triplet_overlays.clear()
        self.thirty_second_overlays.clear()

        for note in groove.notes:
            voice = note.voice
            if voice == "hihat":
                voice = "hihat_closed"
            if voice not in self.voices:
                continue
            key = (voice, note.bar, note.beat, note.subdivision)
            self.notes[key] = (note.accent, self._normalize_hand(note.hand))

        if groove.triplet_overlays:
            for bar, beat in groove.triplet_overlays:
                if 0 <= bar < self.bars and 0 <= beat < self.beats_per_bar:
                    self.triplet_overlays.add((bar, beat))

        if groove.thirty_second_overlays:
            for bar, beat in groove.thirty_second_overlays:
                if 0 <= bar < self.bars and 0 <= beat < self.beats_per_bar:
                    self.thirty_second_overlays.add((bar, beat))

        self.update()
        self.updateGeometry()
        self._sync_minimum_size()

    def get_groove_notes(self) -> List[DrumNote]:
        """Export current grid as DrumNote list."""
        notes = []
        for (voice, bar, beat, tick), (accent, hand) in self.notes.items():
            if voice not in self.voices:
                continue
            notes.append(DrumNote(voice, beat, tick, accent, bar, hand=hand))
        return notes

    def get_compact_groove_data(self) -> Tuple[
        List[DrumNote], int, List[Tuple[int, int]], List[Tuple[int, int]]
    ]:
        """Export notes and resolution, compacting to grid ticks when possible."""
        triplet_overlays = self.get_triplet_overlays()
        thirty_second_overlays = self.get_thirty_second_overlays()
        grid_step = self._grid_tick_step()
        has_overlays = bool(triplet_overlays or thirty_second_overlays)
        if not has_overlays and grid_step > 1:
            for (_, _, _, tick) in self.notes.keys():
                if tick % grid_step != 0:
                    has_overlays = True
                    break

        can_compact = (
            not has_overlays and
            self.ticks_per_beat != self.subdivision and
            self.subdivision > 0 and
            self.ticks_per_beat % self.subdivision == 0
        )
        factor = self.ticks_per_beat // self.subdivision if can_compact else 1
        if can_compact:
            for (_, _, _, tick) in self.notes.keys():
                if tick % factor != 0:
                    can_compact = False
                    factor = 1
                    break

        target_ticks = self.subdivision if can_compact else self.ticks_per_beat
        notes = []
        for (voice, bar, beat, tick), (accent, hand) in self.notes.items():
            if voice not in self.voices:
                continue
            if can_compact:
                tick = tick // factor
            notes.append(DrumNote(voice, beat, tick, accent, bar, hand=hand))
        return notes, target_ticks, triplet_overlays, thirty_second_overlays

    def clear_all(self):
        """Clear all notes."""
        self.notes.clear()
        self.triplet_overlays.clear()
        self.thirty_second_overlays.clear()
        self.update()

    def sizeHint(self):
        total_subdivs = self.beats_per_bar * self.subdivision * max(1, self.bars)
        width = self.label_width + total_subdivs * self.cell_width + 40
        height = len(self.voices) * self.cell_height + 60
        from PyQt5.QtCore import QSize
        return QSize(width, height)

    def _sync_minimum_size(self):
        size_hint = self.sizeHint()
        min_width = max(self.base_min_width, size_hint.width())
        min_height = max(self.base_min_height, size_hint.height())
        self.setMinimumSize(min_width, min_height)

    def set_triplet_edit_mode(self, enabled: bool):
        self.triplet_edit_mode = bool(enabled)

    def set_thirty_second_edit_mode(self, enabled: bool):
        self.thirty_second_edit_mode = bool(enabled)

    def set_triplet_overlays(self, overlays: List[Tuple[int, int]]):
        self.triplet_overlays.clear()
        for bar, beat in overlays:
            self.triplet_overlays.add((int(bar), int(beat)))
        self.update()

    def set_thirty_second_overlays(self, overlays: List[Tuple[int, int]]):
        self.thirty_second_overlays.clear()
        for bar, beat in overlays:
            self.thirty_second_overlays.add((int(bar), int(beat)))
        self.update()

    def get_triplet_overlays(self) -> List[Tuple[int, int]]:
        return sorted(self.triplet_overlays)

    def get_thirty_second_overlays(self) -> List[Tuple[int, int]]:
        return sorted(self.thirty_second_overlays)

    def get_ticks_per_beat(self) -> int:
        return self.ticks_per_beat

    @staticmethod
    def _lcm(a: int, b: int) -> int:
        if a <= 0 or b <= 0:
            return 0
        return abs(a * b) // math.gcd(a, b)

    def _grid_tick_step(self) -> int:
        if self.subdivision <= 0:
            return 1
        return max(1, self.ticks_per_beat // self.subdivision)

    def _triplet_tick_step(self) -> int:
        if self.ticks_per_beat <= 0:
            return 0
        if self.ticks_per_beat % 3 != 0:
            return 0
        return self.ticks_per_beat // 3

    def _thirty_second_tick_step(self) -> int:
        if self.ticks_per_beat <= 0:
            return 0
        if self.ticks_per_beat % 8 != 0:
            return 0
        return self.ticks_per_beat // 8

    def _sixteenth_tick_step(self) -> int:
        if self.ticks_per_beat <= 0:
            return 0
        if self.ticks_per_beat % 4 != 0:
            return 0
        return self.ticks_per_beat // 4

    def _is_grid_tick(self, tick: int) -> bool:
        step = self._grid_tick_step()
        return step > 0 and tick % step == 0

    def _beat_has_triplet_notes(self, bar: int, beat: int) -> bool:
        grid_step = self._grid_tick_step()
        triplet_step = self._triplet_tick_step()
        if grid_step <= 0 or triplet_step <= 0:
            return False
        for (_, note_bar, note_beat, tick) in self.notes.keys():
            if note_bar == bar and note_beat == beat:
                if tick % triplet_step == 0 and tick % grid_step != 0:
                    return True
        return False

    def _beat_has_thirty_second_notes(self, bar: int, beat: int) -> bool:
        sixteenth_step = self._sixteenth_tick_step()
        thirty_second_step = self._thirty_second_tick_step()
        if sixteenth_step <= 0 or thirty_second_step <= 0:
            return False
        for (_, note_bar, note_beat, tick) in self.notes.keys():
            if note_bar == bar and note_beat == beat:
                if tick % thirty_second_step == 0 and tick % sixteenth_step != 0:
                    return True
        return False

    def _beat_has_triplet_overlay(self, bar: int, beat: int) -> bool:
        return (bar, beat) in self.triplet_overlays or self._beat_has_triplet_notes(bar, beat)

    def _beat_has_thirty_second_overlay(self, bar: int, beat: int) -> bool:
        return (
            (bar, beat) in self.thirty_second_overlays or
            self._beat_has_thirty_second_notes(bar, beat)
        )

    def _is_thirty_second_only_tick(self, tick: int) -> bool:
        sixteenth_step = self._sixteenth_tick_step()
        thirty_second_step = self._thirty_second_tick_step()
        if sixteenth_step <= 0 or thirty_second_step <= 0:
            return False
        if tick % thirty_second_step != 0:
            return False
        return tick % sixteenth_step != 0

    def _note_center_x(self, bar: int, beat: int, tick: int, margin_left: int) -> int:
        beat_width = self.subdivision * self.cell_width
        beat_offset = (bar * self.beats_per_bar + beat) * beat_width
        base_x = margin_left + beat_offset

        grid_step = self._grid_tick_step()
        if grid_step > 0 and tick % grid_step == 0:
            grid_idx = tick // grid_step
            return int(round(base_x + (grid_idx + 0.5) * self.cell_width))

        triplet_step = self._triplet_tick_step()
        if triplet_step > 0 and tick % triplet_step == 0:
            triplet_idx = tick // triplet_step
            triplet_width = beat_width / 3.0
            return int(round(base_x + (triplet_idx + 0.5) * triplet_width))

        thirty_second_step = self._thirty_second_tick_step()
        if thirty_second_step > 0 and tick % thirty_second_step == 0:
            thirty_second_idx = tick // thirty_second_step
            thirty_second_width = beat_width / 8.0
            return int(round(base_x + (thirty_second_idx + 0.5) * thirty_second_width))

        return int(round(base_x + (tick + 0.5) * self.cell_width))

    def _ensure_resolution(self, divisor: int):
        if divisor <= 0:
            return
        base = self.ticks_per_beat if self.ticks_per_beat > 0 else self.subdivision
        target = self._lcm(base, divisor)
        if target <= 0:
            return
        if self.ticks_per_beat <= 0:
            self.ticks_per_beat = target
            return
        if target <= self.ticks_per_beat:
            return
        factor = target // self.ticks_per_beat
        if factor <= 1:
            self.ticks_per_beat = target
            return
        updated = {}
        for (voice, bar, beat, tick), state in self.notes.items():
            updated[(voice, bar, beat, tick * factor)] = state
        self.notes = updated
        self.ticks_per_beat = target

    def _ensure_triplet_resolution(self):
        self._ensure_resolution(3)

    def _ensure_thirty_second_resolution(self):
        self._ensure_resolution(8)

    def _maybe_reduce_resolution(self):
        if self.triplet_overlays or self.thirty_second_overlays:
            return
        step = self._grid_tick_step()
        if step <= 1:
            return
        for (_, _, _, tick) in self.notes.keys():
            if tick % step != 0:
                return
        updated = {}
        for (voice, bar, beat, tick), state in self.notes.items():
            updated[(voice, bar, beat, tick // step)] = state
        self.notes = updated
        self.ticks_per_beat = self.subdivision

    def _get_cell_at_pos(self, x: int, y: int) -> Optional[Tuple[str, int, int, int, float]]:
        """Get the cell (voice, bar, beat, grid_subdivision, x_in_beat) at pixel position."""
        # Account for margins
        x -= self.label_width + 20
        y -= 40

        if x < 0 or y < 0:
            return None

        col = x // self.cell_width
        row = y // self.cell_height

        if row < 0 or row >= len(self.voices):
            return None

        total_subdivs = self.beats_per_bar * self.subdivision * max(1, self.bars)
        if col < 0 or col >= total_subdivs:
            return None

        voice = self.voices[row]
        subdivs_per_bar = self.beats_per_bar * self.subdivision
        bar = col // subdivs_per_bar
        pos_in_bar = col % subdivs_per_bar
        beat = pos_in_bar // self.subdivision
        subdiv = pos_in_bar % self.subdivision
        beat_start = (bar * subdivs_per_bar + beat * self.subdivision) * self.cell_width
        x_in_beat = x - beat_start

        return (voice, bar, beat, subdiv, float(x_in_beat))

    def _get_beat_header_at_pos(self, x: int, y: int) -> Optional[Tuple[int, int]]:
        margin_top = 40
        margin_left = self.label_width + 20
        header_height = 30
        if y < margin_top - header_height or y > margin_top:
            return None
        x -= margin_left
        if x < 0:
            return None
        col = x // self.cell_width
        total_subdivs = self.beats_per_bar * self.subdivision * max(1, self.bars)
        if col < 0 or col >= total_subdivs:
            return None
        subdivs_per_bar = self.beats_per_bar * self.subdivision
        bar = col // subdivs_per_bar
        pos_in_bar = col % subdivs_per_bar
        beat = pos_in_bar // self.subdivision
        return (bar, beat)

    def _normalize_hand(self, hand: Optional[str]) -> Optional[str]:
        if not hand:
            return None
        hand = hand.upper()
        return hand if hand in ("L", "R") else None

    def mousePressEvent(self, event: QMouseEvent):
        """Handle mouse clicks to toggle notes."""
        header = self._get_beat_header_at_pos(event.x(), event.y())
        if header and event.button() == Qt.LeftButton:
            bar, beat = header
            if self.thirty_second_edit_mode:
                if (bar, beat) in self.thirty_second_overlays:
                    self.thirty_second_overlays.remove((bar, beat))
                    self._maybe_reduce_resolution()
                else:
                    self._ensure_thirty_second_resolution()
                    self.thirty_second_overlays.add((bar, beat))
            else:
                if (bar, beat) in self.triplet_overlays:
                    self.triplet_overlays.remove((bar, beat))
                    self._maybe_reduce_resolution()
                else:
                    self._ensure_triplet_resolution()
                    self.triplet_overlays.add((bar, beat))
            self.update()
            return

        cell = self._get_cell_at_pos(event.x(), event.y())
        if cell:
            voice, bar, beat, subdiv, x_in_beat = cell
            if self.thirty_second_edit_mode:
                self._ensure_thirty_second_resolution()
                self.thirty_second_overlays.add((bar, beat))
                beat_width = self.subdivision * self.cell_width
                if beat_width <= 0:
                    return
                thirty_second_step = self._thirty_second_tick_step()
                if thirty_second_step <= 0:
                    return
                thirty_second_width = beat_width / 8.0
                thirty_second_idx = int(x_in_beat // thirty_second_width)
                thirty_second_idx = max(0, min(7, thirty_second_idx))
                tick = thirty_second_idx * thirty_second_step
                if not self._is_thirty_second_only_tick(tick):
                    return
            elif self.triplet_edit_mode:
                self._ensure_triplet_resolution()
                self.triplet_overlays.add((bar, beat))
                beat_width = self.subdivision * self.cell_width
                if beat_width <= 0:
                    return
                triplet_step = self._triplet_tick_step()
                if triplet_step <= 0:
                    return
                triplet_width = beat_width / 3.0
                triplet_idx = int(x_in_beat // triplet_width)
                triplet_idx = max(0, min(2, triplet_idx))
                tick = triplet_idx * triplet_step
            else:
                grid_step = self._grid_tick_step()
                tick = subdiv * grid_step
            key = (voice, bar, beat, tick)

            if event.button() == Qt.LeftButton:
                # Cycle note: add -> L -> R -> delete
                if key not in self.notes:
                    self.notes[key] = (False, None)
                else:
                    accent, hand = self.notes[key]
                    hand = self._normalize_hand(hand)
                    if hand is None:
                        self.notes[key] = (accent, "L")
                    elif hand == "L":
                        self.notes[key] = (accent, "R")
                    else:
                        self.notes.pop(key, None)
                        self._maybe_reduce_resolution()
                self.update()

            elif event.button() == Qt.RightButton:
                # Toggle accent (if note exists)
                if key in self.notes:
                    accent, hand = self.notes[key]
                    self.notes[key] = (not accent, hand)
                    self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        # Fill background
        painter.fillRect(self.rect(), self.bg_color)

        margin_top = 40
        margin_left = self.label_width + 20

        subdivs_per_bar = self.beats_per_bar * self.subdivision
        total_subdivs = subdivs_per_bar * max(1, self.bars)
        grid_width = total_subdivs * self.cell_width
        grid_height = len(self.voices) * self.cell_height

        # Draw column headers (bar + beat numbers)
        painter.setPen(self.text_color)
        bar_label_y = margin_top - 40
        if self.bars > 1:
            for bar in range(self.bars):
                bar_x = margin_left + bar * subdivs_per_bar * self.cell_width
                painter.drawText(
                    bar_x,
                    bar_label_y,
                    subdivs_per_bar * self.cell_width,
                    16,
                    Qt.AlignCenter,
                    f"Bar {bar + 1}"
                )

        for bar in range(self.bars):
            bar_x = margin_left + bar * subdivs_per_bar * self.cell_width
            for beat in range(self.beats_per_bar):
                x = bar_x + beat * self.subdivision * self.cell_width
                if self._beat_has_thirty_second_overlay(bar, beat):
                    painter.setPen(self.thirty_second_line_color)
                elif self._beat_has_triplet_overlay(bar, beat):
                    painter.setPen(self.triplet_line_color)
                else:
                    painter.setPen(self.text_color)
                painter.drawText(x, margin_top - 25, self.subdivision * self.cell_width, 20,
                                Qt.AlignCenter, str(beat + 1))

        # Draw subdivision markers
        from PyQt5.QtGui import QFont
        font = QFont("Arial", 8)
        painter.setFont(font)
        subdiv_labels_map = {
            2: {1: '+'},
            3: {1: 'trip', 2: 'let'},
            4: {1: 'e', 2: '+', 3: 'a'},
        }
        subdiv_labels = subdiv_labels_map.get(self.subdivision, {})
        for i in range(total_subdivs):
            subdiv = i % self.subdivision
            if subdiv > 0:  # Don't label the beat itself
                x = margin_left + i * self.cell_width
                label = subdiv_labels.get(subdiv, '')
                if label:
                    painter.drawText(x, margin_top - 10, self.cell_width, 10,
                                    Qt.AlignCenter, label)

        # Draw grid lines
        painter.setPen(QPen(self.grid_color, 1))

        # Horizontal lines (voice separators)
        for i in range(len(self.voices) + 1):
            y = margin_top + i * self.cell_height
            painter.drawLine(margin_left, y, margin_left + grid_width, y)

        # Vertical lines
        for i in range(total_subdivs + 1):
            x = margin_left + i * self.cell_width
            if subdivs_per_bar > 0 and i % subdivs_per_bar == 0:
                painter.setPen(QPen(self.bar_line_color, 3))
            elif i % self.subdivision == 0:
                painter.setPen(QPen(self.beat_line_color, 2))
            else:
                painter.setPen(QPen(self.grid_color, 1))
            painter.drawLine(x, margin_top, x, margin_top + grid_height)

        # Draw triplet overlay lines
        if self.subdivision > 0:
            beat_width = self.subdivision * self.cell_width
            triplet_width = beat_width / 3.0
            triplet_pen = QPen(self.triplet_line_color, 1, Qt.DashLine)
            for bar in range(self.bars):
                for beat in range(self.beats_per_bar):
                    if not self._beat_has_triplet_overlay(bar, beat):
                        continue
                    beat_x = margin_left + (bar * subdivs_per_bar + beat * self.subdivision) * self.cell_width
                    painter.setPen(triplet_pen)
                    for t in (1, 2):
                        x = beat_x + t * triplet_width
                        painter.drawLine(int(round(x)), margin_top, int(round(x)), margin_top + grid_height)

        # Draw 32nd overlay lines
        if self.subdivision > 0:
            beat_width = self.subdivision * self.cell_width
            thirty_second_width = beat_width / 8.0
            thirty_second_pen = QPen(self.thirty_second_line_color, 1, Qt.DotLine)
            for bar in range(self.bars):
                for beat in range(self.beats_per_bar):
                    if not self._beat_has_thirty_second_overlay(bar, beat):
                        continue
                    beat_x = margin_left + (bar * subdivs_per_bar + beat * self.subdivision) * self.cell_width
                    painter.setPen(thirty_second_pen)
                    for t in range(8):
                        x = beat_x + t * thirty_second_width
                        painter.drawLine(int(round(x)), margin_top, int(round(x)), margin_top + grid_height)

        # Draw voice labels
        painter.setPen(self.text_color)
        font = QFont("Arial", 10)
        painter.setFont(font)
        for i, label in enumerate(self.voice_labels):
            y = margin_top + i * self.cell_height
            painter.drawText(10, y, self.label_width, self.cell_height,
                            Qt.AlignVCenter | Qt.AlignRight, label)

        # Draw notes
        for (voice, bar, beat, tick), (accent, hand) in self.notes.items():
            if voice not in self.voices:
                continue

            voice_idx = self.voices.index(voice)
            center_x = self._note_center_x(bar, beat, tick, margin_left)
            x = int(round(center_x - self.cell_width / 2))
            y = margin_top + voice_idx * self.cell_height

            # Draw filled circle for note
            color = self.accent_color if accent else self.note_color
            painter.setBrush(QBrush(color))
            painter.setPen(QPen(color, 2))

            center_y = y + self.cell_height // 2
            radius = 8

            painter.drawEllipse(center_x - radius, center_y - radius, radius * 2, radius * 2)

            hand = self._normalize_hand(hand)
            if hand:
                painter.setPen(self.text_color)
                font_hand = QFont("Arial", 16, QFont.Bold)
                painter.setFont(font_hand)
                painter.drawText(x, y, self.cell_width, self.cell_height, Qt.AlignCenter, hand)

            # Draw accent marker if needed
            if accent:
                painter.setPen(QPen(self.accent_color, 2))
                font_accent = QFont("Arial", 10, QFont.Bold)
                painter.setFont(font_accent)
                painter.drawText(x, y + 5, self.cell_width, 15, Qt.AlignCenter, ">")

            if self._is_thirty_second_only_tick(tick):
                dot_radius = 3
                painter.setPen(Qt.NoPen)
                painter.setBrush(self.thirty_second_dot_color)
                painter.drawEllipse(center_x - dot_radius, center_y - dot_radius,
                                    dot_radius * 2, dot_radius * 2)

        # Draw instructions at bottom
        painter.setPen(self.text_color)
        font = QFont("Arial", 9)
        painter.setFont(font)
        instructions_y = margin_top + grid_height + 10
        painter.drawText(10, instructions_y, self.width() - 20, 30, Qt.AlignLeft,
                        "Left-click: Add -> L -> R -> Delete  |  Right-click: Toggle accent (red)  |  Beat label: Triplet/32nd overlay  |  Triplet Edit: add triplets  |  32nd Edit: add off-grid 32nds")


class GrooveEditorDialog(QDialog):
    """
    Modal dialog for creating and editing drum grooves.
    """

    grooveSaved = pyqtSignal(object)  # DrumGroove

    def __init__(self, library: GrooveLibrary, parent=None):
        super().__init__(parent)
        self.library = library
        self.current_groove = None

        self.setWindowTitle("Groove Editor")
        self.setModal(True)
        self.resize(1200, 1080)

        # Apply dark theme stylesheet
        self.setStyleSheet("""
            QDialog {
                background-color: #1a1a1a;
                color: #e0e0e0;
            }
            QLabel {
                color: #e0e0e0;
            }
            QPushButton {
                background-color: #0d6efd;
                border: none;
                border-radius: 8px;
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
            QComboBox, QSpinBox, QLineEdit {
                background-color: #2c2c2c;
                border: 1px solid #444;
                border-radius: 6px;
                padding: 6px;
                color: #fff;
            }
            QGroupBox {
                border: 1px solid #333;
                border-radius: 8px;
                margin-top: 12px;
                padding: 12px;
                color: #0d6efd;
                font-weight: bold;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top left;
                padding: 0 8px;
            }
        """)

        layout = QVBoxLayout(self)

        # Top controls
        top_group = QGroupBox("Groove Settings")
        top_layout = QGridLayout(top_group)

        # Groove selection
        top_layout.addWidget(QLabel("Load Preset:"), 0, 0)
        self.groove_combo = QComboBox()
        self.groove_combo.addItem("-- New Groove --")
        self.groove_combo.addItems(self.library.get_groove_names())
        self.groove_combo.currentTextChanged.connect(self._on_groove_selected)
        top_layout.addWidget(self.groove_combo, 0, 1)

        # Groove name
        top_layout.addWidget(QLabel("Name:"), 0, 2)
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("Enter groove name...")
        top_layout.addWidget(self.name_edit, 0, 3)

        # Time signature
        top_layout.addWidget(QLabel("Beats per Bar:"), 1, 0)
        self.beats_spin = QSpinBox()
        self.beats_spin.setRange(1, 12)
        self.beats_spin.setValue(4)
        self.beats_spin.valueChanged.connect(self._on_settings_changed)
        top_layout.addWidget(self.beats_spin, 1, 1)

        # Subdivision
        top_layout.addWidget(QLabel("Grid Subdivision:"), 1, 2)
        self.subdiv_combo = QComboBox()
        self.subdiv_combo.addItem("8th notes", 2)
        self.subdiv_combo.addItem("16th notes", 4)
        self.subdiv_combo.addItem("Triplets", 3)
        self.subdiv_combo.setCurrentIndex(1)  # Default to 16th
        self.subdiv_combo.currentIndexChanged.connect(self._on_settings_changed)
        top_layout.addWidget(self.subdiv_combo, 1, 3)

        # Bars
        top_layout.addWidget(QLabel("Bars:"), 2, 0)
        self.bars_spin = QSpinBox()
        self.bars_spin.setRange(1, 8)
        self.bars_spin.setValue(1)
        self.bars_spin.valueChanged.connect(self._on_settings_changed)
        top_layout.addWidget(self.bars_spin, 2, 1)

        top_layout.addWidget(QLabel("Triplet Edit:"), 2, 2)
        self.triplet_edit_check = QCheckBox("Enable")
        top_layout.addWidget(self.triplet_edit_check, 2, 3)

        top_layout.addWidget(QLabel("32nd Edit:"), 3, 2)
        self.thirty_second_edit_check = QCheckBox("Enable")
        top_layout.addWidget(self.thirty_second_edit_check, 3, 3)

        layout.addWidget(top_group)

        # Note grid (scrollable)
        grid_group = QGroupBox("Note Programming Grid")
        grid_layout = QVBoxLayout(grid_group)

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)

        self.note_grid = NoteGridWidget()
        self.triplet_edit_check.toggled.connect(self._on_triplet_edit_toggled)
        self.thirty_second_edit_check.toggled.connect(self._on_thirty_second_edit_toggled)
        scroll_area.setWidget(self.note_grid)

        grid_layout.addWidget(scroll_area)
        layout.addWidget(grid_group, 1)  # Give it stretch

        # Bottom controls
        button_layout = QHBoxLayout()

        self.clear_btn = QPushButton("Clear All")
        self.clear_btn.clicked.connect(self._clear_grid)
        button_layout.addWidget(self.clear_btn)

        button_layout.addStretch()

        self.save_btn = QPushButton("Save Groove")
        self.save_btn.clicked.connect(self._save_groove)
        button_layout.addWidget(self.save_btn)

        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(self.cancel_btn)

        layout.addLayout(button_layout)

    def _on_groove_selected(self, name: str):
        """Load a preset groove into the editor."""
        if name == "-- New Groove --":
            self._clear_grid()
            self.name_edit.clear()
            self.beats_spin.setValue(4)
            self.subdiv_combo.setCurrentIndex(1)
            self.bars_spin.setValue(1)
            self.triplet_edit_check.setChecked(False)
            self.thirty_second_edit_check.setChecked(False)
            return

        groove = self.library.get_groove_by_name(name)
        if groove:
            self.current_groove = groove
            self.name_edit.setText(groove.name)
            self.beats_spin.setValue(groove.beats_per_bar)

            # Set subdivision combo
            grid_subdiv = groove.grid_subdivision or groove.subdivision
            for i in range(self.subdiv_combo.count()):
                if self.subdiv_combo.itemData(i) == grid_subdiv:
                    self.subdiv_combo.setCurrentIndex(i)
                    break

            self.bars_spin.setValue(groove.bars)
            self.triplet_edit_check.setChecked(False)
            self.thirty_second_edit_check.setChecked(False)

            # Load into grid
            self.note_grid.load_groove(groove)

    def _on_settings_changed(self, *args):
        """Update grid when settings change."""
        beats = self.beats_spin.value()
        subdiv = self.subdiv_combo.currentData()
        bars = self.bars_spin.value()
        self.note_grid.set_grid_size(beats, subdiv, bars)
        enable_triplet_edit = subdiv in (2, 4)
        self.triplet_edit_check.setEnabled(enable_triplet_edit)
        if not enable_triplet_edit:
            self.triplet_edit_check.setChecked(False)
        enable_thirty_second_edit = subdiv in (2, 4)
        self.thirty_second_edit_check.setEnabled(enable_thirty_second_edit)
        if not enable_thirty_second_edit:
            self.thirty_second_edit_check.setChecked(False)

    def _on_triplet_edit_toggled(self, enabled: bool):
        if enabled and self.thirty_second_edit_check.isChecked():
            self.thirty_second_edit_check.blockSignals(True)
            self.thirty_second_edit_check.setChecked(False)
            self.thirty_second_edit_check.blockSignals(False)
            self.note_grid.set_thirty_second_edit_mode(False)
        self.note_grid.set_triplet_edit_mode(enabled)

    def _on_thirty_second_edit_toggled(self, enabled: bool):
        if enabled and self.triplet_edit_check.isChecked():
            self.triplet_edit_check.blockSignals(True)
            self.triplet_edit_check.setChecked(False)
            self.triplet_edit_check.blockSignals(False)
            self.note_grid.set_triplet_edit_mode(False)
        self.note_grid.set_thirty_second_edit_mode(enabled)

    def _clear_grid(self):
        """Clear all notes from the grid."""
        self.note_grid.clear_all()

    def _save_groove(self):
        """Save the current groove."""
        name = self.name_edit.text().strip()
        if not name:
            QMessageBox.warning(self, "Invalid Name", "Please enter a groove name.")
            return

        existing = self.library.get_groove_by_name(name)
        if existing is not None:
            reply = QMessageBox.question(
                self,
                "Overwrite Groove?",
                f"A groove named '{name}' already exists. Overwrite it?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )
            if reply != QMessageBox.Yes:
                return

        notes, ticks_per_beat, triplet_overlays, thirty_second_overlays = (
            self.note_grid.get_compact_groove_data()
        )
        if not notes:
            QMessageBox.warning(self, "Empty Groove", "Please add some notes to the groove.")
            return

        groove = DrumGroove(
            name=name,
            notes=notes,
            beats_per_bar=self.beats_spin.value(),
            bars=self.bars_spin.value(),
            subdivision=ticks_per_beat,
            grid_subdivision=self.subdiv_combo.currentData(),
            triplet_overlays=triplet_overlays,
            thirty_second_overlays=thirty_second_overlays,
        )

        try:
            self.library.save_groove(groove)
            self.grooveSaved.emit(groove)
            QMessageBox.information(self, "Success", f"Groove '{name}' saved successfully!")
            self.accept()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save groove: {e}")

    def load_groove_for_editing(self, groove: DrumGroove):
        """Load an existing groove for editing."""
        self.current_groove = groove
        self.name_edit.setText(groove.name)
        self.beats_spin.setValue(groove.beats_per_bar)

        for i in range(self.subdiv_combo.count()):
            if self.subdiv_combo.itemData(i) == groove.subdivision:
                self.subdiv_combo.setCurrentIndex(i)
                break

        self.bars_spin.setValue(groove.bars)
        self.note_grid.load_groove(groove)
