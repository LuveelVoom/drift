"""convrender.py RULE PATTERN.rle OUT.png [FIRST LAST]: draw each reaction in PATTERN (pieces >= 5 apart; still life + input) as a strip of frames, one row per reaction. Blue = input at gen 0, red = active cells, grey = still life, orange = still-life cells currently dead. Needs Pillow and numpy."""
import sys
import os; sys.path.insert(0, os.environ.get("DRIFT_TOOLS", os.path.dirname(os.path.abspath(__file__))))
import driftlib as L
from PIL import Image, ImageDraw
import convanalyze as C
rule, path, out = sys.argv[1:4]
T = L.rule_for(rule); fast = C.Fast(T)
cells = frozenset(L.parse_rle(open(path).read()))
comps = sorted(C.split(cells), key=lambda c: (min(r for r, _ in c), min(cc for _, cc in c)))
a, b = (int(sys.argv[4]), int(sys.argv[5])) if len(sys.argv) > 5 else (1, len(comps))
convs = [C.Conv(c, fast) for c in comps][a - 1:b]
S = 9; GAP = 2; maxg = max(x.back for x in convs) + 1
rows = []
for X in convs:
    r0, r1, c0, c1 = X.box[0] - 3, X.box[1] + 3, X.box[2] - 3, X.box[3] + 3
    rows.append((X, r0, r1, c0, c1))
W = max((c1 - c0 + 1) for _, _, _, c0, c1 in rows) * S + GAP * S
img = Image.new("RGB", (40 + W * min(maxg, 14), sum((r1 - r0 + 1) * S + 18 for _, r0, r1, _, _ in rows)), "white")
d = ImageDraw.Draw(img); y = 0
for k, (X, r0, r1, c0, c1) in enumerate(rows):
    d.text((2, y + 2), str(a + k), fill="black")
    for t in range(min(len(X.hist), 14)):
        x0 = 40 + t * W
        d.text((x0, y + 2), f"g{t}", fill="gray")
        for r in range(r0, r1 + 1):
            for c in range(c0, c1 + 1):
                p = (r, c); on = p in X.hist[t]; st = p in X.still
                col = None
                if on and st: col = (90, 90, 90)
                elif on and t == 0: col = (30, 90, 230)
                elif on: col = (220, 30, 30)
                elif st: col = (255, 200, 120)
                xx, yy = x0 + (c - c0) * S, y + 14 + (r - r0) * S
                d.rectangle([xx, yy, xx + S - 1, yy + S - 1], fill=col or (245, 245, 245), outline=(225, 225, 225))
    y += (r1 - r0 + 1) * S + 18
img.save(out)
print(img.size)
