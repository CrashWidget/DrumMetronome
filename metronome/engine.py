from PyQt5.QtCore import QObject, QTimer, pyqtSignal, Qt, QElapsedTimer, pyqtSlot


class MetronomeEngine(QObject):
    tick = pyqtSignal(int, int, bool, bool)  # step_index, beat_index, is_beat, is_accent
    click = pyqtSignal(bool)  # is_accent (emitted when a sound should play)
    barAdvanced = pyqtSignal(int)  # bar_index
    bpmChanged = pyqtSignal(int)
    runningChanged = pyqtSignal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._bpm = 100
        self._beats_per_bar = 4
        self._subdivision = 1  # per beat
        self._accent_on_one = True

        # Timer is created in initialize() to ensure thread affinity
        self._timer = None
        self._running = False

        self._step_index = 0
        self._beat_index = 0
        self._bar_index = 0

        # High-resolution scheduling
        self._clock = QElapsedTimer()
        self._step_ns = 0
        self._next_due_ns = 0

        self._recompute_interval()

    @pyqtSlot()
    def initialize(self):
        """Create timer in the worker thread."""
        if self._timer is not None:
            return
        self._timer = QTimer(self)
        self._timer.setTimerType(Qt.PreciseTimer)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._on_timeout)

    # Properties
    @property
    def bpm(self) -> int:
        return self._bpm

    @pyqtSlot(int)
    def set_bpm(self, bpm: int):
        bpm = max(20, min(400, int(bpm)))
        if bpm != self._bpm:
            self._bpm = bpm
            self._recompute_interval()
            self.bpmChanged.emit(self._bpm)

    @property
    def beats_per_bar(self) -> int:
        return self._beats_per_bar

    @pyqtSlot(int)
    def set_beats_per_bar(self, beats: int):
        beats = max(1, min(12, int(beats)))
        if beats != self._beats_per_bar:
            self._beats_per_bar = beats
            self._reset_counters()

    @property
    def subdivision(self) -> int:
        return self._subdivision

    @pyqtSlot(int)
    def set_subdivision(self, subdiv: int):
        subdiv = max(1, min(12, int(subdiv)))
        if subdiv != self._subdivision:
            self._subdivision = subdiv
            self._recompute_interval()
            self._reset_counters()

    @property
    def accent_on_one(self) -> bool:
        return self._accent_on_one

    @pyqtSlot(bool)
    def set_accent_on_one(self, on: bool):
        self._accent_on_one = bool(on)

    def is_running(self) -> bool:
        return self._running

    @pyqtSlot()
    def start(self):
        if not self._running:
            # Initialize high-res clock and schedule first tick precisely
            self._clock.start()
            now_ns = self._clock.nsecsElapsed()
            self._next_due_ns = now_ns + self._step_ns
            self._schedule_next(now_ns)
            self._running = True
            self.runningChanged.emit(True)

    @pyqtSlot()
    def stop(self):
        if self._running:
            self._timer.stop()
            self._running = False
            self.runningChanged.emit(False)

    def _reset_counters(self):
        self._step_index = 0
        self._beat_index = 0
        self._bar_index = 0

    def _recompute_interval(self):
        # Interval per subdivision step in ms
        # One beat duration (quarter) = 60000 / bpm
        # Subdivide beat by _subdivision
        subdiv = max(1, self._subdivision)
        
        # High-resolution nanoseconds for precise scheduling
        self._step_ns = int((60_000_000_000) / (self._bpm * subdiv))
        
        # If running, we do NOT reset next_due_ns here.
        # We allow the existing timer/loop to pick up the new step size naturally.
        # This prevents phase jumps and double-scheduling when set_bpm is called inside a tick.

    def _on_timeout(self):
        try:
            if not self._running:
                return
            steps_per_bar = self._beats_per_bar * self._subdivision
            is_beat = (self._step_index % self._subdivision) == 0
            # Accent decision based on current beat BEFORE incrementing
            current_beat = self._beat_index
            is_first_beat = is_beat and current_beat == 0
            is_accent = self._accent_on_one and is_first_beat

            self.tick.emit(self._step_index, current_beat, is_beat, is_accent)

            # Emit click signal for audio handling (decoupled from UI)
            if is_beat or self._subdivision > 1:
                self.click.emit(is_accent)

            # Advance counters AFTER emitting
            if is_beat:
                self._beat_index = (self._beat_index + 1) % self._beats_per_bar
            self._step_index += 1
            if self._step_index >= steps_per_bar:
                self._step_index = 0
                self._beat_index = 0
                self._bar_index += 1
                self.barAdvanced.emit(self._bar_index)

            # Compute and schedule next precise timeout with drift compensation
            now_ns = self._clock.nsecsElapsed()
            # Advance next_due by exactly one step duration from previous target
            self._next_due_ns += self._step_ns
            # If we fell behind by more than one step, jump ahead but do not spam multiple ticks
            if self._next_due_ns <= now_ns:
                # place it at now + small lead to catch the next grid cleanly
                missed = (now_ns - self._next_due_ns) // max(1, self._step_ns) + 1
                self._next_due_ns += missed * self._step_ns
            self._schedule_next(now_ns)
        except Exception as e:
            print(f"Error in metronome engine: {e}")
            import traceback
            traceback.print_exc()

    def _schedule_next(self, now_ns: int):
        delay_ns = max(0, self._next_due_ns - now_ns)
        # Convert to milliseconds for QTimer, but keep sub-ms by rounding down to 0 when very small
        delay_ms = int(delay_ns / 1_000_000)
        # Use 0 to schedule ASAP if under 1ms
        self._timer.start(max(0, delay_ms))


