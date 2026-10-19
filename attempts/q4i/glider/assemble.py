import sys, json
sys.path.insert(0, "/Users/leo/Desktop/Life tools/Vibecoded life tools/dr-attempt/drift/tools")
from driftlib import parse_rle, to_rle
F = "/Users/leo/Desktop/Life tools/Vibecoded life tools/dr-attempt/findings/B3-S23-q4i/best-glider-drifter"
dr = json.load(open("drifter-quick.json"))
ea = json.load(open("eaters-quick.json"))
star = [(67, 0, open("drifter-67.rle").read().split("\n", 1)[1],
         "glider -> down-left drifter -> 2c/3 signal (+2,+2)/3 -> 90-degree turn -> 2c/3 signal (-2,+2)/3 -> eaten")]
sections = [
    ("Highlight: glider -> drifter -> 2c/3 signal -> 90-degree turn -> 2c/3 signal -> eaten (67 gens)", star),
    ("Glider -> drifter reactions, longest first (the glider is absorbed, travels through the still life, and the still life is restored)",
     [d for d in dr if d[0] != 67 or d[3] != star[0][3]]),
    ("Glider eaters (the glider is absorbed; the still life recovers)", ea),
]
txt = ["# Best B3/S23-q4i glider results from drift, 2026-10-18.",
       "# Each pattern is a separate RLE: copy one (from its x = line to the !) and paste into Golly.",
       "# Gen 0 is shown: still life + glider. Every pattern was re-simulated: the still life is restored exactly.",
       "# 'signal' notes list stretches where the disturbance repeats with a fixed shift (3+ times).", ""]
for title, es in sections:
    txt += [f"## {title}: {len(es)}", ""]
    for G, n, rle, sig in es:
        txt += [f"#C {G} gens, still life {n} cells" + (f"; signals: {sig}" if sig else ""), rle.strip(), ""]
open(F + ".txt", "w").write("\n".join(txt))
allc, y = set(), 0
for title, es in sections:
    x, rowh = 0, 0
    for k, (G, n, rle, sig) in enumerate(es):
        cells = {p for p, s in parse_rle(rle).items() if s == 1}
        r0 = min(r for r, c in cells); c0 = min(c for r, c in cells)
        allc |= {(r - r0 + y, c - c0 + x) for r, c in cells}
        x += max(c for r, c in cells) - c0 + 21
        rowh = max(rowh, max(r for r, c in cells) - r0 + 1)
        if x > 800:
            y += rowh + 30; x, rowh = 0, 0
    y += rowh + 60
open(F + ".rle", "w").write("#C Best q4i glider results; rows: highlight | drifters (longest first) | glider eaters\n" + to_rle(allc, "B3/S23-q4i"))
print("wrote", F, {t[:20]: len(e) for t, e in sections})
