from PyQt5.QtCore import Qt, QRect, QTimer, pyqtSlot
from PyQt5.QtWidgets import QWidget
from PyQt5.QtGui import QPainter, QColor, QFont, QPen, QBrush
from typing import List, Optional
from .groove import DrumGroove, DrumNote


class DrumStaffWidget(QWidget):
    """
    A widget that displays a scrolling drum staff notation.
    Shows drum notation with different voices on appropriate staff positions.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(180)
        self.setMaximumHeight(300)

        # Current groove being displayed
        self.current_groove: Optional[DrumGroove] = None

        # Playback state
        self.current_bar = 0
        self.current_beat = 0
        self.current_subdivision = 0
        self.is_playing = False

        # Visual settings
        self.staff_color = QColor("#444444")
        self.note_color = QColor("#0d6efd")
        self.accent_color = QColor("#ff4d4d")
        self.playhead_color = QColor("#00ff00")
        self.bg_color = QColor("#1a1a1a")
        self.text_color = QColor("#e0e0e0")

        # Layout settings
        self.bars_visible = 2  # How many bars to show at once
        self.staff_line_spacing = 12  # Pixels between staff lines

        # Active notes (currently playing)
        self.active_notes: List[DrumNote] = []

        # Animation timer for smooth scrolling
        self.animation_timer = QTimer()
        self.animation_timer.timeout.connect(self.update)
        self.animation_timer.start(50)  # 20 FPS for smooth animation

    @pyqtSlot(object)
    def set_groove(self, groove: DrumGroove):
        """Set the groove to display."""
        self.current_groove = groove
        self.current_bar = 0
        self.current_beat = 0
        self.current_subdivision = 0
        self.update()

    @pyqtSlot(int, int, int)
    def set_position(self, bar: int, beat: int, subdivision: int):
        """Update the current playback position."""
        if self.current_groove:
            self.current_bar = bar % self.current_groove.bars
            self.current_beat = beat
            self.current_subdivision = subdivision
            self.update()

    @pyqtSlot(list)
    def set_active_notes(self, notes: List[DrumNote]):
        """Set which notes are currently playing (for highlighting)."""
        self.active_notes = notes
        self.update()

    @pyqtSlot(bool)
    def set_playing(self, playing: bool):
        """Set whether the groove is playing."""
        self.is_playing = playing
        self.update()

    def _get_voice_position(self, voice: str) -> int:
        """
        Get the vertical position for a drum voice.
        Returns a position relative to the staff (0 = middle line).
        """
        voice_map = {
            'crash': 4,    # Above staff
            'ride': 3,     # Top line
            'hihat': 3,    # Top line
            'tom1': 2,     # Second line
            'snare': 0,    # Middle line
            'tom2': -1,    # Fourth line
            'tom3': -2,    # Below staff
            'kick': -3,    # Below staff
        }
        return voice_map.get(voice, 0)

    def _get_voice_symbol(self, voice: str) -> str:
        """Get the symbol to draw for each voice."""
        symbol_map = {
            'crash': 'X',
            'ride': 'x',
            'hihat': 'x',
            'tom1': '●',
            'snare': '●',
            'tom2': '●',
            'tom3': '●',
            'kick': '●',
        }
        return symbol_map.get(voice, '●')

    def _draw_staff_lines(self, painter: QPainter, x: int, y_center: int, width: int):
        """Draw the 5-line staff."""
        painter.setPen(QPen(self.staff_color, 1))

        for i in range(-2, 3):  # 5 lines: -2, -1, 0, 1, 2
            y = y_center + i * self.staff_line_spacing
            painter.drawLine(x, y, x + width, y)

    def _draw_voice_labels(self, painter: QPainter, x: int, y_center: int):
        """Draw labels for drum voices on the left side."""
        painter.setPen(self.text_color)
        font = QFont("Arial", 9)
        painter.setFont(font)

        labels = [
            ('HH/Rd', 3),
            ('Snare', 0),
            ('Kick', -3),
        ]

        for label, position in labels:
            y = y_center + position * self.staff_line_spacing
            painter.drawText(x - 50, y - 8, 45, 16, Qt.AlignRight | Qt.AlignVCenter, label)

    def _draw_note(self, painter: QPainter, x: int, y_center: int, note: DrumNote, is_active: bool = False):
        """Draw a single note on the staff."""
        y_pos = self._get_voice_position(note.voice)
        y = y_center + y_pos * self.staff_line_spacing

        # Choose color
        if is_active:
            color = QColor("#00ff00")  # Green for active
        elif note.accent:
            color = self.accent_color
        else:
            color = self.note_color

        painter.setPen(QPen(color, 2))
        font = QFont("Arial", 14, QFont.Bold)
        painter.setFont(font)

        symbol = self._get_voice_symbol(note.voice)

        # Draw the symbol
        painter.drawText(x - 6, y - 10, 12, 20, Qt.AlignCenter, symbol)

        # Draw accent mark if needed (> symbol above note)
        if note.accent and not is_active:
            accent_font = QFont("Arial", 10, QFont.Bold)
            painter.setFont(accent_font)
            painter.drawText(x - 5, y - 22, 10, 12, Qt.AlignCenter, ">")

    def _draw_time_signature(self, painter: QPainter, x: int, y_center: int):
        """Draw time signature at the beginning."""
        if not self.current_groove:
            return

        painter.setPen(self.text_color)
        font = QFont("Arial", 14, QFont.Bold)
        painter.setFont(font)

        # Draw as fraction (4/4, 3/4, etc.)
        painter.drawText(x, y_center - 20, 20, 15, Qt.AlignCenter, str(self.current_groove.beats_per_bar))
        painter.drawText(x, y_center + 5, 20, 15, Qt.AlignCenter, "4")

    def _draw_bar_lines(self, painter: QPainter, x: int, y_center: int):
        """Draw a bar line."""
        painter.setPen(QPen(self.staff_color, 2))
        y_top = y_center - 2 * self.staff_line_spacing
        y_bottom = y_center + 2 * self.staff_line_spacing
        painter.drawLine(x, y_top, x, y_bottom)

    def _draw_playhead(self, painter: QPainter, x: int, y_center: int):
        """Draw the playhead indicator."""
        painter.setPen(QPen(self.playhead_color, 3))
        y_top = y_center - 2 * self.staff_line_spacing - 10
        y_bottom = y_center + 2 * self.staff_line_spacing + 10
        painter.drawLine(x, y_top, x, y_bottom)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        # Fill background
        painter.fillRect(self.rect(), self.bg_color)

        if not self.current_groove:
            # Draw "No groove loaded" message
            painter.setPen(self.text_color)
            font = QFont("Arial", 16)
            painter.setFont(font)
            painter.drawText(self.rect(), Qt.AlignCenter, "No groove loaded")
            return

        # Calculate layout
        w = self.width()
        h = self.height()
        y_center = h // 2

        # Margins
        left_margin = 80  # Space for labels
        right_margin = 20
        staff_width = w - left_margin - right_margin

        # Calculate spacing
        total_subdivisions = self.current_groove.beats_per_bar * self.current_groove.subdivision * self.bars_visible
        if total_subdivisions == 0:
            total_subdivisions = 1
        subdivision_width = staff_width / total_subdivisions  # Use float division for accuracy

        # Current position in subdivisions (within the visible area)
        if self.is_playing:
            # The display shows a STATIC 2-bar window (bars_visible = 2)
            # The playhead should move continuously from left to right across both bars
            # before looping back to the start
            #
            # For a 1-bar groove that loops:
            # - Bar cycle 0: playhead in display bar 0 (left bar)
            # - Bar cycle 1: playhead in display bar 1 (right bar)
            # - Bar cycle 2: playhead loops back to display bar 0
            #
            # current_bar tells us which cycle of the groove we're in (0, 1, 2, 3...)
            # We map this to display position using modulo bars_visible

            which_display_bar = self.current_bar % self.bars_visible

            # Position within the visible display area (0 to total_subdivisions-1)
            current_position = (
                which_display_bar * self.current_groove.beats_per_bar * self.current_groove.subdivision +
                self.current_beat * self.current_groove.subdivision +
                self.current_subdivision
            )
        else:
            current_position = 0

        # Draw staff lines
        staff_x = left_margin
        self._draw_staff_lines(painter, staff_x, y_center, staff_width)

        # Draw voice labels
        self._draw_voice_labels(painter, staff_x, y_center)

        # Draw time signature
        self._draw_time_signature(painter, staff_x + 5, y_center)

        # Draw bar lines and notes
        subdivisions_per_bar = self.current_groove.beats_per_bar * self.current_groove.subdivision

        for bar in range(self.bars_visible):
            # Bar line
            bar_x = int(staff_x + bar * subdivisions_per_bar * subdivision_width)
            self._draw_bar_lines(painter, bar_x, y_center)

            # Draw notes for this bar
            for beat in range(self.current_groove.beats_per_bar):
                for subdiv in range(self.current_groove.subdivision):
                    # Calculate x position
                    position_in_visible = (
                        bar * subdivisions_per_bar +
                        beat * self.current_groove.subdivision +
                        subdiv
                    )
                    note_x = int(staff_x + position_in_visible * subdivision_width + subdivision_width / 2)

                    # Get notes at this position
                    # For a static display, always show bars 0, 1, 2, etc. of the groove
                    # (not relative to current_bar)
                    notes = self.current_groove.get_notes_at_position(
                        bar % self.current_groove.bars,
                        beat,
                        subdiv
                    )

                    # Draw each note
                    for note in notes:
                        is_active = (
                            self.is_playing and
                            bar == 0 and
                            beat == self.current_beat and
                            subdiv == self.current_subdivision and
                            note in self.active_notes
                        )
                        self._draw_note(painter, note_x, y_center, note, is_active)

        # Final bar line
        final_bar_x = int(staff_x + self.bars_visible * subdivisions_per_bar * subdivision_width)
        self._draw_bar_lines(painter, final_bar_x, y_center)

        # Draw playhead
        if self.is_playing:
            playhead_x = int(staff_x + current_position * subdivision_width + subdivision_width / 2)
            self._draw_playhead(painter, playhead_x, y_center)

        # Draw groove name at top
        painter.setPen(self.text_color)
        font = QFont("Arial", 12, QFont.Bold)
        painter.setFont(font)
        title_rect = QRect(0, 5, w, 25)
        painter.drawText(title_rect, Qt.AlignCenter, self.current_groove.name)
