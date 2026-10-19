# Findings

These are complete patterns found with drift and finished with `drift/tools/finish.py`. Each file holds plain RLE in its rule, ready to paste into
Golly. Every pattern was re-simulated after completion. Where a separate
implementation of the rule was written (B3/S23-a5 and HighLife), it was
checked with that too. The q4i patterns were checked with drift's rule table
only.

How each kind of file was made:

- **`oscillators.txt`**:
  - a spark search, one spark cell in an unknown background (`attempts/*/spark.cfg`);
  - then `finish.py`.

  This gives one oscillator per distinct rotor, highest period first. "Life
  rotor" means the rotor matches an oscillator in Life's `knownrotors` list.
- **`sparky.txt`**: the same, with empty space above the start, with
  `must-reach` regions. These oscillators throw a spark into empty space in
  their own cycle. Spark depth 1 means the spark is born next to the object;
  2 or more means it is a free spark.
- **`fizzles.txt`**: reactions where a spark hits a still life that then
  recovers completely, i.e. catalysts.
  - From `finish.py`.
  - Rotors longer than 8 cells are left out: those are nearly always a signal
    running along a short wire.
  - Sorted by how long the reaction lasts.
  - Each pattern is the still life plus the spark cell.
- **`converters.txt`**: a spark in, a spark out elsewhere, and the still life
  recovers (`attempts/a5/make_converter.py`).
- **`wire-*.rle`**: a wire with a signal on it. Each one is a whole number of
  repeats long and carries one signal.

## B3/S23-a5

- **180 oscillators**, p4 to p15, from a 22 s search with 6 changed cells in
  4×4. The highest periods are a p15 (52 cells), a p13 (44 cells) and three
  p11s. 162 have exposed rotors and 18 are billiard tables.
- **3 sparky oscillators.**
- **One 18-cell spark converter**, working with two input positions.
- **Diagonal 5c/11 wire:** found from a drift signal, completed by hand. The
  signal moves 10 cells every 22 gens; the wire repeats every (−10,+10).
- **Diagonal 2c/3 wire:** the signal moves (+4,+4) every 6 gens; the wire
  repeats every (6,6).
- **Turns and 180° reflectors** for both wires: none found. See
  `attempts/a5/turns2/README.md`.

## B3/S23-q4i

- **260 oscillators**, p3 to p14 plus a 236-cell p60. The p60 may be several
  interacting rotors (60 = 3·4·5). 228 aren't Life rotors. The highest
  periods besides the p60 are three p14s (50–63 cells), a p12 (42 cells) and
  a p11 (52 cells).
- **1 sparky oscillator:** a 24-cell p4 with a free spark (depth 2).
- **30 catalyst fizzles**, chosen from 758 compact reactions; the longest
  reaction lasts 21 gens.
- **Diagonal 2c/3 wire** (`wire-diagonal-2c3.rle`):
  - found by drift's free signal search (`attempts/q4i/signals.cfg`), then
    made exactly periodic by `wirebuild.py`;
  - the wire repeats every (4,4) with 41 live cells per repeat;
  - a single signal crosses a 40-repeat test wire unchanged.
- **Not an oblique signal:** results #6547 and #2657 of that search looked
  like an oblique (4,1)c/6 signal, but the disturbance repeats only once.
  It's an irregular disturbance that wanders along a zigzag track drift
  improvised for it, lasting about 80 gens. An example is in
  `attempts/q4i/meander-6547.rle`.

## B36/S23 (HighLife)

- **37 oscillators**, p3 to p10. 35 aren't Life rotors. The best are a 41-cell
  p10 and an 84-cell p7.
- **3 sparky p9s**, 27–30 cells, each throwing a spark next to the object.
- **30 catalyst fizzles** (84 compact reactions); the longest lasts 11 gens.
- **Diagonal 5c/6 wire** (`wire-diagonal-5c6.rle`):
  - found by a free drifter search from one spark (9 changed cells in 4×4,
    `no-rechange = 8,80`; config and scripts in `B36-S23/wire-5c6-work/`);
  - the signal is 3 cells and moves (+5,+5) every 6 gens; the wire repeats
    every (5,5);
  - end caps found by SAT with the fewest cells; the signal runs the length
    of the wire, but the far cap isn't a clean eater (3 cells stay changed);
  - a glider-to-signal end cap: 42 lanes × 3·10⁸ steps found nothing (to do).
- **No signals** within 6 changed cells in 4×4, and no converters.
