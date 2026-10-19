import sys
sys.path.insert(0, "/Users/leo/Desktop/Life tools/Vibecoded life tools/dr-attempt/drift/tools")
from driftlib import parse_rle, rule_for, step, minimize, to_rle
t = rule_for("B3/S23-q4i")
g0 = {p for p, s in parse_rle(open("drifter-67.rle").read()).items() if s == 1}
hist = [g0]
for _ in range(80): hist.append(step(hist[-1], t))
bg = hist[-1]
C = {g: {p: int(p in hist[g]) for p in hist[g] ^ bg} for g in range(70)}
A, B = 31, 61                      # clean in-leg starts at 31, out-leg clean through 63
mv = lambda d, v: {(r + v[0], c + v[1]): x for (r, c), x in d.items()}
def ext(g):
    if g < A:
        k, ph = divmod(g - A, 3); return mv(C[A + ph], (2 * k, 2 * k))
    if g > B:
        k, ph = divmod(g - B, 3); return mv(C[B + ph], (-2 * k, 2 * k))
    return C[g]
R = lambda d: {(-c, r): x for (r, c), x in d.items()}
def norm(d):
    r0 = min(r for r, c in d); c0 = min(c for r, c in d)
    return frozenset(((r - r0, c - c0), x) for (r, c), x in d.items()), (r0, c0)
GS = int(sys.argv[1]) if len(sys.argv) > 1 else 34
inp = R(ext(GS))
for Q in range(B - GS, B - GS + 40):
    a, oa = norm(inp); b, ob = norm(ext(GS + Q))
    if a == b:
        v = (ob[0] - oa[0], ob[1] - oa[1]); break
else:
    print("rotated input signal never matches the output signal"); sys.exit(1)
print("quarter time Q =", Q, "-> loop period", 4 * Q, "shift", v)
w, rot = (0, 0), lambda p: (-p[1], p[0])
D, bgval, bad = [], {}, 0
for k in range(4):
    for tt in range(Q):
        d = ext(GS + tt)
        for _ in range(k): d = R(d)
        d = mv(d, w)
        D.append(d)
        for p, x in d.items():
            if bgval.setdefault(p, 1 - x) != 1 - x: bad += 1
    vk = v
    for _ in range(k): vk = rot(vk)
    w = (w[0] + vk[0], w[1] + vk[1])
print("closes:", w == (0, 0), "conflicting cells:", bad)
if bad: sys.exit(1)
states = []
for d in D:
    states.append({p for p in bgval if d.get(p, bgval[p])})
res = minimize(states, t, True, margin=5, seconds=float(sys.argv[2]) if len(sys.argv) > 2 else 120)
if not res:
    print("no stator fits"); sys.exit(1)
pat, pop = res
h = set(pat)
for _ in range(4 * Q): h = step(h, t)
print("period check:", h == pat, "population", pop)
open("loop.rle", "w").write(f"#C q4i 2c/3 signal loop, p{4*Q}\n" + to_rle(pat, "B3/S23-q4i"))
print(open("loop.rle").read())
