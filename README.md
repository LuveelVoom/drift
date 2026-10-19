# drift

A port of **dr2**, Dean Hickerson's drifter search for the Game of Life (1997,
extended in 2014), extended to isotropic non-totalistic (INT/Hensel) rules,
other Life-like rules and Golly `MAP` rules. dr2 is Dean Hickerson's work;
this repo holds LuveelVoom's port.

Main additions:
- named options and config files instead of dr2's numbered `v` variables;
- patterns drawn in Golly (LifeHistory RLE), with results as RLE you can paste back;
- multithreading, a progress line, and checkpoint/resume;
- a single-thread speedup of 1.5–5.5× over dr2.

With one thread and the same seed it reports exactly the same results as dr2,
in the same order. Full documentation: [drift/README.md](drift/README.md).

| Path | What it is |
|---|---|
| `drift/` | Source. `cd drift && make`, then `./drift examples/stillater.cfg` |
| `drift/README.md`, `drift/docs/GUIDE.md` | Quick start; how to build searches and read results |
| `drift/examples/` | Ready-to-run config files |
| `drift/tools/` | `finish.py` (complete and check results; drift runs it), picture, wire and checking tools |
| `drift/tests/` | Rule-table tests, comparison with dr2, benchmark |
| `dr2.c`, `dr2.zip` | The original program, its documentation and the `knownrotors` list |
| `ref/dr2fixed.c` | `dr2.c` with its 64-bit `v`-command bug fixed; the reference for the tests |
| `findings/` | Verified patterns found so far (B3/S23-a5, B3/S23-q4i, HighLife), with notes |
| `attempts/` | The configs and scripts behind them |
| `HANDOFF.md` | Notes for continuing the work |

## Quick check

```
cd drift && make
./drift examples/beehive-spark.cfg      # ~1 s; writes examples/beehive-spark-finished.txt
make test                               # needs ref/dr2fixed, see drift/README.md#tests
```
