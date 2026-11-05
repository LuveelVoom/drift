#!/usr/bin/env python3
"""Glider reactions whose output appears far from where the glider hit.

usage: python3 tools/glfar.py RULE PATTERN.rle [MIND]      (put in drift/tools/, needs numpy)
  PATTERN: reactions (still life + one glider), pieces >= 7 apart, e.g. gliderin.py's RLE.
  The glider is found as the gen-0 cells that aren't in the final still life.

For each reaction:
  contact  first gen where the pattern differs from (still life + free glider)
  entry    every cell that differs from (still life + free glider) in gens contact..contact+2,
           plus the free glider's cells up to contact
  outputs  cells alive outside the still life, in the dead region 4-connected to the outside,
           after contact, at Chebyshev distance >= MIND (default 4) from the entry region
  far side an output beyond the still life's centre along the glider's direction
Prints the farthest output (distance, depth = distance from the still life, gen) per reaction
and writes the reactions with outputs to glfar.rle (header without spaces).
"""
import os
import sys

TOOLS = os.environ.get("DRIFT_TOOLS", os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, TOOLS)
import driftlib as L  # noqa: E402
import convanalyze as C  # noqa: E402

rule, path = sys.argv[1], sys.argv[2]
MIND = int(sys.argv[3]) if len(sys.argv) > 3 else 4
T = L.rule_for(rule)
f = C.Fast(T)


def free_glider(g, n):
    out = [frozenset(g)]
    for _ in range(n):
        out.append(frozenset(L.step(out[-1], T)))
    return out


def analyse(comp):
    X = C.Conv(comp, f, gens=120)
    gl = X.inp
    fg = free_glider(gl, len(X.hist) + 4)
    d = (fg[4] and (min(r for r, c in fg[4]) - min(r for r, c in gl), min(c for r, c in fg[4]) - min(c for r, c in gl)))
    contact = next(t for t in range(len(X.hist)) if X.hist[t] != (X.still | fg[t]))
    entry = set()
    for t in range(contact + 1):
        entry |= fg[t]
    for t in range(contact, min(contact + 3, len(X.hist))):
        entry |= X.hist[t] ^ (X.still | fg[t])
    rs = [r for r, c in X.still]
    cs = [c for r, c in X.still]
    centre = (sum(rs) / len(rs)) * d[0] + (sum(cs) / len(cs)) * d[1]
    best = None
    for t in range(contact + 1, len(X.hist)):
        for p in X.hist[t] - X.still:
            if p not in X.ext:
                continue
            dist = C.cheb(p, entry)
            if dist >= MIND and (best is None or dist > best[0]):
                best = (dist, t, p, C.cheb(p, X.still), p[0] * d[0] + p[1] * d[1] > centre)
    return X, contact, best


def main():
    cells = frozenset(L.parse_rle(open(path).read()))
    comps = sorted(C.split(cells, 7), key=lambda c: (min(r for r, _ in c), min(cc for _, cc in c)))
    keep = []
    for i, comp in enumerate(comps):
        try:
            X, contact, best = analyse(comp)
        except (ValueError, StopIteration) as e:
            print(f"{i + 1}. skipped: {e!r}")
            continue
        rs = [r for r, c in X.still]
        cs = [c for r, c in X.still]
        box = f"{max(cs) - min(cs) + 1}x{max(rs) - min(rs) + 1}"
        if best:
            dist, t, p, depth, far = best
            print(f"{i + 1}. {len(X.still)} cells {box}, contact gen {contact}, back by gen {X.back}: output "
                  f"{dist} from the entry at gen {t}, depth {depth}{', FAR SIDE' if far else ''}")
            keep.append(comp)
        else:
            print(f"{i + 1}. {len(X.still)} cells {box}, back by gen {X.back}: no output >= {MIND} from the entry")
    if keep:
        allc, x = set(), 0
        for comp in keep:
            r0 = min(r for r, c in comp)
            c0 = min(c for r, c in comp)
            allc |= {(r - r0, c - c0 + x) for r, c in comp}
            x += max(c for r, c in comp) - c0 + 13
        lines = L.to_rle(allc, rule).split("\n")
        with open("glfar.rle", "w") as fo:
            fo.write(lines[0].replace(" ", "") + "\n" + "".join(lines[1:]) + "\n")
        print(f"{len(keep)} with outputs -> glfar.rle")


if __name__ == "__main__":
    main()
