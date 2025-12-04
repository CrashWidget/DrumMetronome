from dataclasses import dataclass
from typing import List
import random
from PyQt5.QtCore import QObject, pyqtSignal, pyqtSlot
from .engine import MetronomeEngine

@dataclass
class Rudiment:
    name: str
    sticking: str
    # generic description or note type could be added, e.g. "16th"

class RudimentPracticeRoutine(QObject):
    rudimentChanged = pyqtSignal(object, object)  # current: Rudiment, next: Rudiment
    activeChanged = pyqtSignal(bool)

    def __init__(self, engine: MetronomeEngine, parent=None):
        super().__init__(parent)
        self._engine = engine
        self._running = False
        
        self._bars_per_rudiment = 1
        self._bar_counter = 0
        
        # Library of rudiments
        self._library = [
            Rudiment("Quarter Notes", "R L R L"),
            Rudiment("Eighth Notes", "RL RL RL RL"),
            Rudiment("16th Notes", "RLRL RLRL RLRL RLRL"),
            Rudiment("Triplets", "RLR LRL RLR LRL"),
            Rudiment("Paradiddle", "RLRR LRLL RLRR LRLL"),
            Rudiment("Flam", "lR rL lR rL"),
            Rudiment("Double Paradiddle", "RLRLRR LRLRLL"),
        ]
        self._enabled_rudiments = list(self._library)
        
        self._current_rudiment = None
        self._next_rudiment = None
        self._lead_hand = 'R'  # 'R', 'L', 'Mixed'

    @property
    def running(self):
        return self._running

    def get_rudiment_names(self) -> List[str]:
        return [r.name for r in self._library]

    @pyqtSlot(str)
    def set_lead_hand(self, hand: str):
        if hand in ['R', 'L', 'Mixed']:
            self._lead_hand = hand

    def _apply_lead_hand(self, rudiment: Rudiment) -> Rudiment:
        mode = self._lead_hand
        
        invert = False
        if mode == 'L':
            invert = True
        elif mode == 'Mixed':
            invert = random.choice([True, False])
        
        if not invert:
            return rudiment
            
        # Invert sticking
        original = rudiment.sticking
        inverted = ""
        for char in original:
            if char == 'R': inverted += 'L'
            elif char == 'L': inverted += 'R'
            elif char == 'r': inverted += 'l'
            elif char == 'l': inverted += 'r'
            else: inverted += char
            
        return Rudiment(rudiment.name, inverted)

    @pyqtSlot(list)
    def set_enabled_rudiments(self, names: List[str]):
        if not names:
            self._enabled_rudiments = list(self._library)
            return
        
        filtered = [r for r in self._library if r.name in names]
        if filtered:
            self._enabled_rudiments = filtered
        else:
            self._enabled_rudiments = list(self._library)

    @pyqtSlot(int)
    def set_bars_per_rudiment(self, bars: int):
        self._bars_per_rudiment = max(1, bars)

    @pyqtSlot()
    def start(self):
        if self._running:
            return
        
        self._running = True
        self._bar_counter = 0
        
        # Initial pick
        pool = self._enabled_rudiments if self._enabled_rudiments else self._library
        self._current_rudiment = self._apply_lead_hand(random.choice(pool))
        self._next_rudiment = self._apply_lead_hand(random.choice(pool))
        
        # Connect signals
        try:
            self._engine.barAdvanced.disconnect(self._on_bar_advanced)
        except TypeError:
            pass
        self._engine.barAdvanced.connect(self._on_bar_advanced)
        
        self.activeChanged.emit(True)
        self.rudimentChanged.emit(self._current_rudiment, self._next_rudiment)

    @pyqtSlot()
    def stop(self):
        if not self._running:
            return
        
        self._running = False
        try:
            self._engine.barAdvanced.disconnect(self._on_bar_advanced)
        except TypeError:
            pass
            
        self.activeChanged.emit(False)

    @pyqtSlot(int)
    def _on_bar_advanced(self, bar_idx: int):
        if not self._running:
            return
        
        self._bar_counter += 1
        if self._bar_counter < self._bars_per_rudiment:
            return

        self._bar_counter = 0

        # Swap and pick new
        self._current_rudiment = self._next_rudiment
        pool = self._enabled_rudiments if self._enabled_rudiments else self._library
        self._next_rudiment = self._apply_lead_hand(random.choice(pool))
        
        self.rudimentChanged.emit(self._current_rudiment, self._next_rudiment)
