#!/usr/bin/env python3
"""Turn a drift search into complete, checked patterns.

    python3 tools/finish.py my.cfg

drift runs this automatically after a search (unless --no-finish). It reads
the rule, pattern and regions from the config and the results from
my-results.jsonl, completes every result into a real pattern (cells you drew
as dead and `clear` regions stay empty), simulates it and sorts it:

  clean oscillators     the spark starts an oscillator; nothing of the still
                        life is lost or added for good. With must-reach
                        regions in the config, the oscillator's own cycle has
                        to reach them (a sparky oscillator).
  catalysts             the spark is absorbed and the still life recovers
  spaceship converters  the still life recovers and only spaceships leave
  signals               a disturbance still travelling with a fixed shape
  damaging oscillators  the spark breaks part of the still life to make it
                        (listed last; --clean-only leaves them out)
  debris                oscillates without a stator (not listed)

Each pattern is generation 0 (still life plus spark), shrunk as far as possible
and re-checked, in plain RLE for your rule. Output: my-finished.txt.
"""
import argparse
import collections
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import driftlib as L  # noqa: E402


def config_rule(path):
    for line in open(path):
        m = re.match(r"\s*rule\s*=?\s*(\S+)", line)
        if m:
            return m.group(1)
    return "B3/S23"


class Finisher:
    def __init__(self, cfg, table, seconds):
        self.table, self.seconds = table, seconds
        cells, regions = L.read_config(cfg)
        self.dead = {p for p, k in cells.items() if k == "off"}
        self.clears = [g for k, g in regions if k == "clear"]
        self.reach = [g for k, g in regions if k == "must-reach"]
        self.free_cells, self.free_regions = L.unchecked_cells(cfg)
        self.has_free = bool(self.free_cells or self.free_regions)

    def to_pattern(self, res):
        o = res.get("origin", (0, 0))
        return lambda p: (p[0] + o[0], p[1] + o[1])

    def empty_for(self, res, box=None):
        tp = self.to_pattern(res)

        def empty(p):
            if box and not (box[0] <= p[0] <= box[1] and box[2] <= p[1] <= box[3]):
                return True
            q = tp(p)
            return q in self.dead or any(L.contains(g, q[0], q[1]) for g in self.clears)
        return empty

    def run(self, res, gens, clear_road=False):
        """Complete the background and simulate: (still life, history, empty) or None."""
        cells = L.parse_rle(res["lifehistory"])
        known = {p: s for p, s in cells.items() if s in (1, 2, 3, 4)}
        box = None
        if clear_road:   # nothing may be built outside the searched area, so escapees get a clear road
            rs = [r for r, c in known]
            cs = [c for r, c in known]
            box = (min(rs), max(rs), min(cs), max(cs))
        empty = self.empty_for(res, box)
        tp = self.to_pattern(res)
        free = None
        if self.has_free:
            free = lambda p: tp(p) in self.free_cells or any(L.contains(g, *tp(p)) for g in self.free_regions)
        bk = L.complete(known, self.table, 3, empty, free) or L.complete(known, self.table, 6, empty, free)
        if not bk:
            return None
        still = frozenset(p for p, v in bk.items() if v)
        g = set(still)
        for p, s in known.items():
            if s == 3:
                g.add(p)
            elif s == 4:
                g.discard(p)
        hist = [frozenset(g)]
        for _ in range(gens):
            hist.append(frozenset(L.step(hist[-1], self.table)))
        return still, hist, empty

    # Each classifier returns (category, info) where info has what shrink() needs.
    def oscillator(self, res):
        p, g = res["period"], res["gen"]
        r = self.run(res, g + 2 * p)
        if not r:
            return None
        still, hist, empty = r
        if not all(hist[t] == hist[t - p] for t in range(g + p, g + 2 * p)):
            return None
        if not L.needs_stator(hist[g], p, self.table):
            return "debris", None
        cyc = hist[g:g + p]
        const = {q for q in set().union(*cyc) | still if all((q in ph) == (q in cyc[0]) for ph in cyc)}
        damage = 0 if self.has_free else sum((q in cyc[0]) != (q in still) for q in const)
        info = dict(res=res, hist=hist, still=still, empty=empty, damage=damage, size=len(hist[0]))
        if damage:
            return "damaging", info
        if self.reach:
            tp = self.to_pattern(res)
            rotor = set().union(*cyc) - frozenset.intersection(*cyc)
            if not any(L.contains(rg, *tp(q)) for q in rotor for rg in self.reach):
                return "no-spark", info   # only the start-up reached the must-reach area
        return "clean", info

    def fizzle(self, res):
        g = res["gen"]
        r = self.run(res, g + 2)
        if not r:
            return None
        still, hist, empty = r
        if hist[g] != still or hist[g + 1] != still:
            return None
        return "catalyst", dict(res=res, hist=hist, still=still, empty=empty, size=len(hist[0]))

    def maxgen(self, res):
        r = self.run(res, 320, clear_road=True)
        if r:
            still, hist, empty = r
            end = hist[-1]
            if still <= end and end - still:
                kinds = [L.object_kind(c, self.table) for c in L.components(end - still)]
                if all(k and k.startswith("spaceship") for k in kinds):
                    return "converter", dict(res=res, hist=hist, size=len(hist[0]), what=", ".join(kinds))
        import wirebuild
        m = wirebuild.measure(res, self.table)
        if m:
            return "signal", dict(res=res, size=0, what=f"repeats every {m[0]} gens moving {m[1]}")
        return None

    def shrink(self, kind, info):
        """Smallest gen-0 pattern with the same reaction (checked), else the completed one."""
        hist = info.get("hist")
        if kind not in ("clean", "catalyst", "damaging", "no-spark"):
            return hist[0] if hist else None
        res = info["res"]
        g = res["gen"]
        if kind == "catalyst":
            states, loop = hist[:g + 1], False
        else:
            p = res["period"]
            states, loop = hist[:g + p], g
        spark = set(hist[0]) ^ set(info["still"])
        for margin, seconds in ((4, self.seconds), (7, 3 * self.seconds)):   # retry with more room
            m = L.minimize(states, self.table, loop, margin=margin, seconds=seconds, empty=info["empty"])
            if not m:
                continue
            g0 = frozenset(m[0])
            still = frozenset(set(g0) ^ spark)
            if not self.has_free and frozenset(L.step(still, self.table)) != still:
                continue
            h = [g0]
            for _ in range(len(states) + (res.get("period", 1) * 2)):
                h.append(frozenset(L.step(h[-1], self.table)))
            if kind == "catalyst":
                ok = h[g] == still and h[g + 1] == still
            else:
                p = res["period"]
                ok = h[g + p] == h[g] and h[g + 2 * p] == h[g] and not any(h[g + d] == h[g] for d in range(1, p))
            if ok:
                return g0
        info["unshrunk"] = True
        return hist[0]


