from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple
import random
import json
import os
from pathlib import Path
from PyQt5.QtCore import QObject, pyqtSignal, pyqtSlot
from .engine import MetronomeEngine


@dataclass
class DrumNote:
    """Represents a single drum hit in a groove."""
    voice: str  # 'kick', 'snare', 'hihat_closed', 'hihat_open', 'ride', 'crash', 'tom1', 'tom2', 'tom3'
    beat: int  # Which beat (0-indexed within the bar)
    subdivision: int  # Which subdivision of the beat (0-indexed)
    accent: bool = False  # Whether this note is accented
    bar: int = 0  # Which bar (0-indexed within the groove)
    hand: Optional[str] = None  # 'L' or 'R' sticking (optional)

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
    subdivision: int = 4  # Playback ticks per beat (4 = 16th grid, 12 = 16th + triplet)
    grid_subdivision: Optional[int] = None  # Editor grid subdivision per beat
    triplet_overlays: List[Tuple[int, int]] = field(default_factory=list)
    thirty_second_overlays: List[Tuple[int, int]] = field(default_factory=list)
    _notes_by_position: Dict[Tuple[int, int, int], List[DrumNote]] = field(
        default_factory=dict, init=False, repr=False
    )
    _notes_by_beat: Dict[Tuple[int, int], List[DrumNote]] = field(
        default_factory=dict, init=False, repr=False
    )

    def __post_init__(self):
        if self.grid_subdivision is None or self.grid_subdivision <= 0:
            self.grid_subdivision = self.subdivision
        self._build_note_cache()

    def _build_note_cache(self):
        notes_by_position: Dict[Tuple[int, int, int], List[DrumNote]] = {}
        notes_by_beat: Dict[Tuple[int, int], List[DrumNote]] = {}
        bars = self.bars if self.bars > 0 else 1
        for note in self.notes:
            note_bar = getattr(note, "bar", 0)
            if bars > 0:
                note_bar = note_bar % bars
            pos_key = (note_bar, note.beat, note.subdivision)
            notes_by_position.setdefault(pos_key, []).append(note)
            beat_key = (note_bar, note.beat)
            notes_by_beat.setdefault(beat_key, []).append(note)
        self._notes_by_position = notes_by_position
        self._notes_by_beat = notes_by_beat

    def get_notes_at_position(self, bar: int, beat: int, subdivision: int) -> List[DrumNote]:
        """Get all notes that should play at a specific position."""
        # Normalize position to the pattern length
        bar = bar % self.bars if self.bars > 0 else 0

        return self._notes_by_position.get((bar, beat, subdivision), [])

    def get_notes_for_beat(self, bar: int, beat: int) -> List[DrumNote]:
        """Get all notes that should play within a specific beat."""
        bar = bar % self.bars if self.bars > 0 else 0
        return self._notes_by_beat.get((bar, beat), [])

    def to_dict(self) -> Dict:
        """Serialize to dictionary for JSON storage."""
        notes_data = []
        for note in self.notes:
            hand = note.hand
            if isinstance(hand, str):
                hand = hand.upper()
            note_data = {
                'voice': note.voice,
                'beat': note.beat,
                'subdivision': note.subdivision,
                'accent': note.accent,
                'bar': note.bar,
            }
            if hand in ("L", "R"):
                note_data['hand'] = hand
            notes_data.append(note_data)

        overlays_data = []
        for bar, beat in self.triplet_overlays:
            overlays_data.append({'bar': int(bar), 'beat': int(beat)})

        thirty_second_data = []
        for bar, beat in self.thirty_second_overlays:
            thirty_second_data.append({'bar': int(bar), 'beat': int(beat)})

        return {
            'name': self.name,
            'notes': notes_data,
            'beats_per_bar': self.beats_per_bar,
            'bars': self.bars,
            'subdivision': self.subdivision,
            'grid_subdivision': self.grid_subdivision,
            'triplet_overlays': overlays_data,
            'thirty_second_overlays': thirty_second_data,
        }

    @classmethod
    def from_dict(cls, data: Dict) -> 'DrumGroove':
        """Deserialize from dictionary."""
        notes = []
        for n in data['notes']:
            hand = n.get('hand')
            if isinstance(hand, str):
                hand = hand.upper()
                if hand not in ("L", "R"):
                    hand = None
            else:
                hand = None

            notes.append(DrumNote(
                voice=n['voice'],
                beat=n['beat'],
                subdivision=n['subdivision'],
                accent=n.get('accent', False),
                bar=n.get('bar', 0),
                hand=hand,
            ))

        overlays_raw = data.get('triplet_overlays', [])
        overlays = []
        if isinstance(overlays_raw, list):
            for item in overlays_raw:
                if isinstance(item, dict):
                    bar = item.get('bar', 0)
                    beat = item.get('beat', 0)
                elif isinstance(item, (list, tuple)) and len(item) >= 2:
                    bar, beat = item[0], item[1]
                else:
                    continue
                overlays.append((int(bar), int(beat)))

        thirty_second_raw = data.get('thirty_second_overlays', [])
        thirty_second = []
        if isinstance(thirty_second_raw, list):
            for item in thirty_second_raw:
                if isinstance(item, dict):
                    bar = item.get('bar', 0)
                    beat = item.get('beat', 0)
                elif isinstance(item, (list, tuple)) and len(item) >= 2:
                    bar, beat = item[0], item[1]
                else:
                    continue
                thirty_second.append((int(bar), int(beat)))

        return cls(
            name=data['name'],
            notes=notes,
            beats_per_bar=data.get('beats_per_bar', 4),
            bars=data.get('bars', 1),
            subdivision=data.get('subdivision', 4),
            grid_subdivision=data.get('grid_subdivision'),
            triplet_overlays=overlays,
            thirty_second_overlays=thirty_second,
        )


