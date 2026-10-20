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

## 4. Open ideas

- Further per-cell speedups in `trycell` and `listneighbors`.
- `--symmetric-start`: also mirror the gen-0 `1`/`0` cells (asked for on the
  ConwayLife forum).
- Show `--no-check` cells in pictures (they currently look unknown).

## 5. How to verify a build quickly

```
cd drift && make && tests/ruletest
cd ../ref && unzip -o ../dr2.zip knownrotors && cc -O2 -w -std=gnu89 -include stdlib.h \
   -include string.h -include ctype.h -o dr2fixed dr2fixed.c
cd ../drift && python3 tests/regress.py --seconds 5      # expect "all identical"
```
