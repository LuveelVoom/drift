# Building drift searches

This guide is about writing input files: what goes in them, how to draw the
pattern, and how to set up the main kinds of search. For the full option list
run `./drift --help`; for verified patterns found so far see
[`findings/`](../../findings/README.md).

1. [What drift does, in one paragraph](#1-what-drift-does-in-one-paragraph)
2. [Anatomy of an input file](#2-anatomy-of-an-input-file)
3. [Building one, step by step](#3-building-one-step-by-step)
4. [After the search: real patterns](#4-after-the-search-real-patterns)
5. [Recipes](#5-recipes)
6. [Reference](#6-reference)
7. [Pitfalls](#7-pitfalls)

## 1. What drift does, in one paragraph

You give drift a **still life**, usually only a small part of one, and a
**spark**: a few cells that differ from it in generation 0. Every cell you
don't specify is **unknown**. drift runs the spark forward one generation at a
time. When the next generation depends on an unknown cell, it tries that cell
both ways, always keeping the still life stable. It gives up on a branch as
soon as the disturbance grows past your size limits. Every branch ends as an
**oscillator** (the disturbance repeats), a **fizzle** (it dies out and the
still life is unharmed), or **max gen** (it is still going, usually a moving
signal). drift reports only the cells it needed, so a result is part of a
pattern; `complete.py` turns it into a whole one.

## 2. Anatomy of an input file

An input file (a "config") is plain text: `option = value` lines, `#` starts a
comment, and the pattern goes at the end.

```
# --- 1. the rule and the size limits
rule = B3/S23               # any B/S, INT (e.g. B2-a3/S12) or MAP rule
max-changed = 6             # at most 6 cells may differ from the still life...
size = 4x4                  # ...and they must fit in a 4 wide x 4 high box

# --- 2. what to report
skip = fizzle               # oscillator, fizzle, stable, maxgen
per-rotor = 3               # at most 3 results per distinct oscillator

# --- 3. regions (rows/cols counted from the pattern's top-left cell)
clear = r -4 -2 -1 5        # these cells are dead (empty space)

# --- 4. the pattern (LifeHistory RLE, or dr2-style characters)
pattern:
x = 4, y = 4, rule = LifeHistory
B2AB$A2BA$B2AB$3BC!
```

That's `examples/beehive-spark.cfg`. Run it with
`./drift examples/beehive-spark.cfg`. It finishes in well under a second and
finds a cuphook and several stillaters. Any option can also be given on the
command line, where it overrides the file: `--max-changed 8`.

## 3. Building one, step by step

### Step 1: draw the starting pattern in Golly

1. **File → New**, then **Control → Set Rule**, and type `LifeHistory`. This
   is only for drawing; the search rule is set in the config.
2. Pick a drawing state in the edit bar and draw:

   | state | colour in Golly | means |
   |---|---|---|
   | 0 | empty | **unknown**: drift may decide it |
   | 1 | green | **alive**, in the still life and in gen 0 |
   | 2 | dark blue | **known dead** |
   | 3 | pale green | **the spark**: dead in the still life, alive in gen 0 |
   | 4 | red | dead in gen 0 but alive in the still life (a spark that removes a cell) |
   | 5 | yellow | alive and never allowed to change |
   | 6 | grey | dead and never allowed to change |

   **Undrawn cells are unknown, not dead.** If you want empty space somewhere,
   draw it in state 2 or add a `clear` region (step 3).

3. Draw a **stable** background: drift refuses to start if the alive and
   known-dead cells you drew aren't a still life. Cells next to unknown cells
   are fine, because drift may fill those in.
4. Select the pattern and use **Edit → Copy**. Golly puts an RLE starting
   `x = … rule = LifeHistory` on the clipboard.

For the tutorial example: a beehive in state 1, the dead cells around it in
state 2, and one spark cell in state 3 at its lower right.

### Step 2: put it in a config

Paste the RLE after a line that says `pattern:`, at the end of the file. You
can also save it as a file and write `pattern = beehive.rle`. Then add the
rule and the limits.

**Choosing limits.** `max-changed` and `size` decide how big a disturbance may
get. Bigger means bigger and higher-period results, but the search grows very
fast. Start small (6 cells, 4×4) and widen once a search finishes quickly. The
`changes:` and `sizes:` lines of results show how close they came to the
limits.

### Step 3: add regions

Regions mark areas of the space. Their coordinates count from the **top-left
cell of the pattern** you pasted: row 0, col 0, rows going down and columns
going right. Negative values are above or left of the pattern.

![beehive-spark](img/beehive-spark.svg)

The picture above (from `docs/render.py`) shows `clear = r -4 -2 -1 5`: rows
−4 to −1, columns −2 to 5, i.e. the four rows above the beehive, are empty.

| option | effect |
|---|---|
| `clear = REGION` | make the cells dead (empty space nothing may be built in) |
| `no-change = REGION` | these cells may never change |
| `no-count = REGION` | changes here don't count towards `max-changed` / `size` (use sparingly: an uncounted area can make the search explode) |
| `no-check = REGION` | the still life needn't be stable here |
| `must-reach = REGION` | only report results that change some cell here |

A REGION is `r R0 C0 R1 C1` (a rectangle with corners R0,C0 and R1,C1), or
`p R C` (one cell), `l R0 C0 R1 C1` (a line), or `t R0 C0 R1 C1 R2 C2` (a
triangle). Every region option can be repeated.

### Step 4: check it before running

```
./drift my.cfg --dry-run                          # settings and the starting picture
python3 docs/render.py my.cfg my.svg              # a picture with the regions coloured
```

In the dry-run picture:
- `o`: alive
- `.`: dead
- `,`: unknown
- `1`: spark (alive in gen 0 only)
- `0`: dead in gen 0 only

The coordinates are pattern-relative, like the regions.

### Step 5: run it

```
./drift my.cfg --jsonl results.jsonl
```

- **Text output:** each result is printed, with a summary at the end.
- **JSON:** `--jsonl` saves every result for the tools in section 4.
- **Long runs:** add `--max-steps N` to stop early, `--checkpoint run.ckpt` to
  be able to resume (Ctrl-C saves it), and `--threads N` (default: all cores).

## 4. After the search: real patterns

Each result fixes only the cells it needed. To get something you can paste
into Golly in your rule:

```
RULE=$(./drift --rule B3/S23 --show-rule | sed -n 's/^MAP: *//p')
python3 tests/complete.py results.jsonl --rule "$RULE" --best real.txt --minimize
```

This does three things:
- fills in the unknown cells with a SAT solver so the still life is complete;
- checks that the finished pattern really does what drift reported;
- shrinks the stator as far as it can.

The output keeps one pattern per distinct oscillator, highest period first.

| for | add |
|---|---|
| fizzles (catalysts) | `--kind fizzle --max-extent 8 --limit 30` |
| only oscillators that aren't billiard tables | `--no-billiards` |
| only oscillators that spark into empty space | `--sparky --keep-empty "R0 C0 R1 C1"` |

## 5. Recipes

Each recipe says what to draw and what to add. All of them have been run;
their configs are in `examples/` and `../attempts/`.

### Oscillators from a spark

**Draw:** one spark cell (state 3) and nothing else. Everything around it is
unknown, so drift designs the stator too.

![spark](img/spark.svg)

```
rule = B3/S23-a5
max-changed = 6
size = 4x4
skip = fizzle, stable
min-period = 4
pattern:
x = 1, y = 1, rule = LifeHistory
C!
```

In 22 s this found 180 distinct B3/S23-a5 oscillators, p4 to p15. Here is the
p15:

![p15](img/result-p15.svg)

### Oscillators next to a known object

**Draw:** the object in states 1/2, plus a spark cell beside it. That's the
beehive example in section 2. Use it to find oscillators or sparkers that work
next to a particular still life.

### Sparky oscillators (oscillators that throw sparks)

**Draw:** a spark cell. **Add:** clear the half-plane above it and require
changes there:

```
clear = r -60 -60 -1 60          # everything above row 0 is empty
must-reach = r -60 -60 -1 60     # and the reaction must reach into it
```

![sparky](img/sparky.svg)

Complete with
`complete.py … --best sparky.txt --minimize --sparky --keep-empty "-60 -60 -1 60"`.
That keeps only oscillators whose own cycle sparks into the empty half.

### Catalysts (useful fizzles)

**Draw:** a spark cell, or an object plus a spark. **Add:**
`skip = oscillator, stable`. Then:

```
complete.py fizzles.jsonl … --best catalysts.txt --kind fizzle --max-extent 8 --limit 30 --minimize
```

`--max-extent 8` drops long, thin reactions, which are nearly always a signal
running along a short wire.

### Spark converters

**Draw:** a spark cell. **Add:**
- clear everything except a box beside it, where the still life must fit;
- `must-reach` regions just outside the box, away from the input;
- `skip = oscillator, stable`, so the still life has to recover.

![converter](img/converter.svg)

`attempts/a5/make_converter.py H W C SIZE` writes this config for an H×W box.

### Wires (signals that travel forever)

**Draw:** a spark cell. **Add:**

```
margin = 50                       # plenty of room
max-gen = 80
skip = oscillator, fizzle, stable # keep only what is still moving
```

Results still going at gen 80 are signals running on tracks drift built.
Then:

```
python3 tests/wirecheck.py results.jsonl                       # tracks that repeat
python3 tests/wirebuild.py results.jsonl --rule "$RULE" --n N --out wire.rle
```

`wirebuild.py` checks that the signal repeats at least 3 times. It then asks a
SAT solver for an exactly periodic wire carrying it, and tests a single signal
on a long tiled copy. `--push "right c/2 3"` (or a direction such as `se`, or a
vector `R,C`) can force a speed and direction.

![wire](img/result-wire.svg)

### Turns, reflectors and converters for a wire

**Draw:** a piece of the wire, carrying its signal, cut off. Draw the signal as
state 3/4 cells. Leave the space past the cut unknown and clear the space
beside the wire. There are two ways to continue:

1. **Let drift improvise.** Keep max-gen results and check what the signal
   became (`attempts/q4i/convert/`).
2. **Connector search.** Also draw the outgoing wire, rotated, beyond a small
   gap, and leave only the gap unknown. Success is the signal arriving deep in
   the outgoing wire (`must-reach` boxes on it).

   Run a "straight" control first, an unrotated copy whose gap is a whole
   number of wire periods: it must find the missing piece of wire.
   `attempts/a5/turns2/make_connector2.py` builds all of this.

![turn input](img/turn-left.svg)

### Symmetric billiard tables

Sokwe's setup (`examples/billiard-rot180.cfg`):
- **Draw:** a 3×3 block of dr2's `4` cells (unknown and unchecked).
- **Add:** `symmetry = rot180` and `pattern-no-count`.

![billiard](img/billiard.svg)

## 6. Reference

**LifeHistory states:**

| state | meaning |
|---|---|
| 0 | unknown |
| 1 | alive |
| 2 | known dead |
| 3 | spark (alive in gen 0 only) |
| 4 | dead in gen 0 only |
| 5 | alive, never changes |
| 6 | dead, never changes |

**dr2 characters**, an alternative to RLE. Write them as lines of text after
`pattern:`, ending with `!`:

| char | still life | gen 0 | |
|---|---|---|---|
| `o` / `.` | alive / dead | same | |
| `1` / `0` | dead / alive | alive / dead | the spark |
| `,` or `?` | unknown | unknown | |
| `O` / `:` / `s` | alive / dead / unknown | same | never changes |
| `3` / `2` / `4` | alive / dead / unknown | same | not checked for stability |

**Options that shape the search** (more under `./drift --help`):

| option | effect |
|---|---|
| `max-changed`, `size WxH` | the size limits |
| `max-gen` | how long a disturbance may run (default 500) |
| `margin` | unknown cells around the pattern (default 30) |
| `symmetry` | none, hor, vert, diag, rot90, rot180, plus, x, full (background only) |
| `push "DIR SPEED [SLACK]"` | force motion. DIR: right/left/up/down, se/ne/…, or a vector `R,C`. SPEED: c/2, 2c/3, …, or 0 (stay within SLACK) |
| `skip`, `min-period`, `per-rotor`, `max-results`, `only-new` | what gets printed |

## 7. Pitfalls

- **Undrawn cells are unknown.** Empty space has to be drawn in state 2 or
  given with `clear`.
- **The background must be stable** where it is known. drift tells you the
  first cell that isn't.
- **Pasting results straight into Golly doesn't work.** Results are partial,
  and their LifeHistory RLE runs as plain Life. Use `complete.py`.
- **Storage.** Loose limits can produce millions of results. `per-rotor`
  (default 10) and `max-results` (default 10,000) keep the output small.
- **`no-count` areas** let anything happen inside them uncounted, which can
  make the search explode. Prefer counting everything with looser limits.
- **A repeating track isn't a wire.** A disturbance that zigzags along a track
  drift improvised can look periodic. `wirebuild.py` only accepts signals that
  repeat 3 times.
