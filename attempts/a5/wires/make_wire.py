#!/usr/bin/env python3
"""Write a wire-search config: a single spark at (0,0) in an unknown background;
the disturbance must keep moving in direction DIR at >= SPEED and still be going
at max gen (dr's way of finding signals such as the 2c/3 wire).
DIR: right/left/up/down, a diagonal (se, ne, ...), or an oblique vector R,C
(SPEED c/N = R rows down and C columns right every N gens).
Usage: make_wire.py DIR SPEED MAXCHANGED SIZE > file.cfg"""
import sys
from fractions import Fraction
d, speed, C, size = sys.argv[1], sys.argv[2], int(sys.argv[3]), sys.argv[4]
num, den = speed.split("c")
v = Fraction(int(num or 1), int(den.lstrip("/") or 1))
step = max(abs(int(x)) for x in d.split(",")) if "," in d else 1
maxgen = int(30 / (v * step))   # long enough to travel ~30 cells
print(f"""# Wire search: signal moving {d} at >= {speed}
rule = B3/S23-a5
max-changed = {C}
size = {size}
margin = 40
max-gen = {maxgen}
push = {d} {speed} 3
skip = oscillator, fizzle, stable
no-pics
pattern:
x = 1, y = 1, rule = LifeHistory
C!""")
