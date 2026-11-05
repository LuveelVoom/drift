# drift: notes for developers

How drift is built, the decisions behind it, what has been measured, and what
is still open. For using drift, see [drift/README.md](drift/README.md) and
[drift/docs/GUIDE.md](drift/docs/GUIDE.md).

## 1. What this project is

`drift` is a C++17 port of Dean Hickerson's **dr2.c**, a drifter search for
Life-like cellular automata. It tracks a stable background and a current
generation that differs from it in a few cells, chooses unknown background
cells as needed, and backtracks when the changed region gets too big.

The goals:
1. INT (and MAP) rules;
2. much easier to use in every respect;
3. faster and more flexible.

| Path | What it is |
|---|---|
| `drift/src/rule.*` | Rule parsing (B/S, Hensel INT, MAP) and the 3^9 lookup tables |
| `drift/src/search.*` | The search core, a function-by-function port of dr2.c |
| `drift/src/options.*` | Named options, config files, pattern loading (LifeHistory RLE or dr2 chars) |
| `drift/src/classic.cpp` | dr2's command language (`drift --classic < old.in`) |
| `drift/src/report.*` | Output: dr2's exact format (classic) or drift's format, RLE, JSON lines |
| `drift/src/main.cpp` | Threads, work splitting, progress line, checkpoint/resume, Ctrl-C |
| `drift/tools/` | `survey.py` (`drift survey RULE`), `soups.c`, `finish.py` (complete/check/sort/shrink; run by drift after a search), `driftlib.py` (shared: rules, RLE, SAT completion and minimisation), `render.py`, `wirecheck.py`, `wirebuild.py`, `validate.py` |
| `drift/tests/` | `ruletest.cpp`, `regress.py` (vs dr2), `bench.py` |
| `dr2.c`, `dr2.zip` | The original; `dr2.zip` has `dr.documentation.txt` and `knownrotors` |
| `ref/dr2fixed.c` | The oracle: dr2.c with `"%d %d"` → `"%d %ld"` in the `v` command |

## 2. How it works (decisions worth keeping)

**Rule tables.** A 3×3 window is encoded in base 3 (off 0, on 1, unknown 2;
position k has weight 3^k, positions row-major from NW). There are two tables:
- `next3[code]`: the next state of the centre (off, on or unknown);
- `cons3[code]`: whether the window can still be a still life, plus 9-bit
  masks of the cells it forces on and off.

The per-cell code is kept up to date incrementally, like dr2's `naysum`. For
B/S rules `cons3` forces exactly what dr2's `consistable` forces, proven
exhaustively by `tests/ruletest`. That's why a single-threaded run is
identical to dr2.

**Hensel bit order.** NW=0x80 N=0x40 NE=0x20 W=0x10 E=0x08 SW=0x04 S=0x02
SE=0x01, with r-1 = north. The class table comes from catforce-int.

