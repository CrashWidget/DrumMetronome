from dataclasses import dataclass
from typing import List, Dict
import random
import json
import os
from pathlib import Path
from PyQt5.QtCore import QObject, pyqtSignal, pyqtSlot
from .engine import MetronomeEngine


@dataclass
class DrumNote:
    """Represents a single drum hit in a groove."""
    voice: str  # 'kick', 'snare', 'hihat', 'ride', 'crash', 'tom1', 'tom2', 'tom3'
    beat: int  # Which beat (0-indexed within the bar)
    subdivision: int  # Which subdivision of the beat (0-indexed)
    accent: bool = False  # Whether this note is accented

    def get_absolute_position(self, subdivisions_per_beat: int) -> int:
        """Get the absolute position within a bar."""
        return self.beat * subdivisions_per_beat + self.subdivision


@dataclass
class DrumGroove:
    """Represents a complete drum groove/pattern."""
    name: str
    notes: List[DrumNote]
    beats_per_bar: int = 4
    bars: int = 1
    subdivision: int = 4  # How many subdivisions per beat (4 = 16th notes)

    def get_notes_at_position(self, bar: int, beat: int, subdivision: int) -> List[DrumNote]:
        """Get all notes that should play at a specific position."""
        # Normalize position to the pattern length
        bar = bar % self.bars

        # Only return notes if we're in the right bar and position
        result = []
        for note in self.notes:
            # For single-bar patterns, ignore bar parameter
            # For multi-bar patterns, we'd need to track which bar each note belongs to
            if note.beat == beat and note.subdivision == subdivision:
                result.append(note)
        return result

    def to_dict(self) -> Dict:
        """Serialize to dictionary for JSON storage."""
        return {
            'name': self.name,
            'notes': [
                {
                    'voice': n.voice,
                    'beat': n.beat,
                    'subdivision': n.subdivision,
                    'accent': n.accent
                }
                for n in self.notes
            ],
            'beats_per_bar': self.beats_per_bar,
            'bars': self.bars,
            'subdivision': self.subdivision
        }

    @classmethod
    def from_dict(cls, data: Dict) -> 'DrumGroove':
        """Deserialize from dictionary."""
        notes = [
            DrumNote(
                voice=n['voice'],
                beat=n['beat'],
                subdivision=n['subdivision'],
                accent=n.get('accent', False)
            )
            for n in data['notes']
        ]
        return cls(
            name=data['name'],
            notes=notes,
            beats_per_bar=data.get('beats_per_bar', 4),
            bars=data.get('bars', 1),
            subdivision=data.get('subdivision', 4)
        )


