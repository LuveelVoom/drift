import sys
sys.path.insert(0, "/Users/leo/Desktop/Life tools/Vibecoded life tools/dr-attempt/drift/tools")
from driftlib import parse_rle, rule_for, step
t = rule_for("B3/S23-q4i")
g0 = {p for p, s in parse_rle(open(sys.argv[1]).read()).items() if s == 1}
hist = [g0]
for _ in range(80): hist.append(step(hist[-1], t))
bg = hist[-1]
ch = [frozenset((p, p in hist[g]) for p in hist[g] ^ bg) for g in range(70)]
def norm(s):
    if not s: return None, None
    r0 = min(p[0][0] for p in s); c0 = min(p[0][1] for p in s)
    return frozenset(((r - r0, c - c0), v) for (r, c), v in s), (r0, c0)
for g in range(68):
    s = ch[g]
    if not s: print(g, "-"); continue
    rs = [p[0][0] for p in s]; cs = [p[0][1] for p in s]
    a, o = norm(s)
    rep = ""
    for P in range(1, 13):
        if g + P < 70 and ch[g + P]:
            b, o2 = norm(ch[g + P])
            if a == b:
                rep = f"same shape at +{P} gens moved {(o2[0]-o[0], o2[1]-o[1])}"; break
    print(f"{g:2d} n={len(s):2d} rows {min(rs)}-{max(rs)} cols {min(cs)}-{max(cs)}  {rep}")
