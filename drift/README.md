# drift

drift searches Life-like cellular automata for things a small disturbance can
do to a still life:
- start an **oscillator**, or a **sparky** one;
- be absorbed by a **catalyst**;
- be **converted** into a spaceship;
- travel as a **signal** along a wire.

It works in any B/S, INT (`B2-a3/S12`) or Golly `MAP` rule, uses every core,
and can save and resume long runs. It is a port of Dean Hickerson's **dr2.c**.

## Install

    make                     # builds ./drift
    pip install python-sat   # needed to finish results into complete patterns

## Quick start

    ./drift examples/beehive-spark.cfg

The config describes the search: a beehive with one spark cell beside it, in
Life. drift searches, then finishes the results automatically, writing two
files next to the config:

| file | what it is |
|---|---|
| `examples/beehive-spark-finished.txt` | **complete, checked patterns**, best first, ready to paste into Golly |
| `examples/beehive-spark-results.txt` (and `.jsonl`) | drift's raw results: partial patterns, as found |

To set up your own search, read **[docs/GUIDE.md](docs/GUIDE.md)**. It covers
drawing the starting pattern in Golly, the options, and recipes for each kind
of search. `./drift --help` lists every option, and `./drift my.cfg --dry-run`
shows what a config sets up without searching.

## What's where

| path | |
|---|---|
| `examples/` | ready-to-run configs |
| `docs/GUIDE.md` | how to build searches and read the results |
| `docs/DR2.md` | for dr2 users: old input files, option mapping, differences |
| `tools/finish.py` | completes, checks, sorts and shrinks results (drift runs it for you) |
| `tools/render.py` | draws a config's starting position and regions as an SVG picture |
| `tools/wirecheck.py`, `tools/wirebuild.py` | find wires among travelling signals, and build exactly periodic ones with stable ends |
| `tools/validate.py` | re-simulates results independently |
| `results/` | example searches (`run-all.sh` runs them) |
| `tests/` | `make test`: rule tables, and a comparison with dr2.c |

## How good is it

- **Matches dr2:** with one thread and the same seed it reports exactly dr2's
  results in the same order (`tests/regress.py`).
- **Faster:** 1.5–5.5× faster than dr2 on one core, and roughly 9× more on 14
  cores.
- **Checked results:** `finish.py` keeps only patterns that it has completed and
  re-simulated.

Verified patterns found so far are in [`../findings/`](../findings/README.md).