class GrooveLibrary:
    """Manages a library of preset and custom drum grooves."""

    def __init__(self):
        self.grooves: List[DrumGroove] = []
        self._init_presets()
        self._load_custom_grooves()

    def _init_presets(self):
        """Initialize the preset groove library."""
        # Basic Rock Beat (8th note hi-hat, kick on 1 and 3, snare on 2 and 4)
        basic_rock = DrumGroove(
            name="Basic Rock Beat",
            beats_per_bar=4,
            bars=1,
            subdivision=2,  # 8th notes
            notes=[
                # Hi-hat 8th notes
                DrumNote('hihat', 0, 0), DrumNote('hihat', 0, 1),
                DrumNote('hihat', 1, 0), DrumNote('hihat', 1, 1),
                DrumNote('hihat', 2, 0), DrumNote('hihat', 2, 1),
                DrumNote('hihat', 3, 0), DrumNote('hihat', 3, 1),
                # Kick on 1 and 3
                DrumNote('kick', 0, 0, accent=True),
                DrumNote('kick', 2, 0),
                # Snare on 2 and 4
                DrumNote('snare', 1, 0, accent=True),
                DrumNote('snare', 3, 0, accent=True),
            ]
        )

        # Rock with Kick Variations (16th note hi-hat)
        rock_variations = DrumGroove(
            name="Rock with Kick Variations",
            beats_per_bar=4,
            bars=1,
            subdivision=4,  # 16th notes
            notes=[
                # Hi-hat 8th notes (on 16th grid)
                DrumNote('hihat', 0, 0), DrumNote('hihat', 0, 2),
                DrumNote('hihat', 1, 0), DrumNote('hihat', 1, 2),
                DrumNote('hihat', 2, 0), DrumNote('hihat', 2, 2),
                DrumNote('hihat', 3, 0), DrumNote('hihat', 3, 2),
                # Kick with variations
                DrumNote('kick', 0, 0, accent=True),
                DrumNote('kick', 1, 3),  # "and" of 2
                DrumNote('kick', 2, 0),
                DrumNote('kick', 3, 2),  # "e" of 4
                # Snare on 2 and 4
                DrumNote('snare', 1, 0, accent=True),
                DrumNote('snare', 3, 0, accent=True),
            ]
        )

        # Motown Groove (hi-hat on quarters, detailed kick pattern)
        motown = DrumGroove(
            name="Motown Groove",
            beats_per_bar=4,
            bars=1,
            subdivision=4,
            notes=[
                # Hi-hat on quarter notes
                DrumNote('hihat', 0, 0, accent=True),
                DrumNote('hihat', 1, 0, accent=True),
                DrumNote('hihat', 2, 0, accent=True),
                DrumNote('hihat', 3, 0, accent=True),
                # Syncopated kick
                DrumNote('kick', 0, 0, accent=True),
                DrumNote('kick', 1, 2),
                DrumNote('kick', 2, 1),
                DrumNote('kick', 3, 3),
                # Snare on 2 and 4
                DrumNote('snare', 1, 0, accent=True),
                DrumNote('snare', 3, 0, accent=True),
            ]
        )

        # Jazz Swing (ride pattern with swing feel)
        jazz_swing = DrumGroove(
            name="Jazz Swing Pattern",
            beats_per_bar=4,
            bars=1,
            subdivision=3,  # Triplet feel
            notes=[
                # Ride cymbal swing pattern (ding-ding-a)
                DrumNote('ride', 0, 0, accent=True), DrumNote('ride', 0, 2),
                DrumNote('ride', 1, 0, accent=True), DrumNote('ride', 1, 2),
                DrumNote('ride', 2, 0, accent=True), DrumNote('ride', 2, 2),
                DrumNote('ride', 3, 0, accent=True), DrumNote('ride', 3, 2),
                # Hi-hat on 2 and 4
                DrumNote('hihat', 1, 0),
                DrumNote('hihat', 3, 0),
                # Sparse kick
                DrumNote('kick', 0, 0),
                DrumNote('kick', 2, 1),
            ]
        )

        # Linear Groove
        linear = DrumGroove(
            name="Linear Groove",
            beats_per_bar=4,
            bars=1,
            subdivision=4,
            notes=[
                # Beat 1
                DrumNote('kick', 0, 0, accent=True),
                DrumNote('hihat', 0, 1),
                DrumNote('snare', 0, 2),
                DrumNote('hihat', 0, 3),
                # Beat 2
                DrumNote('kick', 1, 0),
                DrumNote('hihat', 1, 1),
                DrumNote('snare', 1, 2, accent=True),
                DrumNote('hihat', 1, 3),
                # Beat 3
                DrumNote('kick', 2, 0),
                DrumNote('hihat', 2, 1),
                DrumNote('snare', 2, 2),
                DrumNote('hihat', 2, 3),
                # Beat 4
                DrumNote('kick', 3, 0),
                DrumNote('hihat', 3, 1),
                DrumNote('snare', 3, 2, accent=True),
                DrumNote('kick', 3, 3),
            ]
        )

        # Basic Fill (16th note tom pattern)
        basic_fill = DrumGroove(
            name="Basic Tom Fill",
            beats_per_bar=4,
            bars=1,
            subdivision=4,
            notes=[
                # First 3 beats: basic pattern
                DrumNote('hihat', 0, 0), DrumNote('hihat', 0, 2),
                DrumNote('kick', 0, 0, accent=True),
                DrumNote('hihat', 1, 0), DrumNote('hihat', 1, 2),
                DrumNote('snare', 1, 0, accent=True),
                DrumNote('hihat', 2, 0), DrumNote('hihat', 2, 2),
                DrumNote('kick', 2, 0),
                # Beat 4: fill
                DrumNote('tom1', 3, 0, accent=True),
                DrumNote('tom1', 3, 1),
                DrumNote('tom2', 3, 2),
                DrumNote('tom3', 3, 3),
            ]
        )

        # Half-time Groove
        halftime = DrumGroove(
            name="Half-time Groove",
            beats_per_bar=4,
            bars=1,
            subdivision=4,
            notes=[
                # Hi-hat 16ths
                DrumNote('hihat', 0, 0), DrumNote('hihat', 0, 1),
                DrumNote('hihat', 0, 2), DrumNote('hihat', 0, 3),
                DrumNote('hihat', 1, 0), DrumNote('hihat', 1, 1),
                DrumNote('hihat', 1, 2), DrumNote('hihat', 1, 3),
                DrumNote('hihat', 2, 0), DrumNote('hihat', 2, 1),
                DrumNote('hihat', 2, 2), DrumNote('hihat', 2, 3),
                DrumNote('hihat', 3, 0), DrumNote('hihat', 3, 1),
                DrumNote('hihat', 3, 2), DrumNote('hihat', 3, 3),
                # Kick on 1
                DrumNote('kick', 0, 0, accent=True),
                # Snare on 3 (half-time feel)
                DrumNote('snare', 2, 0, accent=True),
            ]
        )

        # Shuffle Pattern
        shuffle = DrumGroove(
            name="Shuffle Pattern",
            beats_per_bar=4,
            bars=1,
            subdivision=3,  # Triplet subdivision
            notes=[
                # Shuffle hi-hat (long-short pattern)
                DrumNote('hihat', 0, 0, accent=True), DrumNote('hihat', 0, 2),
                DrumNote('hihat', 1, 0), DrumNote('hihat', 1, 2),
                DrumNote('hihat', 2, 0, accent=True), DrumNote('hihat', 2, 2),
                DrumNote('hihat', 3, 0), DrumNote('hihat', 3, 2),
                # Kick on 1 and 3
                DrumNote('kick', 0, 0, accent=True),
                DrumNote('kick', 2, 0),
                # Snare on 2 and 4
                DrumNote('snare', 1, 0, accent=True),
                DrumNote('snare', 3, 0, accent=True),
            ]
        )

        # Paradiddle Groove
        paradiddle = DrumGroove(
            name="Paradiddle Groove",
            beats_per_bar=4,
            bars=1,
            subdivision=4,
            notes=[
                # Paradiddle on hi-hat/snare (RLRR LRLL pattern)
                # Beat 1: R(hihat) L(snare) R(hihat) R(snare)
                DrumNote('hihat', 0, 0, accent=True),
                DrumNote('snare', 0, 1),
                DrumNote('hihat', 0, 2),
                DrumNote('snare', 0, 3),
                # Beat 2: L(snare) R(hihat) L(snare) L(snare)
                DrumNote('snare', 1, 0, accent=True),
                DrumNote('hihat', 1, 1),
                DrumNote('snare', 1, 2),
                DrumNote('snare', 1, 3),
                # Beat 3: repeat
                DrumNote('hihat', 2, 0),
                DrumNote('snare', 2, 1),
                DrumNote('hihat', 2, 2),
                DrumNote('snare', 2, 3),
                # Beat 4: repeat
                DrumNote('snare', 3, 0),
                DrumNote('hihat', 3, 1),
                DrumNote('snare', 3, 2),
                DrumNote('snare', 3, 3),
                # Kick pattern underneath
                DrumNote('kick', 0, 0, accent=True),
                DrumNote('kick', 2, 0),
            ]
        )

        self.grooves = [
            basic_rock,
            rock_variations,
            motown,
            jazz_swing,
            linear,
            basic_fill,
            halftime,
            shuffle,
            paradiddle,
        ]

    def _get_custom_grooves_path(self) -> Path:
        """Get the path to custom grooves directory."""
        home = Path.home()
        grooves_dir = home / '.drummetronome' / 'grooves'
        grooves_dir.mkdir(parents=True, exist_ok=True)
        return grooves_dir

    def _load_custom_grooves(self):
        """Load custom grooves from user directory."""
        grooves_dir = self._get_custom_grooves_path()
        for file_path in grooves_dir.glob('*.json'):
            try:
                with open(file_path, 'r') as f:
                    data = json.load(f)
                    groove = DrumGroove.from_dict(data)
                    self.grooves.append(groove)
            except Exception as e:
                print(f"Failed to load groove from {file_path}: {e}")

    def save_groove(self, groove: DrumGroove):
        """Save a custom groove to disk."""
        grooves_dir = self._get_custom_grooves_path()
        # Sanitize filename
        filename = "".join(c for c in groove.name if c.isalnum() or c in (' ', '_', '-')).rstrip()
        filename = filename.replace(' ', '_') + '.json'
        file_path = grooves_dir / filename

        try:
            with open(file_path, 'w') as f:
                json.dump(groove.to_dict(), f, indent=2)

            # Add to library if not already present
            if groove not in self.grooves:
                self.grooves.append(groove)
        except Exception as e:
            print(f"Failed to save groove: {e}")
            raise

    def delete_groove(self, groove: DrumGroove):
        """Delete a custom groove (presets cannot be deleted)."""
        if groove in self.grooves:
            # Only delete if it's a custom groove (has file on disk)
            grooves_dir = self._get_custom_grooves_path()
            filename = "".join(c for c in groove.name if c.isalnum() or c in (' ', '_', '-')).rstrip()
            filename = filename.replace(' ', '_') + '.json'
            file_path = grooves_dir / filename

            if file_path.exists():
                file_path.unlink()
                self.grooves.remove(groove)
                return True
        return False

    def get_groove_names(self) -> List[str]:
        """Get list of all groove names."""
        return [g.name for g in self.grooves]

    def get_groove_by_name(self, name: str) -> DrumGroove:
        """Get a groove by name."""
        for g in self.grooves:
            if g.name == name:
                return g
        return None


