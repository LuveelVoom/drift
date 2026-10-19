# Findings

These are complete patterns found with drift and finished with the tools in
`drift/tests/`. Each file holds plain RLE in its rule, ready to paste into
Golly. Every pattern was re-simulated after completion. Where a separate
implementation of the rule was written (B3/S23-a5 and HighLife), it was
checked with that too. The q4i patterns were checked with drift's rule table
only.

How each kind of file was made:

- **`oscillators.txt`**:
  - a spark search, one spark cell in an unknown background (`attempts/*/spark.cfg`);
  - then `complete.py --best --minimize`.

  This gives one oscillator per distinct rotor, highest period first. "Life
  rotor" means the rotor matches an oscillator in Life's `knownrotors` list.
- **`sparky.txt`**: the same, with empty space above the start, then
  `--sparky --keep-empty`. These oscillators throw a spark into empty space in
  their own cycle. Spark depth 1 means the spark is born next to the object;
  2 or more means it is a free spark.
- **`fizzles.txt`**: reactions where a spark hits a still life that then
  recovers completely, i.e. catalysts.
  - From `complete.py --best --kind fizzle --max-extent 8`.
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
- **Oblique (4,1)c/6 signal:** results #6547 and #2657 of that search. It is
  real on drift's improvised track, but no exactly periodic wire was found
  with repeats up to 6 signal steps and a band up to 8 cells wide.

## B36/S23 (HighLife)

- **37 oscillators**, p3 to p10. 35 aren't Life rotors. The best are a 41-cell
  p10 and an 84-cell p7.
- **3 sparky p9s**, 27–30 cells, each throwing a spark next to the object.
- **30 catalyst fizzles** (84 compact reactions); the longest lasts 11 gens.
- **No signals** within 6 changed cells in 4×4, and no converters.
