# drift

drift searches cellular automata for **drifters**: small disturbances that
travel through a stable background and, along the way, may turn into
oscillators, die out, or keep moving. It is a port of Dean Hickerson's
**dr2.c** (1997, extended in 2014) and adds:

- **Rules**: Life-like (B3/S23), INT (`B2-a3/S12`) and Golly `MAP…` rules.
- **Configuration**: named options and config files instead of dr2's numbered variables.
- **Patterns**: drawn in Golly; results come back as RLE you can paste into Golly.
- **Long runs**: all CPU cores, a progress line, and saving/resuming.
- **Speed**: 1.5–5.5× dr2 on one core, about 9× more on 14 cores.

Contents: [Build](#build) · [How a search works](#how-a-search-works) ·
[Walkthrough](#walkthrough) · [Reading results](#reading-results) ·
[Setting up your own search](#setting-up-your-own-search) · [Recipes](#recipes) ·
[Long runs](#long-runs) · [Coming from dr2](#coming-from-dr2) · [Tests](#tests)

## Build

    make

This builds `./drift`. Keep the `knownrotors` file next to it; it's the list
of known Life oscillators used to name results.

## How a search works

drift keeps track of two patterns:

- the **background**, which must be a still life, and
- the **current generation**, which differs from the background in a few
  cells, the **changed** cells.

At the start almost every cell is **unknown**. You supply a small known part
of the background and mark a few cells that differ from it in generation 0
(the disturbance, or "spark"). drift then computes generation 1, 2, 3, … of
the disturbance. Whenever the next generation depends on an unknown
background cell, it tries that cell both ways: off and on. Every choice must
keep the background stable.

A branch is abandoned as soon as the changed cells get too many or too spread
out. You set those limits with `--max-changed` and `--size`. This is what
keeps the search small: drift only looks for disturbances that stay small.
Every branch ends in one of these outcomes:

| outcome | meaning |
|---|---|
| **oscillator** | the changes repeat: the spark started an oscillator (the usual goal) |
| **fizzle** | the changes die out and the background is unchanged: e.g. an eater ate something |
| **stable** | the changes settle into a different still life. Printed only when the remaining changes are all in a `--no-count` area ("semifizzle") |
| **max gen** | still going at `--max-gen` (default 500) without repeating: usually a moving signal. Rare and interesting |

drift explores every branch, so the search is exhaustive within your limits.
**Results are partial patterns.** drift only fixes the background cells it
needed, and everything else stays unknown. To get a real pattern you complete
the rest of the still life yourself, by hand or with a still-life completion
tool.

## Walkthrough

This is the example from dr2's documentation: a single cell switched on
between two rows of three, in an otherwise unknown background.

**1. Write the config** (`examples/stillater.cfg`):

```
rule = B3/S23
max-changed = 3     # at most 3 changed cells in any generation
size = 3x3          # ... inside a 3x3 box (width x height)
skip = fizzle       # don't print fizzles

pattern:
ooo
.1.
ooo!
```

In the pattern, `o` is a live background cell, `.` a dead one and `1` a cell
that is dead in the background but alive in generation 0. Any cell not shown
is unknown.

**2. Check the setup**, without searching:

    ./drift examples/stillater.cfg --dry-run

This prints the settings and the starting position.

**3. Run it:**

    ./drift examples/stillater.cfg

It finishes in a fraction of a second with 92 oscillators, all already known
(16 of them stillaters, 12 burloaferimeters, 10 cuphooks, …). Here is the
first one:

```
***** #1 oscillator p3 from gen 1: stillater (SC 3.1.2)
rotor:   p3 r3 2x2 .2 2A
history: u4 r4 2x3 .B. 2AD
changes: 1 1 2 1 1
sizes:   1x1 1x1 2x1 1x1 1x1
gen 0, rows -5..5, cols -3..6
,
,
,,,oo.
,,,.o.o.
,,....oo
,,oooo..
,,..1.oo
,,.ooo..
,,o....o
,
,
x = 6, y = 7, rule = LifeHistory
.2AB$.BABAB$4B2A$4A2B$2BCB2A$B3A2B$A4BA!
```

**4. Look at it in Golly.** Copy the two RLE lines and paste them into Golly.
Live cells are state 1, known dead cells state 2, and the spark is state 3
(4 would mean "alive in the background, dead in gen 0").

**5. Complete it.** The unknown cells (`,`) still need filling in with a
stable background. dr2's documentation completes this result as follows (`1`
is the spark cell):

```
..oo..........
..o.o.........
....o..oo.....
...oo.o.o.....
.o....o.......
.oooo..o......
.....ooo....oo
...o....oo..o.
.ooooooo..o.o.
o....1.o..oo..
.oooooo.......
..............
...oo.........
...oo.........
```

Without the `1` cell it is a still life; with it, it becomes the stillater.

## Reading results

Each result starts with a line of the form
`***** #number kind details: name`.

- **`p3 from gen 1`**: period 3, repeating from generation 1 onwards.
- **The name** comes from `knownrotors`, a list of about 4,500 known Life
  oscillators. `SC` = Dean Hickerson's stamp collection, `DJB` = David
  Buckingham's collection, `new …` = found by dr. **`NEW ROTOR`** means the
  oscillator isn't in the list: these are the ones to look at. **`split
  rotor, gap N`** means the moving part is two or more separate pieces,
  usually known oscillators side by side, so less exciting.
  - Most results are already known. `--only-new` prints only the others.
  - The same oscillator can appear many times with different backgrounds; each
    one is a different way to build it.
  - For rules other than B3/S23 there is no list, so every oscillator shows as
    `NEW ROTOR`.
- **`rotor:`** describes the rotor, the cells that oscillate (Hickerson's
  rotor descriptor). For `p3 r3 2x2 .2 2A`:
  - `p3`: period 3.
  - `r3`: the rotor has 3 cells.
  - `2x2`: they fit in a 2×2 box.
  - `.2 2A`: the rows of that box in gen 0.
    - `.`: not part of the rotor.
    - A digit: a rotor cell that is dead in gen 0, with that many live
      neighbours in the stator (the part that doesn't change).
    - `@ A B C …`: a rotor cell that is alive in gen 0, with 0, 1, 2, 3, …
      live stator neighbours.

  The descriptor doesn't depend on how the oscillator is rotated or which
  phase you start from, which is how known ones are recognised.
- **`history:`**: the same kind of description, covering everything that
  changed from generation 0 until the end. Fizzles are recognised by it
  (e.g. `g-eater 6.3`).
- **`changes:` / `sizes:`**: the number of changed cells and the size of their
  bounding box in each generation 0, 1, 2, …. Use them to judge whether
  `--max-changed` and `--size` are too tight.
- **The picture**: the known background with generation 0 on top.
  - `o`: alive.
  - `.`: dead.
  - `,`: unknown.
  - `1`: alive in gen 0 only.
  - `0`: dead in gen 0 only.

  Rows and columns are counted from the top-left cell of your pattern, the
  same numbering the region options use.
- **The RLE**: every known cell, in Golly's LifeHistory rule (see the table
  below).

At the end comes a summary of how many outcomes of each kind were found.
`--jsonl FILE` also writes each result as one JSON line, including a plain
on/off RLE of generation 0 in your rule.

## Turning results into real patterns

Pasting a result's RLE into Golly won't show a working oscillator. Its unknown
cells count as dead there, and the LifeHistory rule runs plain Life rather
than your rule. `tests/complete.py` finishes the job for you. It fills in the
unknown cells with a SAT solver so that the whole background is a real still
life, then simulates the finished pattern in your rule to confirm the
oscillator. It needs `pip install python-sat`.

    ./drift my.cfg --jsonl results.jsonl --per-rotor 8
    python3 tests/complete.py results.jsonl --rule "$(./drift --rule B3/S23-a5 --show-rule | sed -n 's/^MAP: *//p')" --best real.txt

`real.txt` then holds one working, complete pattern per distinct rotor,
highest period first, as plain RLE in your rule. Add `--minimize` to shrink
each stator. The rotor's behaviour stays fixed phase by phase, and a SAT
solver finds the fewest live stator cells within 4 cells of the rotor
(`--min-margin`, `--min-seconds`). Every minimised pattern is re-simulated
before it's kept; in tests stators came out about 70% smaller.

Some results can't be completed. drift only checks that each 3×3 window of
the background is possible, so a large partial background (typically from a
long transient) may have no still life that fits all of it. `--best` simply
tries other results with the same rotor. dr2 has the same limitation.

`--per-rotor N` prints at most N results per rotor. Without it a search can
print thousands of copies of the same few oscillators.

## Setting up your own search

### The pattern

Draw it in Golly with the **LifeHistory** rule (Control → Set Rule), select it,
copy it and save the clipboard to a file:

| state | meaning |
|---|---|
| 0 | unknown |
| 1 | alive (background and gen 0) |
| 2 | known dead |
| 3 | alive in gen 0 only (dead in the background) — the spark |
| 4 | dead in gen 0 only (alive in the background) |
| 5 | alive, and may never change |
| 6 | dead, and may never change |

Then use `--pattern FILE` on the command line or `pattern = FILE` in a config.
The pattern can also be written straight into a config after a `pattern:`
line, either as RLE or in dr2's characters:

| char | background | gen 0 | |
|---|---|---|---|
| `o` / `.` | alive / dead | same | |
| `1` / `0` | dead / alive | alive / dead | the spark |
| `,` or `?` | unknown | unknown | |
| `O` / `:` / `s` | alive / dead / unknown | same | may never change |
| `3` / `2` / `4` | alive / dead / unknown | same | background not checked for stability |

The background part of your pattern must be stable (drift tells you which cell
isn't), and at least one cell must differ in gen 0 (or be a `2`/`3`/`4` cell).
The search space is sized automatically: `--margin` (default 30) unknown cells
on each side.

### Limits

`--max-changed N` and `--size WxH` matter most. Start small and widen them.
Searches grow very fast: a jump from 3 to 6 changed cells can turn a
sub-second search into hours. Use `--max-steps N` or Ctrl-C to stop a run
early.

### Regions

Some options take a **region**. The rows and columns are counted from the
top-left cell of the pattern, and negative values are allowed:

| region | syntax |
|---|---|
| rectangle | `r R0 C0 R1 C1` (the `r` may be left out) |
| line | `l R0 C0 R1 C1` |
| point | `p R C` |
| triangle | `t R0 C0 R1 C1 R2 C2` |

| option | effect |
|---|---|
| `--clear REGION` | make unknown cells there dead: keeps the area empty, e.g. a path for an incoming glider |
| `--no-change REGION` | cells there may never change |
| `--no-count REGION` | changes there don't count towards the limits; a result whose changes end up only there is a "semifizzle" |
| `--no-check REGION` | the background there needn't be stable |

Each option can be given several times. `--allow-change`, `--count` and
`--check` undo the corresponding option for a sub-region.

### Symmetry

`--symmetry hor|vert|diag|rot90|rot180|plus|x|full` makes the *background*
symmetric about the centre of your pattern. Generation 0 is not mirrored, so
draw the spark symmetric yourself if you want symmetric results.

### Rules

`--rule` takes `B3/S23`, `B36/S23`, INT rules like `B2-a3/S12`, or a Golly
`MAP…` string. `--show-rule` prints a rule's canonical and MAP forms. Rules
with B0 aren't supported.

## Recipes

These have all been run. Commands are shown from the `drift` directory.

**Oscillators started by a single spark cell, in an INT rule**
(`examples/int-sparker.cfg`). Finishes in about a second and prints
thousands of results:

```
rule = B3-c/S23
max-changed = 5
size = 3x3
skip = fizzle
pattern:
x = 1, y = 1, rule = LifeHistory
C!
```

**Symmetric billiard tables** (`examples/billiard-rot180.cfg`). This is
Sokwe's setup from the ConwayLife forum:

- the centre 3×3 starts unknown and unchecked (`4`);
- `pattern-no-count` stops it counting towards the limits;
- the background has 180° symmetry;
- `only-new` hides known oscillators.

This search is large; let it run, and checkpoint it (see Long runs).

```
max-changed = 18
size = 9x9
symmetry = rot180
pattern-no-count
skip = stable, fizzle
only-new
pattern:
444
444
444!
```

**Glider eaters** (`examples/glider-eater.cfg`). A glider flies south-east through a cleared region. Eaters
show up as fizzles named `g-eater …`; anything not named is new. Stopped after
1.5 billion steps (about 6 seconds on 14 cores), this had found 60 fizzles, as
well as many glider-to-oscillator conversions:

```
max-changed = 10
size = 5x5
clear = r -12 -12 5 5     # empty space the glider arrives through
skip = oscillator         # show only fizzles (eaters)
pattern:
.1.
..1
111!
```

## Long runs

- **Threads**: `--threads N` (default: all cores). Results then arrive in a
  different order from a one-thread run, but the set of results is the same.
- **Progress**: while running, a progress line on stderr shows the share
  explored (a rough estimate), the speed, results so far and an estimated time
  left. `--quiet` turns it off.
- **Saving and resuming**: `--checkpoint run.ckpt` saves the search every 5
  minutes (`--checkpoint-every SECONDS`) and when you press Ctrl-C. Resume
  with `./drift --resume run.ckpt`, adding options like `--threads` if you
  want. Results already printed aren't printed again. Results go to stdout, so
  redirect them (`> results.txt`, `>> results.txt` when resuming).
- **Stopping early**: `--max-steps N` stops after about N search steps.

## Coming from dr2

Old input files work unchanged: `./drift --classic < old.in` prints dr2's
own output. With one thread and the same seed, the results and their order
are the same as dr2's (`--threads N` may be added). The table below maps
dr2's commands to drift's options.

| dr2.c | drift |
|---|---|
| `c#`, `w#`, `h#` | `--max-changed`, `--max-width`, `--max-height` (`--size WxH`) |
| `r# #` + grid | `--pattern FILE` / `pattern:` |
| `C`, `d0`/`D0`, `d1`/`D1`, `d2`/`D2` | `--clear`, `--no-change`/`--allow-change`, `--no-count`/`--count`, `--no-check`/`--check` |
| `Rrule` | `--rule` (Golly reading: `23/3` = B3/S23) |
| `s#`, `P#` | `--seed`, `--prob` |
| `H#`, `W#` | `--grid HxW` or `--margin N` |
| `horsymm` … `fullsymm` | `--symmetry hor/vert/diag/rot90/rot180/plus/x/full` |
| `skipstable`, `skipfizzle`, `nopics`, `showfin`, `showall` | `--skip stable,fizzle`, `--no-pics`, `--show-final`, `--show-all` |
| `cc # # …` | `--change-counts` |
| `K file` | `--known-rotors` |
| v100 / v125 / v126 | `--relax-changed` / `--relax-height` / `--relax-width` |
| v101, v117+v118 | `--max-new-changed`, `--max-new-changed-vs N,G` |
| v102, v103 | `--diag-width-ne`, `--diag-width-nw` |
| v104, v105, v109 | `--push-right`, `--push-down`, `--push-down-c2` (relative to the pattern) |
| v106 | `--count-from-gen` |
| v107+v108 | `--no-rechange A,B` |
| v110 | `--max-twos` |
| v111 + v132–v135 | `--persist N` + `--persist-region R0 C0 R1 C1` |
| v112, v113 | `--split-vertical`, `--split-horizontal` |
| v114, v115 | `--symmetry-from` |
| v116 | `--forbid-5c9` |
| v119 | `--fizzle-gen0-only` |
| v120 | `--min-changed` |
| v121+v122, v123+v124 | `--forbid-count G,N`, `--require-count G,N` |
| v127 | `--pattern-no-count` |
| v128 | `--same-shape-every` |
| v129 | `--max-age-sum` |
| v130 | `--day-night` |
| v131 | `--min-period` (hides small periods) |
| v136 (Just Friends) | not needed: use the INT rule |
| v137+v138, v139 | `--max-consec-sum K,G`, `--max-neighbors` |
| any `v# #` | `--var N,V` (absolute coordinates) |

### Differences from dr2

**Order and placement.** In dr2, command order mattered: for example,
`d2` regions had to come before the read command. drift applies region flags
first, then the pattern, then clears, so order doesn't matter. Symmetries are
centred on the pattern rather than the 81×81 space.

**Rule tables.** The rule is applied with two lookup tables indexed by the
3×3 window of off/on/unknown cells. For B/S rules they force exactly the
cells dr2 forces (checked in `tests/ruletest.cpp`). For INT and MAP rules
each unknown neighbour can be forced on its own.

**dr2 bugs not reproduced:**
- **The `v# #` command on 64-bit builds.** dr2 reads it with `%d` into a
  `long`, leaving garbage in the high bytes, so most `v` settings silently do
  nothing. The original 2014 `dr2.exe` was 32-bit, so it isn't affected.
- **A stray (0,0) cell** appended to every neighbour list once a pattern is
  read. It only makes dr2 do a few extra no-op steps.
- **The DONTCHECK cell list**, which dr2 restarts on each read command.
- **The dead border is not checked for stability.** In dr2, results that reach
  the edge of the space can rely on border cells that would really be born,
  which makes them impossible to complete. drift checks the border (everything
  outside the space is dead). `--unchecked-border` and `--classic` keep dr2's
  behaviour.

## Tests

    make test                      # rule tables + comparison with dr2.c
    tests/ruletest                 # rule tables vs dr2's logic and direct simulation
    python3 tests/regress.py       # --classic output vs dr2.c, block by block
    python3 tests/bench.py         # speed vs dr2.c on identical work
    python3 tests/validate.py results.jsonl [--rule MAP…]   # re-simulate results independently
    python3 tests/complete.py results.jsonl --rule MAP… --best real.txt --minimize   # real, small patterns

The comparison with dr2 needs the original program built with the `v` fix,
in `../ref`:

    cd ../ref && unzip -o ../dr2.zip knownrotors
    cc -O2 -w -std=gnu89 -include stdlib.h -include string.h -include ctype.h -o dr2fixed dr2fixed.c

(`dr2fixed.c` is `../dr2.c` with `"%d %d"` changed to `"%d %ld"` in the
`v` command.)