class TempoLadderRoutine(QObject):
    stateChanged = pyqtSignal(bool)
    routineFinished = pyqtSignal()

    def __init__(self, engine: MetronomeEngine, parent=None):
        super().__init__(parent)
        self._engine = engine
        self._running = False

        self._start_bpm = 100
        self._end_bpm = 120
        self._step_bpm = 5
        self._bars_per_step = 4

        self._bar_counter = 0

    @pyqtSlot(int, int, int, int)
    def configure(self, start_bpm: int, end_bpm: int, step_bpm: int, bars_per_step: int):
        self._start_bpm = start_bpm
        self._end_bpm = end_bpm
        self._step_bpm = step_bpm
        self._bars_per_step = bars_per_step

    @pyqtSlot()
    def start(self):
        if self._running:
            return

        self._running = True
        self._bar_counter = 0

        # Set initial BPM
        self._engine.set_bpm(self._start_bpm)

        # Connect to bar signal
        # Avoid duplicate connection if safe, but disconnect/connect is safer
        try:
            self._engine.barAdvanced.disconnect(self._on_bar_advanced)
        except TypeError:
            pass  # wasn't connected

        self._engine.barAdvanced.connect(self._on_bar_advanced)

        self.stateChanged.emit(True)

    @pyqtSlot()
    def stop(self):
        if not self._running:
            return

        self._running = False
        try:
            self._engine.barAdvanced.disconnect(self._on_bar_advanced)
        except TypeError:
            pass

        self.stateChanged.emit(False)

    def is_running(self) -> bool:
        return self._running

    @pyqtSlot(int)
    def _on_bar_advanced(self, bar_idx: int):
        if not self._running:
            return

        self._bar_counter += 1
        if self._bar_counter < self._bars_per_step:
            return

        self._bar_counter = 0
        current_bpm = self._engine.bpm

        # Check if we just finished the final segment
        if current_bpm == self._end_bpm:
            self.stop()
            self.routineFinished.emit()
            return

        # Calculate next
        if self._start_bpm <= self._end_bpm:
            # Going up
            next_bpm = current_bpm + self._step_bpm
            if next_bpm >= self._end_bpm:
                next_bpm = self._end_bpm
        else:
            # Going down
            next_bpm = current_bpm - self._step_bpm
            if next_bpm <= self._end_bpm:
                next_bpm = self._end_bpm

        self._engine.set_bpm(next_bpm)
    