import sys, json
sys.path.insert(0, "/Users/leo/Desktop/Life tools/Vibecoded life tools/dr-attempt/drift/tools")
from driftlib import parse_rle, rule_for, step, complete, to_rle
t = rule_for("B3/S23-q4i")
def build(res):
    known = {p: s for p, s in parse_rle(res["lifehistory"]).items() if s in (1, 2, 3, 4)}
    sp = [p for p, s in known.items() if s == 3]
    r0 = min(p[0] for p in sp) - 1; c0 = min(p[1] for p in sp) - 1
    empty = lambda p: (p[0] <= r0 + 4 and p[1] < c0) or (p[1] <= c0 + 4 and p[0] < r0)
    bk = complete(known, t, 4, empty=empty, fewest=3)
    if not bk: return None
    bg = {p for p, v in bk.items() if v}
    g0 = (bg | set(sp)) - {p for p, s in known.items() if s == 4}
    h = g0
    for gen in range(1, 300):
        h = step(h, t)
        if h == bg: return g0, bg, gen
    return None
def signals(g0, bg, G):
    hist = [g0]
    for _ in range(G + 2): hist.append(step(hist[-1], t))
    def norm(g):
        s = hist[g] ^ bg
        if not s: return None, None
        r0 = min(r for r, c in s); c0 = min(c for r, c in s)
        return frozenset(((r - r0, c - c0), (r, c) in hist[g]) for r, c in s), (r0, c0)
    segs = []
    for g in range(G):
        a, o = norm(g)
        for P in range(1, 9):
            if g + 2 * P <= G:
                b, o2 = norm(g + P); c, o3 = norm(g + 2 * P)
                if a and a == b == c and o2 != o and (o3[0]-o2[0], o3[1]-o2[1]) == (o2[0]-o[0], o2[1]-o[1]):
                    d = (o2[0]-o[0], o2[1]-o[1])
                    if segs and segs[-1][1] == (P, d) and segs[-1][0][1] >= g - 1:
                        segs[-1][0][1] = g
                    else:
                        segs.append([[g, g], (P, d)])
                    break
    return "; ".join(f"gens {a}-{b + 2*P}: period {P} moving {d}" for (a, b), (P, d) in segs)
which = sys.argv[1]
rs = [r for r in map(json.loads, open(f"{which}-results.jsonl")) if r["kind"] == "fizzle"]
seen, out = set(), []
for res in sorted(rs, key=lambda r: -r["gen"]):
    if res["history"] in seen: continue
    seen.add(res["history"])
    if which == "drifter" and len(out) >= 40: break
    b = build(res)
    if not b: continue
    g0, bg, G = b
    out.append((G, len(bg), to_rle(g0, "B3/S23-q4i"), signals(g0, bg, G)))
    print(G, len(bg), out[-1][3], flush=True)
json.dump(out, open(f"{which}-quick.json", "w"))
