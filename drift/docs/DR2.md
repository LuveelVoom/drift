# drift for dr2 users

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

## Differences from dr2

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
