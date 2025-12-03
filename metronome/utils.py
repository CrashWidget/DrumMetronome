import time


class TapTempo:
    """Collects tap times and computes BPM as 60 / average interval.

    Resets if time between taps exceeds reset_ms.
    """

    def __init__(self, reset_ms: int = 2500):
        self.reset_ms = reset_ms
        self._times = []  # seconds

    def tap(self) -> int | None:
        now = time.time()
        if self._times and (now - self._times[-1]) * 1000 > self.reset_ms:
            self._times.clear()
        self._times.append(now)
        if len(self._times) < 2:
            return None
        # compute average interval over last up to 8 taps
        times = self._times[-8:]
        intervals = [t2 - t1 for t1, t2 in zip(times[:-1], times[1:])]
        avg = sum(intervals) / len(intervals)
        if avg <= 0:
            return None
        bpm = int(round(60.0 / avg))
        return max(20, min(400, bpm))
