from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QPushButton,
    QComboBox, QSpinBox, QGroupBox, QWidget, QCheckBox, QScrollArea,
    QLineEdit, QMessageBox
)
from PyQt5.QtGui import QPainter, QColor, QPen, QBrush, QMouseEvent
from typing import Dict, Tuple, Optional, List
from .groove import DrumGroove, DrumNote, GrooveLibrary


class NoteGridWidget(QWidget):
    """
    A grid widget for programming drum notes.
    Rows = drum voices, Columns = subdivisions
    """

    noteToggled = pyqtSignal(str, int, int, bool)  # voice, beat, subdivision, state

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(800, 400)

        # Grid data: Dict[(voice, beat, subdiv)] = (enabled, accent)
        self.notes: Dict[Tuple[str, int, int], Tuple[bool, bool]] = {}

        # Grid settings
        self.voices = ['crash', 'ride', 'hihat', 'tom1', 'snare', 'tom2', 'tom3', 'kick']
        self.voice_labels = ['Crash', 'Ride', 'Hi-Hat', 'Tom 1', 'Snare', 'Tom 2', 'Tom 3', 'Kick']
        self.beats_per_bar = 4
        self.subdivision = 4  # 16th notes by default

        # Colors
        self.bg_color = QColor("#1a1a1a")
        self.grid_color = QColor("#333333")
        self.note_color = QColor("#0d6efd")
        self.accent_color = QColor("#ff4d4d")
        self.beat_line_color = QColor("#555555")
        self.text_color = QColor("#e0e0e0")

        # Interaction
        self.cell_width = 30
        self.cell_height = 40
        self.label_width = 80

    def set_grid_size(self, beats: int, subdivision: int):
        """Set the grid dimensions."""
        self.beats_per_bar = beats
        self.subdivision = subdivision
        self.notes.clear()
        self.update()
        self.updateGeometry()

    def load_groove(self, groove: DrumGroove):
        """Load notes from a groove."""
        self.beats_per_bar = groove.beats_per_bar
        self.subdivision = groove.subdivision
        self.notes.clear()

        for note in groove.notes:
            key = (note.voice, note.beat, note.subdivision)
            self.notes[key] = (True, note.accent)

        self.update()
        self.updateGeometry()

    def get_groove_notes(self) -> List[DrumNote]:
        """Export current grid as DrumNote list."""
        notes = []
        for (voice, beat, subdiv), (enabled, accent) in self.notes.items():
            if enabled:
                notes.append(DrumNote(voice, beat, subdiv, accent))
        return notes

    def clear_all(self):
        """Clear all notes."""
        self.notes.clear()
        self.update()

    def sizeHint(self):
        total_subdivs = self.beats_per_bar * self.subdivision
        width = self.label_width + total_subdivs * self.cell_width + 40
        height = len(self.voices) * self.cell_height + 60
        from PyQt5.QtCore import QSize
        return QSize(width, height)

    def _get_cell_at_pos(self, x: int, y: int) -> Optional[Tuple[str, int, int]]:
        """Get the cell (voice, beat, subdivision) at pixel position."""
        # Account for margins
        x -= self.label_width + 20
        y -= 40

        if x < 0 or y < 0:
            return None

        col = x // self.cell_width
        row = y // self.cell_height

        if row < 0 or row >= len(self.voices):
            return None

        total_subdivs = self.beats_per_bar * self.subdivision
        if col < 0 or col >= total_subdivs:
            return None

        voice = self.voices[row]
        beat = col // self.subdivision
        subdiv = col % self.subdivision

        return (voice, beat, subdiv)

    def mousePressEvent(self, event: QMouseEvent):
        """Handle mouse clicks to toggle notes."""
        cell = self._get_cell_at_pos(event.x(), event.y())
        if cell:
            voice, beat, subdiv = cell
            key = (voice, beat, subdiv)

            if event.button() == Qt.LeftButton:
                # Toggle note on/off
                if key in self.notes:
                    enabled, accent = self.notes[key]
                    self.notes[key] = (not enabled, accent)
                else:
                    self.notes[key] = (True, False)
                self.update()

            elif event.button() == Qt.RightButton:
                # Toggle accent (if note exists)
                if key in self.notes:
                    enabled, accent = self.notes[key]
                    if enabled:
                        self.notes[key] = (enabled, not accent)
                        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        # Fill background
        painter.fillRect(self.rect(), self.bg_color)

        margin_top = 40
        margin_left = self.label_width + 20

        total_subdivs = self.beats_per_bar * self.subdivision
        grid_width = total_subdivs * self.cell_width
        grid_height = len(self.voices) * self.cell_height

        # Draw column headers (beat numbers)
        painter.setPen(self.text_color)
        for beat in range(self.beats_per_bar):
            x = margin_left + beat * self.subdivision * self.cell_width
            painter.drawText(x, margin_top - 25, self.subdivision * self.cell_width, 20,
                            Qt.AlignCenter, str(beat + 1))

        # Draw subdivision markers
        from PyQt5.QtGui import QFont
        font = QFont("Arial", 8)
        painter.setFont(font)
        for i in range(total_subdivs):
            subdiv = i % self.subdivision
            if subdiv > 0:  # Don't label the beat itself
                x = margin_left + i * self.cell_width
                subdiv_labels = {1: 'e', 2: '+', 3: 'a'}
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
            # Thicker line at beat boundaries
            if i % self.subdivision == 0:
                painter.setPen(QPen(self.beat_line_color, 2))
            else:
                painter.setPen(QPen(self.grid_color, 1))
            painter.drawLine(x, margin_top, x, margin_top + grid_height)

        # Draw voice labels
        painter.setPen(self.text_color)
        font = QFont("Arial", 10)
        painter.setFont(font)
        for i, label in enumerate(self.voice_labels):
            y = margin_top + i * self.cell_height
            painter.drawText(10, y, self.label_width, self.cell_height,
                            Qt.AlignVCenter | Qt.AlignRight, label)

        # Draw notes
        for (voice, beat, subdiv), (enabled, accent) in self.notes.items():
            if not enabled:
                continue

            voice_idx = self.voices.index(voice)
            col = beat * self.subdivision + subdiv

            x = margin_left + col * self.cell_width
            y = margin_top + voice_idx * self.cell_height

            # Draw filled circle for note
            color = self.accent_color if accent else self.note_color
            painter.setBrush(QBrush(color))
            painter.setPen(QPen(color, 2))

            center_x = x + self.cell_width // 2
            center_y = y + self.cell_height // 2
            radius = 8

            painter.drawEllipse(center_x - radius, center_y - radius, radius * 2, radius * 2)

            # Draw accent marker if needed
            if accent:
                painter.setPen(QPen(self.accent_color, 2))
                font_accent = QFont("Arial", 10, QFont.Bold)
                painter.setFont(font_accent)
                painter.drawText(x, y + 5, self.cell_width, 15, Qt.AlignCenter, ">")

        # Draw instructions at bottom
        painter.setPen(self.text_color)
        font = QFont("Arial", 9)
        painter.setFont(font)
        instructions_y = margin_top + grid_height + 10
        painter.drawText(10, instructions_y, self.width() - 20, 30, Qt.AlignLeft,
                        "Left-click: Toggle note  |  Right-click: Toggle accent (red)")


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
        self.resize(1000, 700)

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
        top_layout.addWidget(QLabel("Subdivision:"), 1, 2)
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
        top_layout.addWidget(self.bars_spin, 2, 1)

        layout.addWidget(top_group)

        # Note grid (scrollable)
        grid_group = QGroupBox("Note Programming Grid")
        grid_layout = QVBoxLayout(grid_group)

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)

        self.note_grid = NoteGridWidget()
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
            return

        groove = self.library.get_groove_by_name(name)
        if groove:
            self.current_groove = groove
            self.name_edit.setText(groove.name)
            self.beats_spin.setValue(groove.beats_per_bar)

            # Set subdivision combo
            for i in range(self.subdiv_combo.count()):
                if self.subdiv_combo.itemData(i) == groove.subdivision:
                    self.subdiv_combo.setCurrentIndex(i)
                    break

            self.bars_spin.setValue(groove.bars)

            # Load into grid
            self.note_grid.load_groove(groove)

    def _on_settings_changed(self):
        """Update grid when settings change."""
        beats = self.beats_spin.value()
        subdiv = self.subdiv_combo.currentData()
        self.note_grid.set_grid_size(beats, subdiv)

    def _clear_grid(self):
        """Clear all notes from the grid."""
        self.note_grid.clear_all()

    def _save_groove(self):
        """Save the current groove."""
        name = self.name_edit.text().strip()
        if not name:
            QMessageBox.warning(self, "Invalid Name", "Please enter a groove name.")
            return

        notes = self.note_grid.get_groove_notes()
        if not notes:
            QMessageBox.warning(self, "Empty Groove", "Please add some notes to the groove.")
            return

        groove = DrumGroove(
            name=name,
            notes=notes,
            beats_per_bar=self.beats_spin.value(),
            bars=self.bars_spin.value(),
            subdivision=self.subdiv_combo.currentData()
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
