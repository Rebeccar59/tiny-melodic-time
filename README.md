# tiny-melodic-time

Maps clock time to musical tempo and measure positions.

```python
from tiny_melodic_time import TimeMapper

def fake_clock():
    return 2.0  # seconds

mapper = TimeMapper(
    bpm=120,
    beats_per_measure=4,
    time_signature=(4, 4),
    clock=fake_clock,
)

pos = mapper.now()
# pos.measure == 2
# pos.beat_in_measure == 0.0
# pos.beat_phase == 0.0
```

## Why

When syncing visuals or control signals to music, you need to know two things at every instant: *which measure am I in*, and *how far through the current beat*. Deriving that by hand from `time.monotonic()` is a few lines of arithmetic that is easy to get wrong at measure boundaries, where floating-point rounding can push a clean downbeat into the tail of the previous measure. This library does those few lines correctly and returns a small immutable `Position`.

The trade-off: `TimeMapper` does not understand note values. `bpm` is beats per minute in whatever unit the caller means. If your score calls 120 bpm "quarter-note = 120", pass `beats_per_measure=4` and you get quarter-note beats. If you want eighth-note precision at the same tempo, pass `bpm=240` and `beats_per_measure=8`. The `time_signature` denominator is kept verbatim for inspection but never participates in the math; converting it would force the library to pick a beat unit, and that decision belongs upstream.

## Edge cases you will hit

- **Zero seconds is the downbeat of measure 1.** There is no anacrusis / pickup measure support. If your piece has a pickup, offset the clock you pass in.
- **A time that lands exactly on a measure boundary reports the *next* measure's downbeat**, beat 0, phase 0 — not the previous measure's last beat at phase ~1. This is deliberate and matches how step sequencers and DAWs count.
- **`time_signature`'s numerator must equal `beats_per_measure`.** A mismatch raises `ValueError`, because it almost always means the caller expected the library to derive beat count from the time signature, which it does not do.
- **Negative seconds raise.** A clock that has not started has no musical position.
