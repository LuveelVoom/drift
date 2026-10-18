#!/usr/bin/env python3
"""Write a spark-converter config: spark at (0,0), still life confined to a box
of H rows (centred on row 0) and W columns starting at column 1, output spark
required just outside the box (above, below or right), 4+ cells from the input.
Usage: make_converter.py H W MAXCHANGED SIZE > file.cfg"""
import sys
H, W, C, SIZE = int(sys.argv[1]), int(sys.argv[2]), int(sys.argv[3]), sys.argv[4]
t, b, r = -(H // 2), H // 2, W   # box rows t..b, cols 1..r
print(f"""# Spark converter, box rows {t}..{b}, cols 1..{r}
rule = B3/S23-a5
max-changed = {C}
size = {SIZE}
clear = r -60 -60 {t - 1} 80
clear = r {b + 1} -60 60 80
clear = r {t} -60 {b} 0
clear = r {t} {r + 1} {b} 80
must-reach = r -60 4 {t - 1} 80
must-reach = r {b + 1} 4 60 80
must-reach = r -60 {r + 1} 60 80
must-reach = r -60 -60 -4 3
must-reach = r 4 -60 60 3
skip = oscillator, stable
per-rotor = 3
pattern:
x = 1, y = 1, rule = LifeHistory
C!""")
