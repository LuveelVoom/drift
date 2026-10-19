# Turns and 180° reflectors by connector search

Two B3/S23-a5 wires:

| file | signal | wire repeat |
|---|---|---|
| `wire2.rle` | diagonal 2c/3, heading down-right, (+4,+4) per 6 gens | (6,6) |
| `../turns/wire-5c11.rle` | diagonal 5c/11, heading up-right, (−10,+10) per 22 gens | (−10,+10) |

`make_connector2.py WIRE MODE A B [C SIZE]` writes a search where **both**
wires are given and only the gap between them is unknown:

- **incoming:** the wire, cut a little after its signal (signal in a known phase);
- **outgoing:** a copy of the wire, end cap included, turned `right` or `left`
  (90°), or reflected (180°, `reflect-right` / `reflect-left`: lying beside the
  incoming wire on that side and heading back);
- the copy's open end sits at E + A·heading + B·side, where E is the end of the
  incoming wire;
- **connector zone:** cells within `ZONE` (environment variable) of the segment
  between the two ends are unknown; everything else is known (wire or dead).

**Success:** the signal travels into the outgoing wire and is absorbed by its
end cap. drift reports that as a fizzle that reaches `--must-reach` boxes
placed far along the outgoing wire.

## Controls

`straight` mode places an unrotated copy whose shift is a whole number of
wire repeats, so the right connector is simply the missing piece of wire.
A setup is only trusted if this control finds it.

| wire | ZONE | gap A | control |
|---|---|---|---|
| 2c/3 | 3 | 7 | found, whole search 0.8 s |
| 2c/3 | 4, 5 | 7 | not found within 1.5·10⁹ steps (too big a search) |
| 5c/11 | 7 | 3 | found |
| 5c/11 | 3, 5 | 3 | the wire's cut end doesn't fit (it's about 12 cells wide) |
| 5c/11 | 7 | 13 | not found within 10¹⁰ steps |

Lessons:
- The 5c/11 wire is short: only along −16…20 is periodic, and its end cap
  starts at about 26. The incoming cut must be inside the periodic part.
- `make_turn.py`, which asked drift to build the outgoing wire as well, found
  nothing. That's a much harder search than this connector one.

## Results

**2c/3 wire, ZONE 3** (`scan4.sh`, log `scan4.log`):
- 225 runs: right and left turns with A 3…11 and B −3…5, and reflectors on
  both sides with A −3…4 and B 7…11;
- 220 searches finished completely, 5 hit the 3·10⁹-step cap;
- **nothing found**: no turn or reflector fits in a radius-3 connector at these
  alignments.

**5c/11 wire, ZONE 7, 10 changed cells in 6×6** (`scan5.sh`, log `scan5.log`):
- stopped early, after 110 runs (turns with A up to about 7);
- nothing found.
