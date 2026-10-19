# Build drift configs: fixed wire, unknown NW end, glider from the NW on a given lane.
import sys
sys.path.insert(0, "/Users/leo/Desktop/Life tools/Vibecoded life tools/dr-attempt/drift/tools")
from driftlib import parse_rle
live = {p for p, s in parse_rle(open("wire10.rle").read()).items() if s == 1}
proj = lambda p: p[0] + p[1]
perp = lambda p: p[0] - p[1]
pmin = min(map(proj, live)); pmax = max(map(proj, live))
CUT = pmin + 24
QC = sorted(map(perp, live))[len(live) // 2]          # cells with proj < CUT become unknown (the end to design)
GL = [[(0, 1), (1, 2), (2, 0), (2, 1), (2, 2)],   # se glider
      [(1, 0), (2, 1), (0, 2), (1, 2), (2, 2)]]   # its mirror image
def make(lane, shift, chir, name):
    st = {}
    R0, R1, C0, C1 = -30, 50, -30, 50
    for r in range(R0, R1):
        for c in range(C0, C1):
            p = (r, c)
            st[p] = 2
            if proj(p) >= CUT:
                st[p] = 1 if p in live else 2
            elif proj(p) >= CUT - 14 and abs(perp(p) - QC) <= 15:
                st[p] = 0       # unknown: the end cap drift designs
    # glider: centre on perp = lane, along the axis well before the cut
    lane += QC
    g0 = CUT - 21 + shift
    r0 = (g0 + lane) // 2 - 1; c0 = (g0 - lane) // 2 - 1
    for r in range(r0 - 2, r0 + 5):
        for c in range(c0 - 2, c0 + 5):
            st[(r, c)] = 2
    for dr, dc in GL[chir]:
        st[(r0 + dr, c0 + dc)] = 3
    rows = []
    for r in range(R0, R1):
        rows.append("".join(".ABC"[st[(r, c)]] for c in range(C0, C1)))
    body = "$".join(rows) + "!"
    # must-reach: a stretch of wire 4 periods past the cut
    mr = sorted([p for p in live if CUT + 20 <= proj(p) <= CUT + 24])
    r, c = mr[0]
    cfg = f"""rule = B36/S23
max-changed = 12
size = 7x7
skip = stable, oscillator, fizzle
max-gen = 60
margin = 2
per-rotor = 3
threads = 4
max-steps = 300000000
must-reach = r {r - R0 - 2} {c - C0 - 2} {r - R0 + 2} {c - C0 + 2}
pattern:
x = {C1 - C0}, y = {R1 - R0}, rule = LifeHistory
{body}
"""
    open(name, "w").write(cfg)
if __name__ == "__main__":
    make(int(sys.argv[1]), int(sys.argv[2]), int(sys.argv[3]), sys.argv[4])