class GrooveRoutine(QObject):
    """Manages playing drum grooves synchronized with the metronome engine."""

    grooveChanged = pyqtSignal(object)  # DrumGroove
    notesPlaying = pyqtSignal(list)  # List[DrumNote] - notes at current position
    activeChanged = pyqtSignal(bool)

    def __init__(self, engine: MetronomeEngine, library: GrooveLibrary, parent=None):
        super().__init__(parent)
        self._engine = engine
        self._library = library
        self._running = False

        self._current_groove = None
        self._bar_in_groove = 0
        self._loop_count = 0  # 0 = infinite
        self._bars_played = 0

    @property
    def running(self):
        return self._running

    @pyqtSlot(str)
    def set_groove(self, groove_name: str):
        """Set the current groove by name."""
        groove = self._library.get_groove_by_name(groove_name)
        if groove:
            self._current_groove = groove
            self.grooveChanged.emit(groove)

            # Update engine settings to match groove
            if groove.beats_per_bar != self._engine.beats_per_bar:
                self._engine.set_beats_per_bar(groove.beats_per_bar)
            if groove.subdivision != self._engine.subdivision:
                self._engine.set_subdivision(groove.subdivision)

    @pyqtSlot(int)
    def set_loop_count(self, count: int):
        """Set how many times to loop the groove (0 = infinite)."""
        self._loop_count = max(0, count)

    @pyqtSlot()
    def start(self):
        """Start playing the current groove."""
        if self._running or not self._current_groove:
            return

        self._running = True
        self._bar_in_groove = 0
        self._bars_played = 0

        # Connect to engine signals
        try:
            self._engine.tick.disconnect(self._on_tick)
        except TypeError:
            pass
        try:
            self._engine.barAdvanced.disconnect(self._on_bar_advanced)
        except TypeError:
            pass

        self._engine.tick.connect(self._on_tick)
        self._engine.barAdvanced.connect(self._on_bar_advanced)

        self.activeChanged.emit(True)

    @pyqtSlot()
    def stop(self):
        """Stop playing the groove."""
        if not self._running:
            return

        self._running = False

        try:
            self._engine.tick.disconnect(self._on_tick)
        except TypeError:
            pass
        try:
            self._engine.barAdvanced.disconnect(self._on_bar_advanced)
        except TypeError:
            pass

        self.activeChanged.emit(False)
        self.notesPlaying.emit([])  # Clear display

    @pyqtSlot(int, int, bool, bool)
    def _on_tick(self, step_idx: int, beat_idx: int, is_beat: bool, is_accent: bool):
        """Handle each metronome tick."""
        if not self._running or not self._current_groove:
            return

        # Calculate which subdivision we're on (based on engine's subdivision)
        # step_idx is the step within the bar, so we need modulo to get subdivision within beat
        subdivision_idx = step_idx % self._engine.subdivision

        # Get notes at this position
        notes = self._current_groove.get_notes_at_position(
            self._bar_in_groove,
            beat_idx,
            subdivision_idx
        )

        if notes:
            self.notesPlaying.emit(notes)
        else:
            # Clear notes display between hits
            self.notesPlaying.emit([])

    @pyqtSlot(int)
    def _on_bar_advanced(self, bar_idx: int):
        """Handle bar advancement."""
        if not self._running or not self._current_groove:
            return

        self._bars_played += 1
        self._bar_in_groove = (self._bar_in_groove + 1) % self._current_groove.bars

        # Check if we should stop (loop count reached)
        if self._loop_count > 0:
            total_bars = self._current_groove.bars * self._loop_count
            if self._bars_played >= total_bars:
                self.stop()