SECTIONS = [
    ("clean", "Clean oscillators (the spark starts them; the still life loses nothing)"),
    ("catalyst", "Catalysts (the spark is absorbed; the still life recovers exactly)"),
    ("converter", "Spaceship converters (the still life recovers; spaceships leave)"),
    ("signal", "Signals (still travelling with a fixed shape)"),
    ("damaging", "Damaging oscillators (the spark breaks part of the still life)"),
    ("no-spark", "Oscillators that don't reach the must-reach area in their own cycle"),
]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("config")
    ap.add_argument("--jsonl", help="results file (default: <config>-results.jsonl)")
    ap.add_argument("--out", help="output file (default: <config>-finished.txt)")
    ap.add_argument("--all", action="store_true",
                    help="also list oscillators without a spark in their cycle, and long fizzles")
    ap.add_argument("--clean-only", action="store_true", help="don't list damaging oscillators")
    ap.add_argument("--limit", type=int, default=30, help="patterns listed per section (default 30)")
    ap.add_argument("--max-cells", type=int, default=0, help="leave out patterns bigger than this")
    ap.add_argument("--seconds", type=float, default=5, help="time spent shrinking each listed pattern")
    a = ap.parse_args()
    base = a.config[:-4] if a.config.endswith(".cfg") else a.config
    jsonl = a.jsonl or base + "-results.jsonl"
    out = a.out or base + "-finished.txt"
    if not os.path.exists(jsonl):
        sys.exit(f"finish.py: no results file {jsonl}. Run drift on {a.config} first, or pass --jsonl.")
    L.need_pysat()
    rule = config_rule(a.config)
    fin = Finisher(a.config, L.rule_for(rule), a.seconds)

    # 1. group the results (one entry per distinct rotor / reaction / signal)
    groups = collections.defaultdict(list)
    for line in open(jsonl):
        res = json.loads(line)
        k = res["kind"]
        if k == "oscillator":
            groups[(k, res["rotor"])].append(res)
        elif k == "fizzle":
            h, w = map(int, res["history"].split()[2].split("x"))
            if max(h, w) <= 8 or a.all:   # long thin fizzles are signals running along a wire
                groups[(k, res["history"])].append(res)
        elif k == "maxgen":
            groups[(k, tuple(res["change_counts"][-12:]))].append(res)
    print(f"finishing {sum(map(len, groups.values()))} results ({len(groups)} distinct)...", flush=True)

    # 2. classify (quick), keeping the best candidate of each group
    found = collections.defaultdict(list)
    counts = collections.Counter()
    rank = {"clean": 0, "catalyst": 0, "converter": 0, "signal": 0, "no-spark": 1, "damaging": 2, "debris": 3}
    for (kind, _), cands in groups.items():
        cands.sort(key=lambda r: r["gen"])
        best = None
        for res in cands[:6]:
            try:
                r = getattr(fin, kind)(res)
            except Exception as e:   # one bad result shouldn't stop the rest
                print(f"  (result #{res['n']} skipped: {e})", file=sys.stderr)
                r = None
            if r and (best is None or rank[r[0]] < rank[best[0]] or
                      (rank[r[0]] == rank[best[0]] and r[1] and best[1] and r[1]["size"] < best[1]["size"])):
                best = r
            if best and rank[best[0]] == 0:
                break
        if not best:
            counts["incomplete"] += 1
            continue
        counts[best[0]] += 1
        if best[0] != "debris":
            found[best[0]].append(best[1])

    # 3. shrink and write the ones that are listed
    lines = [f"# drift results for {a.config}, finished by finish.py (rule {rule}).",
             "# Each pattern is gen 0 (still life + spark); paste into Golly with this rule.", None, ""]
    summary = []
    for key, title in SECTIONS:
        items = found.get(key, [])
        if (key == "no-spark" and not a.all) or (key == "damaging" and a.clean_only):
            continue
        if key in ("clean", "damaging", "no-spark"):
            items.sort(key=lambda i: (-i["res"]["period"], i.get("damage", 0), i["size"]))
        elif key == "catalyst":
            items.sort(key=lambda i: (-i["res"]["gen"], i["size"]))
        written = []
        for info in items:
            if len(written) >= a.limit:
                break
            g0 = fin.shrink(key, info)
            if a.max_cells and g0 is not None and len(g0) > a.max_cells:
                continue
            res = info["res"]
            if key in ("clean", "damaging", "no-spark"):
                p = res["period"]
                head = f"p{p} oscillator, {len(g0)} cells, oscillating from gen {res['gen'] - p}"
                head += ", billiard table" if not L.exposed(g0, p, fin.table) and key == "clean" else ""
                if info.get("damage"):
                    head += f", {info['damage']} still-life cells changed for good"
            elif key == "catalyst":
                head = f"catalyst, {len(g0)} cells, reaction lasts {res['gen']} gens"
            elif key == "converter":
                head = f"converter, {len(g0)} cells: {info['what']}"
            else:
                head = f"signal: {info['what']} (result #{res['n']} in {os.path.basename(jsonl)})"
            if info.get("unshrunk"):
                head += " (couldn't be shrunk)"
            written.append(f"#C {head}\n" + (L.to_rle(g0, rule).rstrip() if g0 is not None else ""))
        if not items:
            continue
        summary.append(f"{len(items)} {title.split(' (')[0].lower()}")
        lines.append(f"## {title}: {len(items)}" + (f" (showing {len(written)})" if len(written) < len(items) else ""))
        lines.append("")
        lines += [w + "\n" for w in written]
    lines[2] = "# Found: " + (", ".join(summary) if summary else "nothing usable")
    open(out, "w").write("\n".join(lines) + "\n")

    names = {"clean": "clean oscillators", "catalyst": "catalysts", "converter": "spaceship converters",
             "signal": "signals", "damaging": "damaging oscillators", "no-spark": "oscillators without a spark in their cycle",
             "debris": "debris (dropped)", "incomplete": "couldn't be completed"}
    for k, name in names.items():
        if counts[k]:
            print(f"  {counts[k]:4d}  {name}")
    print(f"Saved to {out}")
    if counts["no-spark"] and not a.all:
        print("  (oscillators without a spark in their cycle aren't listed; add --all)")
    if not (counts["clean"] + counts["catalyst"] + counts["converter"] + counts["signal"] + counts["damaging"]):
        skip = " ".join(l.split("=", 1)[1] for l in open(a.config) if re.match(r"\s*skip\s*=", l))
        print("Nothing usable was found. Things to try:")
        if "fizzle" in skip:
            print("  - catalysts were skipped: remove 'fizzle' from skip")
        print("  - looser limits (max-changed, size), or put the spark next to unknown cells")


if __name__ == "__main__":
    main()
