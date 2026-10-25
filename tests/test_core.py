"""Unit tests for tiny_melodic_time.core.

Every test is deterministic. No wall-clock reads, no sleeps, no float ==.
Where a float comparison is unavoidable we use assertAlmostEqual with a
fixed delta so slow CI machines cannot make the test flaky.
"""

import math
import unittest

from tiny_melodic_time.core import Position, TimeMapper


class TestConstruction(unittest.TestCase):
    def test_default_clock_is_set_when_none(self):
        # We do not call now(); we only confirm the attribute is populated so
        # that a later call would not raise AttributeError.
        mapper = TimeMapper(bpm=120, beats_per_measure=4)
        self.assertIsNotNone(mapper.clock)

    def test_bpm_must_be_positive(self):
        with self.assertRaises(ValueError):
            TimeMapper(bpm=0, beats_per_measure=4)
        with self.assertRaises(ValueError):
            TimeMapper(bpm=-10, beats_per_measure=4)

    def test_beats_per_measure_must_be_positive(self):
        with self.assertRaises(ValueError):
            TimeMapper(bpm=120, beats_per_measure=0)
        with self.assertRaises(ValueError):
            TimeMapper(bpm=120, beats_per_measure=-3)

    def test_beats_per_measure_rejects_bool(self):
        # bool is a subclass of int; True would silently mean 1 beat/measure.
        with self.assertRaises(TypeError):
            TimeMapper(bpm=120, beats_per_measure=True)

    def test_time_signature_numerator_must_match_beats_per_measure(self):
        with self.assertRaises(ValueError):
            TimeMapper(
                bpm=120,
                beats_per_measure=4,
                time_signature=(3, 4),
            )

    def test_time_signature_denominator_must_be_positive(self):
        with self.assertRaises(ValueError):
            TimeMapper(
                bpm=120,
                beats_per_measure=4,
                time_signature=(4, 0),
            )


class FakeClock:
    """Deterministic stand-in for time.monotonic."""

    def __init__(self, start: float = 0.0) -> None:
        self.t = start

    def __call__(self) -> float:
        return self.t


class TestMapping(unittest.TestCase):
    def setUp(self) -> None:
        self.clock = FakeClock()
        self.mapper = TimeMapper(
            bpm=120,
            beats_per_measure=4,
            time_signature=(4, 4),
            clock=self.clock,
        )

    def test_zero_seconds_is_measure_one_downbeat(self):
        p = self.mapper.at(0.0)
        self.assertEqual(p.measure, 1)
        self.assertEqual(p.beat_in_measure, 0.0)
        self.assertEqual(p.beat, 0.0)

    def test_one_beat_later(self):
        # 120 bpm => 0.5 s per beat.
        p = self.mapper.at(0.5)
        self.assertEqual(p.measure, 1)
        self.assertEqual(p.beat_in_measure, 1.0)
        self.assertAlmostEqual(p.beat_phase, 0.0, delta=1e-9)

    def test_measure_boundary_reports_next_measure(self):
        # 2.0 s = 4 beats = exactly one measure. The library's stated
        # convention: this is the downbeat of measure 2, not the last beat
        # of measure 1.
        p = self.mapper.at(2.0)
        self.assertEqual(p.measure, 2)
        self.assertEqual(p.beat_in_measure, 0.0)

    def test_mid_measure_in_third_measure(self):
        # 5.25 s at 120bpm 4/4 => 10.5 beats => measure 3 (11th beat is
        # beat 2 of measure 3, 0-based index 1), phase 0.5.
        p = self.mapper.at(5.25)
        self.assertEqual(p.measure, 3)
        self.assertEqual(p.beat_in_measure, 2.0)
        self.assertAlmostEqual(p.beat_phase, 0.5, delta=1e-9)

    def test_negative_seconds_rejected(self):
        with self.assertRaises(ValueError):
            self.mapper.at(-0.001)

    def test_now_uses_clock(self):
        self.clock.t = 1.0
        p = self.mapper.now()
        self.assertEqual(p.seconds, 1.0)
        # 1.0 s at 120bpm 4/4 => beat 2 of measure 1.
        self.assertEqual(p.measure, 1)
        self.assertEqual(p.beat_in_measure, 2.0)

    def test_seconds_per_beat_and_measure(self):
        self.assertAlmostEqual(self.mapper.seconds_per_beat, 0.5, delta=1e-9)
        self.assertAlmostEqual(
            self.mapper.seconds_per_measure, 2.0, delta=1e-9
        )


class TestThreeFour(unittest.TestCase):
    """3/4 time, 90 bpm => 2/3 s per beat, 2.0 s per measure."""

    def setUp(self) -> None:
        self.clock = FakeClock()
        self.mapper = TimeMapper(
            bpm=90,
            beats_per_measure=3,
            time_signature=(3, 4),
            clock=self.clock,
        )

    def test_one_full_measure(self):
        p = self.mapper.at(2.0)
        self.assertEqual(p.measure, 2)
        self.assertEqual(p.beat_in_measure, 0.0)

    def test_two_beats_in(self):
        # 2/3 s per beat * 2 = 4/3 s => beat index 2 (0-based), measure 1.
        p = self.mapper.at(4.0 / 3.0)
        self.assertEqual(p.measure, 1)
        self.assertEqual(p.beat_in_measure, 2.0)


class TestFastTempo(unittest.TestCase):
    """240 bpm, 2/4. Guards against float noise at fast tempos."""

    def setUp(self) -> None:
        self.clock = FakeClock()
        self.mapper = TimeMapper(
            bpm=240,
            beats_per_measure=2,
            time_signature=(2, 4),
            clock=self.clock,
        )

    def test_measure_boundary_stable(self):
        # 0.5 s = 2 beats = one measure. Must be measure 2 downbeat.
        p = self.mapper.at(0.5)
        self.assertEqual(p.measure, 2)
        self.assertEqual(p.beat_in_measure, 0.0)
        # phase must be exactly representable as 0 after clamping.
        self.assertLess(p.beat_phase, 1e-6)


class TestPositionShape(unittest.TestCase):
    def test_position_fields(self):
        mapper = TimeMapper(
            bpm=120, beats_per_measure=4, clock=FakeClock()
        )
        p = mapper.at(0.75)
        self.assertIsInstance(p, Position)
        # 0.75 s at 120bpm 4/4 => beat 1.5 => measure 1, beat 1, phase 0.5.
        self.assertEqual(p.measure, 1)
        self.assertEqual(p.beat_in_measure, 1.0)
        self.assertAlmostEqual(p.beat_phase, 0.5, delta=1e-9)
        # beat is the raw fractional total, kept as a float.
        self.assertIsInstance(p.beat, float)


if __name__ == "__main__":
    unittest.main()
