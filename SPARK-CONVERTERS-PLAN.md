# drift: finding spark converters — what went wrong and what to change

Goal: drift + finish.py should list **spark converters** directly. A spark
converter is a still life that takes a spark at its outer edge, produces a
spark somewhere else on the object (≥ 2 cells away, preferably ≥ 3), and
restores itself completely. The motivating rule is B3/S23-q4i; nothing below
is rule-specific.

Labels: **measured** (ran it), **verified** (ran or traced the code),
**inferred** (reasoning, not checked).

**Status (2026-11-04):** P1-P4 are implemented (see DEVELOPMENT.md for the
measurements). P5 is partly done (incomplete fizzles are counted, not listed);
P6 isn't started. P7 exists only as the prototype `tools/convanalyze.py`, not
yet in finish.py. Acceptance test 2 passed on a reconstructed t10 config.

## 1. What happened (session of 2026-11-02)

Searches run (all `skip = oscillator, stable`, `per-rotor = 0`, `max-gen = 80`,
B3/S23-q4i, spark drawn as LifeHistory `C` at the pattern's top-left):

| Name | Spark | Region the still life may use | Limits | Time | Fizzles |
|---|---|---|---|---|---|
| c1 | 1 cell | rows −6..6, cols 1..9 (column 0 cleared) | 10 cells, 6×6 | 18 s, 1 thread | 34 |
| c2 | 1 cell | same | 12 cells, 7×7 | 174 s, 1 thread | 34 (same set) |
| A | 1 cell | rows −8..8, cols 0..10 | 12, 7×7 | stopped at 600 s | 28 |
| B | vertical domino | rows −8..8, cols 0..10 | 12, 7×7 | stopped at 600 s | 7 |
| t10 | 1 cell | rows −8..8, cols 0..10, plus must-reach ≥3 away | 10, 6×6 | 131 s, 2 threads | 178 (155 passed must-reach) |

All measured. Across the four runs that were post-processed (c1, A, B, t10):
224 fizzle results, 34 couldn't be completed, 116 distinct after
completion, 99 with an output ≥ 2 away by the loose test below, **25 with a
still-life box ≤ 10×10** (measured with the new `sparkconv.py`).

Only one of them was reported to the user at first. Two the user found by hand
(`b2ob2o$obobo$o4bo$b4o$o$3b2o$2bobo$3bo$4b3o$6bo!`, t10 #102, and
`4b2o$2o2bo$obobo$2bobob2o$b2obob2o$2o2bo$3b2o2$3b2o$3b2o!`, A #2) were in the
results all along.

### Causes, in order of impact

1. **Post-processing too strict (verified).** The first `sparkconv.py`:
   - required the output to be "clean": some outside cell sees it without
     seeing any still-life cell. Real outputs often sit in a notch next to
     catalyst cells, like the user's example;
   - defaulted to `MAXBOX = 9` (reading "<10×10" literally); both of the
     user's examples are 10 tall;
   - defaulted to distance ≥ 3 in the delivered version.

   On t10 alone, 115 of 155 fizzles failed the box ≤ 9 test, and 76 had a
   clean output ≥ 3 away (measured). After that, results at distance 2–3 were
   dismissed by eye as "reaction creeping along the edge".
2. **finish.py has no converter category (verified).** Fizzles go to
   "Catalysts", sorted by reaction length. Nothing there says where the
   reaction's cells end up relative to the spark.
3. **survey.py's `converter` job can't find these (verified from the config
   and its log).** Its `must-reach` regions are all outside the 9×9 box the
   still life lives in, so the output must leave the catalyst's box. Log:
   "nothing of the kinds it keeps" at 10/6×6, 12/7×7, 14/8×8 and 16/9×9. It
   also uses `per-rotor = 3`. Fizzles are grouped by `main.desc` (report.cpp
   `seenRotor`), so different catalysts with the same reaction shape beyond
   the third are dropped (inferred effect; the mechanism is verified).
4. **Search geometry (measured).** Clearing column 0 as well as everything to
   its left (c1) gave 34 fizzles. Clearing only columns ≤ −1 (t10) gave 178 at
   the same limits, because the catalyst may then wrap above and below the
   spark. The user's first example came from t10, the second from both c1 and
   A.
5. **Uncompletable results are dropped silently (measured).** 34 of 224
   fizzle partials failed `Finisher.run` (completion at margin 3, then 6).
   Whether any of them are real wasn't checked.
6. **Fizzles are rare and the search spends almost all its time on
   oscillators (measured).** t10: 9551 oscillators against 178 fizzles.
   `skip = oscillator` only hides the output; those branches are still
   searched.

## 2. Changes, in priority order

Keep exhaustiveness: every change below is either an output filter or a
pruning rule that only removes patterns the user said they don't want. Anything
that could lose wanted results goes behind an option labelled unsafe, off by
default. Compare single-threaded outputs before and after (`make test`, plus
the acceptance tests in §3).

### P1. finish.py: a "Spark converters" section (output only)

For each fizzle that completes and is checked (existing `Finisher.fizzle`,
then `shrink`, then re-simulation):
- input spark = gen-0 cells not in the still life;
- exterior = dead cells 4-connected to the outside of the still life's box
  + 4 (same flood fill as `driftlib.spark_stats`);
- output cells = cells alive at some gen t ≥ 1, not in the still life, in the
  exterior;
- `dist` = max Chebyshev distance from an output cell to the nearest input
  cell, and the first gen it occurs;
- `clean` = the same, counting only output cells that an exterior cell sees in
  its 3×3 without seeing a still-life cell (report it, don't filter on it);
- `back` = first gen from which the still life is unchanged;
- box (width × height) of the still life without the spark.

Options:
- `--min-output-dist N` (default 2);
- `--max-box N` (default: none);
- sort by box, then `dist` (descending), then cells.

List every converter (deduplicated over the 8 orientations of still life +
spark), plus one combined RLE with the converters 10 cells apart. The
prototype is `tools/sparkconv.py` from this session (delivered to the user):
port its `outputs()`, `exterior()`, `canon()` and layout code. Keep the
existing "Catalysts" section unchanged.

### P2. drift: `output-dist = N` result filter (output only, safe)

When a fizzle is detected, drift knows the background around the reaction. Keep
the result only if some cell that was on at a gen ≥ 1, off in the background,
and not a gen-0 spark cell lies at Chebyshev distance ≥ N from every gen-0
spark cell. Implement it next to the `mustReach` check in `Reporter::modern`
(report.cpp), and count rejects like `unreached`. This replaces the
hand-placed must-reach rectangles in the converter configs. Note that drift
can't know "exterior" (the background isn't complete); finish.py does the
exact test.

### P3. drift: `max-box = WxH` pruning for the background (safe for the stated goal)

Back out of a branch as soon as the background cells known to be on don't fit
in a W×H box (in either orientation if `max-box` says so). It differs from
`clear` rectangles because the box can sit anywhere around the spark. It is
exhaustive for still lifes whose live cells fit the box.

Where to hook it: wherever a background cell is set on (the `trycell` /
`consistify` path in search.cpp, as named in DEVELOPMENT.md; not traced). Track the min/max row and column of the
known-on cells incrementally, with undo on backup. **Measure** the speedup on
a config like `conv-dot-14.cfg` with `max-box = 10x10` and the clears
loosened. Confirm with one thread that the result set equals the unpruned run
filtered by box. Inferred benefit: large, because most branches build big
backgrounds that are then rejected.

### P4. survey.py `converter` job

Use the t10 geometry: clear only the side the spark comes from. Use
`output-dist = 3` (P2) instead of the box-escaping must-reach regions, and
`per-rotor = 0`. Run finish with the P1 section. Keep level-deepening as is.

### P5. finish.py: report uncompletable partials

Count them in the summary and list them at the end, with the partial pattern
in LifeHistory and unknown cells shown. First check whether completion at a
larger margin (10, 15) or without the `empty` closure rescues any of the 34
(measure; don't change the default until then).

### P6. Optional, measure first: fizzle-only searches

98% of the time goes to oscillator branches (measured counts, inferred time
share). Ideas to measure, not to merge blindly:
- an **unsafe** option to abandon a branch once it has gone K gens without
  any changed cell outside the still life's current known region, or once its
  changed count has been 0 at the input side for K gens. It can lose results,
  so it's labelled unsafe and off by default;
- profile which outcome kinds the steps go to (add counters per outcome to
  the existing step counts).

### P7. finish.py: describe each converter, don't just measure distance

The second mistake in this session: converters were ranked by one number
(output distance), and the ones that matter for building things weren't
noticed: 1→2 splitters, 90° turners, converters that throw a free spark away
from the object, and converters whose output can trigger another converter.
Port `tools/convanalyze.py` (delivered with this plan) into finish.py's
converter section:
- output **sites**: exterior output cells grouped over all gens (cells ≤ 2
  apart); per site: distance from the input, **depth** (distance from the still
  life; ≥ 2 = a free spark another object can use without touching the
  catalyst), side of the still life's box relative to the input (same / turn /
  opposite), first and last gen;
- **route**: `through` if the site's activity isn't connected, outside the
  still life, to the activity around the input (the signal crossed the
  catalyst), else `along`;
- tags: SPLITTER (two sites ≥ 3 apart), TURN, OPPOSITE-SIDE, FREE-SPARK,
  THROUGH, LONG (≥ 10 gens);
- **chain test** over all converters found: place converter Y (8
  orientations) with its input spark on live output cells of X at that gen,
  require X ∪ Y stable, simulate, keep placements where both still lifes come
  back and Y's output appears. Also keep placements that become periodic with
  both still lifes ≥ 80 % stator (a loop: a new oscillator). In B3/S23-a5,
  a 14-cell converter whose output is a free domino 3 cells out triggered 6
  other converters (measured, re-checked with driftlib.step). In
  B3/S23-q4i, none of the 25 chained: every q4i output with depth 1 sits too
  close to its own catalyst for another catalyst to fit (measured: 16816
  spark matches, 14791 overlapped, 1885 unstable, 140 simulated, 0 worked).
- write a reaction strip image per converter (`tools/render.py`) next to the
  finished file. Looking at the reactions is what found the splitters.

Sort the section by tags first (chainable, then SPLITTER / FREE-SPARK /
OPPOSITE-SIDE / TURN), then by box.

## 3. Acceptance tests

1. **Regression:** `make test` still ends with "all identical". With one
   thread, a converter config without the new options gives byte-identical
   results to the current build.
2. **The user's two catalysts are listed.** Run the t10 config
   (`conv-dot-14.cfg` with `max-changed = 10`, `size = 6x6`; 131 s on 2
   threads) and the A config (12/7×7, the full run takes longer than 10 min).
   The P1 section must list
   `b2ob2o$obobo$o4bo$b4o$o$3b2o$2bobo$3bo$4b3o$6bo!` (dist 3, back by gen 8)
   and `4b2o$2o2bo$obobo$2bobob2o$b2obob2o$2o2bo$3b2o2$3b2o$3b2o!` (dist 3–4,
   back by gen 12–13), up to orientation. A cheaper fixture: draw each
   catalyst as known cells (`A`/`B`) with its spark as `C`, unknown elsewhere,
   10 cells / 6×6. It must come back as a converter.
3. **P2:** the result set with `output-dist = 3` equals the unfiltered set
   filtered afterwards by the same rule (one thread).
4. **P3:** the result set with `max-box = 10x10` equals the unpruned run's
   fizzles whose completed still life fits 10×10. One thread; check that no
   result is lost (one direction) and report the speedup with run-to-run noise.
5. **Orientation:** for P1 dist/box, test an asymmetric case (one of the two
   catalysts and its mirror image) and check the same numbers come out.

## 4. Conventions used in configs here

- Region syntax: `r TOP LEFT BOTTOM RIGHT`, rows and columns relative to the
  pattern's top-left cell (options.cpp `parseRegion`, shifted by
  `o.top`/`o.left`; verified).
- Region flags are applied, then the pattern is read, then `clear`s. A `C`
  spark inside a `clear` survives (measured), since a clear sets the
  background off and `C` is on now / off in the background.
- LifeHistory in patterns: `A` on (known), `B` off (known), `C` spark (on at
  gen 0, off in the background), `.` unknown.
- finish/sparkconv coordinates are drift result coordinates (row, col).
