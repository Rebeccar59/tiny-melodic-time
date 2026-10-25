# tiny-melodic-time
# Maps clock time to musical tempo and measure positions.
#
# Only public name re-exported here is TimeMapper. Keeping the surface area
# to a single class means downstream code cannot accidentally reach into
# helpers whose signatures may change between releases.

import time

from dataclasses import dataclass, field
from typing import Callable, Tuple


# A clock is anything callable that returns a float in seconds. Tests pass
# a fake; production code passes time.monotonic. Using a protocol here would
# be overkill and would complicate the single-file story.
Clock = Callable[[], float]


@dataclass(frozen=True)
class Position:
    """A point inside the musical timeline.

    Fields:
        seconds:           The clock time this position corresponds to.
        beat:              Total elapsed beats since the epoch (measure 1,
                           beat 0). A float, so fractional beats carry
                           sub-beat phase. Never negative for non-negative
                           input seconds.
        measure:           One-based measure number. Starts at 1 so it matches
                           how musicians count. Increments at every downbeat.
        beat_in_measure:   Zero-based beat within the current measure,
                           in [0, beats_per_measure). Integer-valued in
                           practice, but typed float so callers can do
                           arithmetic without casting.
        beat_phase:        Fractional position within the current beat,
                           in [0.0, 1.0). Use this for LFO-style modulation
                           synced to the tempo.
    """

    seconds: float
    beat: float
    measure: int
    beat_in_measure: float
    beat_phase: float


@dataclass
class TimeMapper:
    """Maps clock seconds to musical tempo and measure positions.

    Construction is cheap and side-effect free. ``now()`` only reads the
    clock function, so two ``TimeMapper`` instances sharing a clock stay
    consistent.

    Args:
        bpm:               Beats per minute. Must be positive.
        beats_per_measure: Number of beats in one measure. Must be a
                           positive integer. Derived from the time
                           signature's numerator by convention.
        time_signature:    Optional (numerator, denominator) pair, kept
                           verbatim for inspection. The numerator MUST
                           match beats_per_measure or a ValueError is
                           raised, because a mismatch almost always means
                           the caller misunderstood the API.
        clock:             Callable returning current seconds. Defaults to
                           time.monotonic so that real use needs no
                           argument. Tests inject a fake.
    """

    bpm: float
    beats_per_measure: int
    time_signature: Tuple[int, int] = field(default=(4, 4))
    clock: Clock = field(default=None, repr=False)

    def __post_init__(self) -> None:
        if self.bpm <= 0:
            raise ValueError(
                f"bpm must be positive, got {self.bpm!r}"
            )
        # bool is a subclass of int in Python; reject it explicitly so
        # TimeMapper(beats_per_measure=True) fails loudly instead of
        # being silently treated as 1 beat per measure.
        if isinstance(self.beats_per_measure, bool):
            raise TypeError(
                f"beats_per_measure must be int, got "
                f"{type(self.beats_per_measure).__name__}"
            )
        if not isinstance(self.beats_per_measure, int):
            raise TypeError(
                f"beats_per_measure must be int, got "
                f"{type(self.beats_per_measure).__name__}"
            )
        if self.beats_per_measure <= 0:
            raise ValueError(
                f"beats_per_measure must be a positive integer, "
                f"got {self.beats_per_measure!r}"
            )
        if self.time_signature[0] != self.beats_per_measure:
            raise ValueError(
                f"time_signature numerator {self.time_signature[0]} "
                f"does not match beats_per_measure "
                f"{self.beats_per_measure}"
            )
        if self.time_signature[1] <= 0:
            raise ValueError(
                f"time_signature denominator must be positive, got "
                f"{self.time_signature[1]!r}"
            )
        if self.clock is None:
            self.clock = time.monotonic

    @property
    def seconds_per_beat(self) -> float:
        """Seconds per single beat at the current tempo."""
        return 60.0 / self.bpm

    @property
    def seconds_per_measure(self) -> float:
        """Seconds per full measure at the current tempo and meter."""
        return self.seconds_per_beat * self.beats_per_measure

    def at(self, seconds: float) -> Position:
        """Return the musical Position for an absolute clock time.

        Negative seconds are rejected. A clock that has not started yet has
        no defined musical position, and silently returning measure 0 would
        conflict with the one-based measure convention.

        Float comparison uses strict < 0 rather than a tolerance because the
        only legitimate source of tiny negatives is floating-point noise
        around zero, and clamping that noise to zero would hide genuine
        negative inputs from upstream bugs.
        """
        if seconds < 0:
            raise ValueError(
                f"seconds must be non-negative, got {seconds!r}"
            )

        # beats_per_measure is guaranteed positive by __post_init__, so this
        # division is safe.
        total_beats = seconds / self.seconds_per_beat
        beat = float(total_beats)

        # We add a tiny epsilon before flooring so that a seconds value that
        # lands EXACTLY on a measure boundary (e.g. 2.0 s at 120 bpm, 4/4)
        # reports the NEXT measure's downbeat, beat_in_measure 0, rather than
        # the previous measure's final beat at phase ~1.0. Without the
        # epsilon, floating-point representation of e.g. 4.0 can come out as
        # 3.999999... and floor() yields beat 3 instead of 4. The epsilon is
        # far below any perceptual threshold but large enough to overcome
        # double-precision rounding at plausible tempos.
        eps = 1e-9
        beat_index = int(beat + eps)
        measure_zero_based = beat_index // self.beats_per_measure
        measure = measure_zero_based + 1
        beat_in_measure = float(beat_index % self.beats_per_measure)

        # Phase within the current beat. Subtracted beat_index (the integer
        # part) rather than using math.fmod so the sign is always
        # non-negative for non-negative input.
        beat_phase = beat - beat_index
        # Guard against the tiny case where the epsilon pushed beat_index
        # one past a clean boundary, leaving phase slightly negative.
        if beat_phase < 0.0:
            beat_phase = 0.0
        elif beat_phase >= 1.0:
            beat_phase = 0.0

        return Position(
            seconds=float(seconds),
            beat=beat,
            measure=measure,
            beat_in_measure=beat_in_measure,
            beat_phase=beat_phase,
        )

    def now(self) -> Position:
        """Return the Position for the clock's current reading.

        Equivalent to ``mapper.at(mapper.clock())`` but expressed as a
        method so callers do not have to touch the clock directly.
        """
        return self.at(self.clock())