**Threads.** Every free choice is recorded as a decision. A subtree is the
list of decision values that leads to it. A worker replays that path (with
the replayed choices locked, so backup can't undo them), then searches below.
Idle workers get the untried branch of a busy worker's shallowest free
decision.

**Checkpoints.** A checkpoint is the list of unexplored paths, collected while
all workers are paused. It also holds the dedupe hashes, the counts and the
original arguments, plus a fingerprint of the search settings.

**Modern mode.**
- Coordinates are relative to the pattern's top-left cell.
- The grid is the pattern plus `--margin` (default 30) on each side, plus dr2's
  2-cell fixed border.
- Region flags are applied, then the pattern is read, then clears.

## 3. Known facts and measurements

- **dr2 bugs.** On 64-bit builds, `v# #` reads `%d` into a `long`, so most `v`
  settings are garbage and silently do nothing. dr2 also appends a stray (0,0)
  cell to every neighbour list; that shifts only its "computecellorbackup
  calls" counter, which `regress.py` ignores. drift fixes neither in classic
  output; it simply doesn't have them.
- **regress.py:** all 10 classic inputs are identical to dr2fixed. These
  include Sokwe's rot90 DONTCHECK search (565 or more outcomes), billiard
  rot180, glider, HighLife, vars, and Life written as an INT rule.
- **Speed, one thread, identical work, quiet machine:**
  - stillater c6 h4 w4: 1.5×;
  - billiard rot180: 2.9×;
  - Sokwe rot90: 5.5×.
- **Threads:** 14 threads on stillater c6 h4 w4 took 1.26 s against 11.5 s on
  one thread, with the same result set (3,996 outcomes, 265 distinct).
- **Profile (one thread):** `trycell` > `listneighbors` > `go`/`backup` >
  `nxgen`. Gains already in: per-cell stamp instead of a linear duplicate scan;
  stable counting sort; inline `consistify` fast path; unrolled `nxgen`.
- **validate.py** re-simulates results independently. All results passed for
  Life, two INT rules and a non-isotropic MAP rule. The mirrored MAP rule
  rejects about 30% of them, so the orientation is verified. The exported Life
  MAP string equals Golly's.
- **Checkpoint:** a run interrupted at 0.4 s and resumed gave the same result
  multiset as an uninterrupted run.
- **Eater searches:** `--no-count` over the glider's path makes the search
  explode. Counting everything with `max-changed 10`, `size 5x5` works and
  finds `g-eater` fizzles.

- **Fixed dead border.** dr2 doesn't check the 2-cell dead border for stability.
  In B3/S23-a5 spark searches, 70% of results were signals that ran into the
  border and relied on it, so they couldn't be completed. Modern mode now
  checks the border (`P.checkBorder`); `--classic` and `--unchecked-border`
  keep dr2's behaviour.
- **Partial results.** `drift/tools/finish.py` completes and checks them (pysat), using `driftlib.py`.
  `tests/minimize.py` shrinks stators with the rotor fixed phase by phase:
  about 70% smaller, at most a few seconds each. Earlier bug: SAT variable
  numbers overlapped the constants 0/1; they now start at 2.
- **First search:** 180 real B3/S23-a5 oscillators (p4–p15) from a 22 s spark
  search (`drift/examples/a5-spark-oscillators.cfg`).

- **Survey (2026-10-19).** `drift survey RULE` = `tools/survey.py`:
  - spaceship census from random 16x16 soups (`tools/soups.c`, built on demand into
    `build/soups`, one process per core, ship test in C); ships are named by
    their smallest phase and ranked by count. B3/S135: ship12 (~90 per 17k soups)
    and ship8 (~33);
  - about 12 searches run at once. Each one's thread count is in `NAME.threads`
    (drift `--threads-file`); a finished search's threads go to the rest;
  - `--max-time` + `--checkpoint`: at the limit drift saves the rest of the
    search (verified exact on resume);
  - ship searches scale `max-changed`/`size` from the ship's largest phase.
    The ship-drifter `no-rechange` gap is probed: the smallest value at which
    the bare ship search keeps going, plus 1 (glider: 4);
  - `finish.py --max-minutes`: the most promising groups are checked first.
    `driftlib.complete` now enumerates only unknown cells per window: 12x faster,
    same output.
- **`--symmetric-start` (2026-10-20).** Copies the pattern's `1`/`0` cells into
  their symmetric images before the search (options.cpp `mirrorStart`, same maps
  as `setbkgd`); an image drawn as a conflicting known cell is an error. Output
  is byte-identical to drawing every image by hand (rot180, vert, plus, full,
  diag checked). Not with `symmetry-from` or `day-night`. The starting-position
  picture now shows no-check cells as dr2's `4`/`2`/`3`.
- **Survey levels (2026-10-20).** Three real surveys showed `signals` was the
  `osc` search again (same spark and limits, identical counts) and never kept
  anything, so `osc` now has max-gen 80 and keeps travelling signals itself;
  `osc-big` became `osc-2`. Every search deepens while time is left: a complete
  one starts `NAME-2` (+2 cells, +1x1), and so on to level 6; one that kept
  nothing is rerun in place (+4/+2x2 only if it found nothing at all; a step
  that size took `converter` from 746 skipped results to 731k). `--resume` and
  `--summary` keep the configs in the folder and pick up the levels. SUMMARY.md
  has an "Across all searches" section (oscillators by period, smallest
  catalysts). Ship converters start at pop+6 / +5 (they never got past gen ~37
  at pop+10 / +9). Tried and dropped: clearing the ship's lane beyond a short
  runway (each reaction is otherwise searched at every contact distance); per
  fixed work it found 2x the eaters, per wall time slightly fewer.
- **Finishing speed.** `finish.py` builds the SAT clauses from per-rule
  templates (`driftlib.rule_cnf` / `reduced_clauses`: prime-implicant clauses
  for one cell, worked out once per rule and checked exhaustively against the
  rule table) and runs results in worker processes (`--jobs`; the output is the
  same with any number). Clause building had been about 90% of the time; a
  B3/S135 survey search finishes in 1.5 s instead of 29.5 s.
- **Damaging oscillators.** `finish.py` also lists the oscillator each damaging
  reaction settles into, on its own with the smallest stator found, split into
  separate parts and deduplicated by rotor (any phase, position, orientation).
- **Threads-file details.** Switched-off workers hand their whole pending list back
  to the queue (`Search::pending`, as for checkpoints) and park. Result sets are
  identical under 8→1→3→14 switching (stillater c7 4x4: 5934 osc).

- **Trivial oscillators (2026-10-27).** `finish.py` splits each oscillator's
  rotor into groups more than 2 cells apart (`rotor_groups`). Such groups can't
  interact: no cell has rotor cells of two groups in its 3x3 neighbourhood, so
  each runs at any phase offset. With 2+ groups the result is "trivial": left out
  of clean/damaging/no-spark (`--keep-trivial` keeps it) and each group goes to
  "Oscillators found", minimized on its own stator. A part that shares a stator
  and can't be minimized is listed as the whole oscillator, marked. Conservative:
  groups 2 cells apart that don't actually interact are kept together.
  Checked on copies of two survey result sets (B3/S23 osc, qr4k osc) with casim: every listed
  pattern has its stated period, none is trivial, all old rotors still listed
  (qr4k: 30 trivial damaging oscillators dropped; "Oscillators found" 261 -> 235,
  the difference being old entries that were two rotors on one stator); all 57
  multi-group patterns of the old output survive a one-generation phase shift of
  each group.

- **Spark metrics (2026-10-31).** `driftlib.spark_stats(cycle)` gives open / spark
  depth / touch cells, purely geometric; `finish.py --sort sparky|open`. Sorted
  once before `--limit` on unshrunk cycles, then again on the listed shrunk ones.
  Known answers: `tests/sparktest.py` (includes the q4i depth-2 sparky p4 from
  `findings/`).

- **Rotor database (2026-10-31).** `--rotor-db FILE`: `Reporter::loadRotorDb` loads
  rotor descriptors (`main.desc`, canonical in phase and orientation), and
  matching oscillators return before the per-rotor count. Output filter only:
  search paths are unchanged. finish.py adds a rotor only when it was listed,
  when all parts of its reaction were listed, or as debris; never when cut by
  `--limit`, incomplete or unchecked. So nothing is hidden unseen. Non-isotropic
  rules are refused (the descriptor folds reflections). Measured single-threaded,
  seeding half the rotors: B3/S23 and B3-c/S23 result sets equal the unfiltered
  set minus exactly those rotors (B3-c/S23: 3731 -> 1681 results, 43 rotors, 21 seeded).

- **Spark converters (2026-11-02).** From `SPARK-CONVERTERS-PLAN.md`: P1
  finish.py section (every fizzle, dedupe over 8 orientations, `tests/convtest.py`),
  P2 `output-dist` (Reporter filter), P3 `max-box`, P4 survey job. `max-box`:
  `Search::onBox[n]` is the box after n settings, so backup needs no undo; it's in
  the fingerprint. All settings pass through `proceed`, where it's checked.
  Measured, q4i, one thread, 8 cells 5x5: P2 equals the unfiltered set filtered
  afterwards (96 of 124, none lost or extra). P3: comparing exact results needs
  `--prob 100`, since pruning shifts the random choice order and with it which duplicate
  is kept; then 0 lost by history, and shrunk converters are the same 16 with
  and without. Speed, 10 threads, 10 cells 6x6, clear left only: 8.6 s with
  `max-box = 10x10` (twice), not finished after 60 s without. Not done: P5
  (incomplete fizzles are only counted), P6.

- **Analysis tools from the 2026-11-02..04 web sessions** (`tools/`, prototypes, not
  wired into finish.py; need python-sat, plus numpy for convanalyze/oneshot and
  Pillow for convrender). Session configs and the original handoff are in the local
  results folder (`../results/attempts/session-2026-11-04/`,
  `../results/notes/web-handoff-2026-11-04/`).

  | Tool | Does |
  |---|---|
  | `sparkconv.py CFG...` | fizzles → complete, shrink, re-simulate, require full restore; output distance, clean distance, box; dedupe over 8 orientations. Env MIND (2), MAXBOX (10), SECS, OUT |
  | `sparkout.py RULE RLE SPARK` | output distance beyond the spark's own reach (for sparks that grow) |
  | `convanalyze.py RULE RLE [--chain]` | tags SPLITTER, TURN, FREE-SPARK, THROUGH, LONG; chain test X→Y over 8 orientations, loop detection. Side labels are crude for corner inputs |
  | `convrender.py RULE RLE OUT.png` | reaction strips per converter |
  | `gliderin.py CFG...` | glider fizzles: complete, shrink, from-infinity check (glider 40 periods back must reach the same gen 0), eater/converter/escape |
  | `glfar.py RULE RLE [MIND]` | glider reactions: output distance from the impact, FAR SIDE flag. Supersedes `glout.py` (which penalised far-side outputs on the path line) |
  | `sparkers.py RULE MINDEPTH FINISHED...` | distinct sparky oscillators from finish.py output |
  | `oneshot.py CFG [MIND]` | one-shot reactions from short-max-gen runs: replay on drift's known cells, then local completion, from-infinity, fate. STRICT=1, DIR=1,-1 (use 1,1 for the q4i/a5 configs), LATER=100 |
  | `tlosc.py`, `oscparts.py` | traffic-light detection and part extraction, specific to the q4i plus configs |

  Measured there: oneshot's stage-1 replay equals full completion on 60/60 results
  (10 min → 23 s). Only sparkconv, oneshot, glfar, convanalyze and sparkers were run
  from a clean repo copy; the rest were only syntax-checked there.

- **drift behaviour found in those sessions** (verified in `search.cpp`/`report.cpp`):
  permanent damage that settles into a still life is never reported (STABLE needs
  `semifizzle()`); damage that grows past `max-changed`/`size` is pruned silently.
  A short `max-gen` (~20) turns every still-active branch into a `maxgen` result,
  which is how one-shot reactions are kept. The progress ETA can sit at ~97% for
  10+ minutes in deep subtrees. Search order is deterministic, so a rerun from
  scratch repeats the same first part: use `--checkpoint`/`--resume`. Symmetric
  searches count changed cells of all copies. A `C` spark inside a `clear` region
  survives (regions, then pattern, then clears). There's no "on at gen 0, background
  unknown" state.

- **finish.py completion fills free space with arbitrary still lifes.** In one-shot
  runs the "catalysts" came out as 250-500-cell carpets, and 316 of 388 failed the
  from-infinity check because junk sat on the glider's path. Fizzles are unaffected
  because `shrink` minimises. oneshot.py completes locally instead (new live cells only
  within R = 2, then 4, 6, of drift's known background); finish.py could do the same
  for oscillators and max-gen results.

- **Results of those sessions** (re-simulated; RLEs in the handoff): q4i 25 converters
  within 10×10 incl. splitters and turns, no chains; a5 30 converters, #3 (14 cells,
  free domino output) chains into 6 others; HighLife 9; q4i glider from infinity 41
  distinct (14 far-side); q4i `3o$bo$2bo!` SE-open 11 converters; a5 `3o$bo$2bo!` none
  at 12/7×7 (exhaustive); q4i plus: 61 symmetric catalyst sets, two oscillators
  rebuilding the full traffic light (p9 124 cells, p14 104 cells); B36/S23-e7 glider 17
  restoring reactions. Unchecked whether any are already known.

- **B3/S135 stabilisation (unfinished).** No still life can contain
  `4bo$5bo2$o$o2b2o$o2b2o$b4o$2bo2$2bo$b4o$o2b2o$o2b2o$o2$5bo$4bo!`: core cell (2,3)
  is alive with 6 live neighbours and S135 has no S6 (checked per cell). So it can
  only be an oscillator phase. The user wants drift, not SAT, for this.
  `b3s135-stabilise-UNRUN.cfg` (session folder) dry-runs but was never run; core
  cells can't be stator (no LifeHistory state for that).

## 4. Open ideas

- oneshot.py: intact-catalyst check (at the output gen, still-life cells within 1 of
  it must be intact). Acceptance: `a5-glider-oneshot.cfg` (60 s) rejects #1067 and
  #1073 and keeps #1197; B36/S23-e7 keeps #212-#214.
- Classify "still active after LATER gens" (a5: 508 of 867): explosion vs signal on
  a drift-built wire (`wirecheck.py` logic).
- Port convanalyze into finish.py's converter section (plan P7) and add a one-shot
  section from maxgen results.
- An option to report period-1 permanent-damage outcomes.
- Long runs still to do, with `--checkpoint`: `q4i-glider-fizzle.cfg` (~3 h on 2
  threads), `q4i-spark3o-ring1-10.cfg` (~1 h 11 min), `a5-spark3o-far-*16.cfg`.

- Further per-cell speedups in `trycell` and `listneighbors`.
- Survey ship converters and ship drifters have never kept a result (B3/S135,
  B36/S245, B3/S23-a5): the ship meets unknown cells from gen 0, so the search
  branches on every contact distance and stays below gen ~40. Needs a different
  setup (e.g. a known approach lane plus a short unknown window).

## 5. How to verify a build quickly

```
cd drift && make test      # rule tables, then builds ref/dr2fixed and compares; expect "all identical"
```