class GrooveLibrary:
    """Manages a library of preset and custom drum grooves."""

    def __init__(self):
        self.grooves: List[DrumGroove] = []
        self._init_presets()
        self._load_custom_grooves()

    @staticmethod
    def _normalize_name(name: str) -> str:
        return name.strip().casefold()

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
        """Get the path to the grooves directory."""
        project_root = Path(__file__).resolve().parent.parent
        grooves_dir = project_root / 'grooves'
        grooves_dir.mkdir(parents=True, exist_ok=True)
        return grooves_dir

    def _load_custom_grooves(self):
        """Load custom grooves from user directory."""
        grooves_dir = self._get_custom_grooves_path()
        for file_path in sorted(grooves_dir.iterdir()):
            if not file_path.is_file():
                continue
            try:
                with open(file_path, 'r') as f:
                    data = json.load(f)
                    groove = DrumGroove.from_dict(data)
                    self._upsert_groove(groove)
            except Exception as e:
                print(f"Failed to load groove from {file_path}: {e}")

    def _upsert_groove(self, groove: DrumGroove):
        """Replace any existing groove with the same name or append a new one."""
        name_key = self._normalize_name(groove.name)
        updated = []
        inserted = False

        for existing in self.grooves:
            if self._normalize_name(existing.name) == name_key:
                if not inserted:
                    updated.append(groove)
                    inserted = True
                continue
            updated.append(existing)

        if not inserted:
            updated.append(groove)

        self.grooves = updated

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

            self._upsert_groove(groove)
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
        name_key = self._normalize_name(name)
        for g in self.grooves:
            if self._normalize_name(g.name) == name_key:
                return g
        return None


class GrooveRoutine(QObject):
    """Manages playing drum grooves synchronized with the metronome engine."""

    grooveChanged = pyqtSignal(object)  # DrumGroove
    notesPlaying = pyqtSignal(list)  # List[DrumNote] - notes at current position
    positionChanged = pyqtSignal(int, int, int)  # bar_in_groove, beat, subdivision
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
        # step_idx is the step within the bar, so compute beat and subdivision directly from it
        if self._engine.subdivision > 0:
            beat_from_step = step_idx // self._engine.subdivision
            subdivision_idx = step_idx % self._engine.subdivision
        else:
            beat_from_step = 0
            subdivision_idx = 0

        # Get notes at this position
        notes = self._current_groove.get_notes_at_position(
            self._bar_in_groove,
            beat_from_step,
            subdivision_idx
        )

        self.positionChanged.emit(self._bar_in_groove, beat_from_step, subdivision_idx)

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
