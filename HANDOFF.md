# drift — handoff for a new chat

Read this first, then continue. Everything needed to keep working is in this repo.

## 1. What this project is

`drift` is a C++17 port of Dean Hickerson's **dr2.c**, a drifter search for
Life-like cellular automata. It tracks a stable background and a current
generation that differs from it in a few cells, chooses unknown background
cells as needed, and backtracks when the changed region gets too big.

The user's goals were:
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
| `drift/tests/` | `ruletest.cpp`, `regress.py` (vs dr2), `bench.py`, `validate.py` |
| `dr2.c`, `dr2.zip` | The original; `dr2.zip` has `dr.documentation.txt` and `knownrotors` |
| `ref/dr2fixed.c` | The oracle: dr2.c with `"%d %d"` → `"%d %ld"` in the `v` command |

## 2. User preferences (keep following these)

- Be concise; short answers.
- Short tests and fast iteration. No long serial benchmark loops; wrap up wins.
- The user sometimes runs their own long searches. Ask before benchmarking,
  because machine load makes timings noisy.
- Stop and report when something gets expensive.

## 3. How it works (decisions worth keeping)

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

## 4. Known facts and measurements

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

## 5. Open ideas

- Further per-cell speedups in `trycell` and `listneighbors`.
- `--symmetric-start`: also mirror the gen-0 `1`/`0` cells (asked for on the
  ConwayLife forum).
- Show `--no-check` cells in pictures (they currently look unknown).

## 6. How to verify a build quickly

```
cd drift && make && tests/ruletest
cd ../ref && unzip -o ../dr2.zip knownrotors && cc -O2 -w -std=gnu89 -include stdlib.h \
   -include string.h -include ctype.h -o dr2fixed dr2fixed.c
cd ../drift && python3 tests/regress.py --seconds 5      # expect "all identical"
```
