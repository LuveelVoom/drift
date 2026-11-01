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
  escapes               (--escape) the still life is back while something is
                        outside in no-count space, e.g. a glider turned into a pi
  signals               a disturbance still travelling with a fixed shape
  oscillators found     the oscillators that damaging reactions end in, each
  in damaging reactions on its own with the smallest stator found: real
                        oscillators even though the spark doesn't start them
                        cleanly. Separate oscillators are split apart, rotors
                        already listed are left out, and rotors not in the
                        known list (B3/S23) come first. The parts of trivial
                        oscillators (below) are listed here too.
  damaging oscillators  the spark breaks part of the still life to make it
                        (listed last; --clean-only leaves out these and the
                        section above)
  debris                oscillates without a stator (not listed)
  trivial               the rotor falls apart into parts more than 2 cells
                        apart, which can't affect each other even through a
                        shared stator (e.g. a p2 and a p3 rotor making a "p6").
                        Not listed as a whole (--keep-trivial lists them);
                        each part goes to "oscillators found" instead.

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


class Finisher:
    def __init__(self, cfg, table, seconds):
        self.table, self.seconds = table, seconds
        cells, regions = L.read_config(cfg)
        self.dead = {p for p, k in cells.items() if k == "off"}
        self.clears = [g for k, g in regions if k == "clear"]
        self.regions = regions
        self.reach = [g for k, g in regions if k == "must-reach"]
        self.free_cells, self.free_regions = L.unchecked_cells(cfg)
        self.has_free = bool(self.free_cells or any(k == "no-check" for k, g in self.free_regions))

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
            free = lambda p: tp(p) in self.free_cells or L.flagged(self.free_regions, "no-check", *tp(p))
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
            # keep the completed pattern so the signal is written out (it used to be left empty)
            r = r or self.run(res, 1)
            hist = r[1] if r else None
            return "signal", dict(res=res, hist=hist, size=len(hist[0]) if hist else 0,
                                  what=f"repeats every {m[0]} gens moving {m[1]}")
        return None

    def escape(self, res):
        g = res["gen"]
        r = self.run(res, g)
        if not r:
            return None
        still, hist, empty = r
        tp = self.to_pattern(res)
        out = hist[g] ^ still
        if not out or not all(L.flagged(self.regions, "no-count", *tp(q)) for q in out):
            return None
        kinds = []
        for comp in L.components(out):
            k = L.object_kind(frozenset(comp & hist[g]), self.table)
            kinds.append(k or f"{len(comp)}-cell active region")
        return "escape", dict(res=res, hist=hist, size=len(hist[0]), what=", ".join(sorted(kinds)))

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

    def extract(self, info):
        """One phase of an oscillator part with the smallest stator found (checked),
        else the part as it was in the reaction."""
        cyc, p = info["cyc"], info["period"]
        for margin, seconds in ((4, self.seconds), (7, 3 * self.seconds)):
            m = L.minimize([set(s) for s in cyc], self.table, True, margin=margin, seconds=seconds)
            if not m:
                continue
            h = [frozenset(m[0])]
            for _ in range(2 * p):
                h.append(frozenset(L.step(h[-1], self.table)))
            if h[p] == h[0] and h[2 * p] == h[0] and not any(h[d] == h[0] for d in range(1, p)):
                return h[0]
        info["unshrunk"] = True
        if not info.get("alone", True):   # cyc[0] isn't a working pattern: give the whole oscillator
            info["unseparated"] = True
            return info["full"]
        return cyc[0]


TRANSFORMS = [lambda r, c: (r, c), lambda r, c: (r, -c), lambda r, c: (-r, c), lambda r, c: (-r, -c),
              lambda r, c: (c, r), lambda r, c: (c, -r), lambda r, c: (-c, r), lambda r, c: (-c, -r)]


def rotor_groups(cyc):
    """The rotor cells of one cycle, split into groups more than 2 cells apart. No cell
    sees rotor cells of two groups in its 3x3 neighbourhood, so the groups can't affect
    each other, even through a stator they share: each runs at any phase offset."""
    return L.components(set().union(*cyc) - frozenset.intersection(*cyc))


def oscillator_parts(cyc, table):
    """Split one cycle of a periodic pattern into its independent oscillators (one per
    rotor group). Returns (phases, period, rotor key, alone) for each part that needs a
    stator; the key is the same for the same rotor in any phase, position or orientation.
    alone: the phases are a working pattern by themselves (the part's cells are more than
    2 cells from every other rotor). Otherwise they hold the part's rotor and the whole
    stator around it, a valid input for L.minimize but not an oscillator as they stand."""
    out = []
    allc = set().union(*cyc)
    allrotor = allc - frozenset.intersection(*cyc)
    comps = L.components(allc)
    for rotor in rotor_groups(cyc):
        mine = set().union(*(c for c in comps if c & rotor))   # the cells joined to this rotor
        others = (allrotor - rotor) & mine
        alone = not others
        ph = [frozenset((s & mine) - others) for s in cyc]
        per = next(d for d in range(1, len(ph) + 1) if len(ph) % d == 0 and ph[d % len(ph)] == ph[0])
        ph = ph[:per]
        h = [ph[0] & rotor]   # as L.needs_stator: the rotor on its own, without any stator
        for _ in range(2 * per):
            h.append(frozenset(L.step(h[-1], table)))
        if per < 2 or (h[per] == h[0] and h[2 * per] == h[0]):
            continue
        key = None
        for t in TRANSFORMS:
            rs = [{t(*q) for q in s & rotor} for s in ph]
            r0 = min(r for r, c in map(lambda q: t(*q), rotor))
            c0 = min(c for r, c in map(lambda q: t(*q), rotor))
            rs = [tuple(sorted((r - r0, c - c0) for r, c in s)) for s in rs]
            for k in range(per):
                cand = tuple(rs[(i + k) % per] for i in range(per))
                key = cand if key is None or cand < key else key
        out.append((ph, per, key, alone))
    return out


SECTIONS = [
    ("clean", "Clean oscillators (the spark starts them; the still life loses nothing)"),
    ("catalyst", "Catalysts (the spark is absorbed; the still life recovers exactly)"),
    ("converter", "Spaceship converters (the still life recovers; spaceships leave)"),
    ("escape", "Escapes (the still life is back while something is outside it)"),
    ("signal", "Signals (still travelling with a fixed shape)"),
    ("extracted", "Oscillators found in damaging reactions and trivial oscillators (each part alone, without the spark)"),
    ("damaging", "Damaging oscillators (the spark breaks part of the still life)"),
    ("no-spark", "Oscillators that don't reach the must-reach area in their own cycle"),
]


# ---- worker processes: every result is finished independently, so they share the cores

FIN = None


def _init(cfg, table, seconds, cnf):
    global FIN
    L.set_cnf_cache(cnf)
    FIN = Finisher(cfg, table, seconds)


def spark_key(cyc, how):
    """Sort key for --sort (smaller first) from L.spark_stats."""
    o, d, t = L.spark_stats(cyc)
    return (-d, -t, -o) if how == "sparky" else (-o, -t, -d)


def spark_note(cyc):
    o, d, t = L.spark_stats(cyc)
    return f"open {100 * o:.0f}%, spark depth {d}, {t} touch cells"


RANK = {"clean": 0, "catalyst": 0, "converter": 0, "escape": 0, "signal": 0, "no-spark": 1, "damaging": 2, "debris": 3}


def _classify(job):
    """The best classification among a group's first candidates, or None."""
    kind, cands = job
    best = None
    for res in cands[:6]:
        try:
            r = getattr(FIN, kind)(res)
        except Exception as e:   # one bad result shouldn't stop the rest
            print(f"  (result #{res['n']} skipped: {e})", file=sys.stderr, flush=True)
            r = None
        if r and (best is None or RANK[r[0]] < RANK[best[0]] or
                  (RANK[r[0]] == RANK[best[0]] and r[1] and best[1] and r[1]["size"] < best[1]["size"])):
            best = r
        if best and RANK[best[0]] == 0:
            break
    if best and best[1]:
        best[1].pop("empty", None)   # a closure; rebuilt where it's needed
    return best


def _shrink(job):
    """(pattern to list, whether it couldn't be shrunk, whether a part couldn't be separated)"""
    key, info = job
    if key == "extracted":
        g0 = FIN.extract(info)
    else:
        if "res" in info and "still" in info:
            info["empty"] = FIN.empty_for(info["res"])
        g0 = FIN.shrink(key, info)
    return g0, bool(info.get("unshrunk")), bool(info.get("unseparated"))


class Workers:
    """map / imap over worker processes (or in this process with jobs = 1)."""
    def __init__(self, jobs, init):
        self.jobs, self.init, self.pool = jobs, init, None

    def __enter__(self):
        if self.jobs > 1:
            import multiprocessing
            self.pool = multiprocessing.get_context("spawn").Pool(self.jobs, _init, self.init)
        else:
            _init(*self.init)
        return self

    def imap(self, fn, items):
        return self.pool.imap(fn, items) if self.pool else map(fn, items)

    def __exit__(self, *_):
        if self.pool:
            self.pool.terminate()


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("config")
    ap.add_argument("--jsonl", help="results file (default: <config>-results.jsonl)")
    ap.add_argument("--out", help="output file (default: <config>-finished.txt)")
    ap.add_argument("--all", action="store_true",
                    help="also list oscillators without a spark in their cycle, and long fizzles "
                         "(always listed when the config uses no-rechange or push)")
    ap.add_argument("--clean-only", action="store_true", help="don't list damaging oscillators, or the oscillators found in them")
    ap.add_argument("--keep-trivial", action="store_true",
                    help="list trivial oscillators (rotor parts more than 2 cells apart, so they can't "
                         "interact) as they are, instead of only their parts")
    ap.add_argument("--sort", choices=("period", "sparky", "open"), default="period",
                    help="order of the oscillator sections: period (default), sparky (free sparks first: "
                         "spark depth, then touch cells) or open (largest share of the rotor reachable "
                         "from outside first). The numbers are in each pattern's comment")
    ap.add_argument("--limit", type=int, default=30, help="patterns listed per section (default 30)")
    ap.add_argument("--max-cells", type=int, default=0, help="leave out patterns bigger than this")
    ap.add_argument("--seconds", type=float, default=5, help="time spent shrinking each listed pattern")
    ap.add_argument("--jobs", type=int, default=os.cpu_count() or 1,
                    help="processes to use (default: all cores); the output is the same with any number")
    ap.add_argument("--max-minutes", type=float, default=0,
                    help="time limit: the most promising results (highest periods, longest reactions) "
                         "are checked first, and patterns are listed unshrunk once time is short")
    a = ap.parse_args()
    import time
    deadline = time.time() + a.max_minutes * 60 if a.max_minutes else float("inf")
    late = lambda frac: time.time() > deadline - (1 - frac) * a.max_minutes * 60
    base = a.config[:-4] if a.config.endswith(".cfg") else a.config
    jsonl = a.jsonl or base + "-results.jsonl"
    out = a.out or base + "-finished.txt"
    if not os.path.exists(jsonl):
        sys.exit(f"finish.py: no results file {jsonl}. Run drift on {a.config} first, or pass --jsonl.")
    L.need_pysat()
    rule = L.config_rule(a.config)
    table = L.rule_for(rule)
    fin = Finisher(a.config, table, a.seconds)
    L.rule_cnf(table, "still")
    L.rule_cnf(table, "step")
    init = (a.config, table, a.seconds, L.cnf_cache())

    # 1. group the results (one entry per distinct rotor / reaction / signal)
    # Long thin fizzles are usually a signal running along a short wire. That's
    # noise in most searches, but the point of a drifter search.
    drifters = bool(re.search(r"^\s*(no-rechange|push)\b", open(a.config).read(), re.M))
    groups = collections.defaultdict(list)
    for line in open(jsonl):
        res = json.loads(line)
        k = res["kind"]
        if k == "oscillator":
            groups[(k, res["rotor"])].append(res)
        elif k == "fizzle":
            h, w = map(int, res["history"].split()[2].split("x"))
            if max(h, w) <= 8 or a.all or drifters:
                groups[(k, res["history"])].append(res)
        elif k == "maxgen":
            groups[(k, tuple(res["change_counts"][-12:]))].append(res)
        elif k == "escape":
            groups[(k, tuple(res["change_counts"]))].append(res)
    print(f"finishing {sum(map(len, groups.values()))} results ({len(groups)} distinct)...", flush=True)

    # 2. classify (quick), keeping the best candidate of each group
    found = collections.defaultdict(list)
    counts = collections.Counter()
    order = sorted(groups.items(), key=lambda kv: -max(r.get("period", 0) * 1000 + r["gen"] for r in kv[1]))
    for kv in order:
        kv[1].sort(key=lambda r: r["gen"])
    with Workers(min(a.jobs, len(order)), init) as W:
        for gi, best in enumerate(W.imap(_classify, [(kind, cands) for (kind, _), cands in order])):
            if late(0.6):
                counts["unchecked"] = len(order) - gi
                break
            if not best:
                counts["incomplete"] += 1
                continue
            kind = best[0]
            if kind in ("clean", "damaging", "no-spark") and not a.keep_trivial:
                g, p = best[1]["res"]["gen"], best[1]["res"]["period"]
                if len(rotor_groups(best[1]["hist"][g:g + p])) > 1:
                    best[1]["was"], kind = kind, "trivial"
            counts[kind] += 1
            if kind != "debris":
                found[kind].append(best[1])

    # The oscillators a damaging reaction ends in are real oscillators in their
    # own right, even though the spark doesn't start them cleanly; so are the
    # parts of a trivial oscillator. Each part is checked on its own; parts that
    # oscillate without a stator, and rotors already listed (here or as clean
    # oscillators), are left out.
    seen = set()
    for i in found.get("clean", []):
        g, p = i["res"]["gen"], i["res"]["period"]
        seen |= {k for _, _, k, _ in oscillator_parts(i["hist"][g:g + p], fin.table)}
    ext, queued = [], set()
    known = lambda i: i["whole"] and str(i["res"].get("known")) == "True"
    sources = [i for i in found.get("trivial", [])
               if i["was"] == "clean" or (i["was"] == "damaging" and not a.clean_only) or (i["was"] == "no-spark" and a.all)]
    if not a.clean_only:
        sources += found.get("damaging", [])
    for i in sources:
        g, p = i["res"]["gen"], i["res"]["period"]
        whole = i["hist"][g:g + p]
        parts = oscillator_parts(whole, fin.table)
        # drift's known-rotor flag describes the whole rotor, so it only applies to a part that is all of it
        nrot = len(set().union(*whole) - frozenset.intersection(*whole))
        for cyc, per, k, alone in parts:
            if k not in seen and k not in queued:
                queued.add(k)
                rotor = len(set().union(*cyc) - frozenset.intersection(*cyc))
                ext.append(dict(res=i["res"], cyc=cyc, period=per, rotor=rotor, whole=rotor == nrot,
                                alone=alone, full=whole[0]))
    if ext:
        ext.sort(key=lambda i: (known(i), -i["period"], -i["rotor"]))
        found["extracted"] = ext

    # 3. shrink and write the ones that are listed
    lines = [f"# drift results for {a.config}, finished by finish.py (rule {rule}).",
             "# Each pattern is gen 0 (still life + spark); paste into Golly with this rule.", None, ""]
    summary = []
    with Workers(a.jobs, init) as W:
        for key, title in SECTIONS:
            items = found.get(key, [])
            if (key == "no-spark" and not a.all) or (key == "damaging" and a.clean_only):
                continue
            if key in ("clean", "damaging", "no-spark"):
                if a.sort == "period":
                    items.sort(key=lambda i: (-i["res"]["period"], i.get("damage", 0), i["size"]))
                else:   # on the unshrunk patterns: this picks what gets past --limit
                    cycle = lambda i: i["hist"][i["res"]["gen"]:i["res"]["gen"] + i["res"]["period"]]
                    items.sort(key=lambda i: (spark_key(cycle(i), a.sort), -i["res"]["period"], i["size"]))
            elif key == "catalyst":
                items.sort(key=lambda i: (-i["res"]["gen"], i["size"]))
            elif key == "extracted" and a.sort != "period":
                items.sort(key=lambda i: (known(i), spark_key(i["cyc"], a.sort), -i["period"]))
            final = {}   # listed pattern -> its --sort key, measured on the shrunk pattern
            written, shown = [], set(seen) if key == "extracted" else set()
            i = 0
            while i < len(items) and len(written) < a.limit:
                chunk = items[i:i + max(a.jobs, a.limit - len(written))]
                i += len(chunk)
                if late(0.95):
                    outs = [((info["cyc"][0] if info["alone"] else info["full"]) if key == "extracted"
                             else info["hist"][0] if info.get("hist") else None, True,
                             key == "extracted" and not info["alone"])
                            for info in chunk]
                else:
                    outs = W.imap(_shrink, [(key, info) for info in chunk])
                for info, (g0, unshrunk, unseparated) in zip(chunk, outs):
                    if len(written) >= a.limit:
                        break
                    if unshrunk:
                        info["unshrunk"] = True
                    res = info["res"]
                    if key == "extracted":
                        if unseparated:   # no stator of its own was found: list the whole oscillator once
                            if info["full"] in shown:
                                continue
                            shown.add(info["full"])
                            head = (f"p{res['period']} oscillator, {len(g0)} cells, from the reaction of result #{res['n']}: "
                                    f"trivial, but its p{info['period']} part couldn't be given a stator of its own")
                            written.append(f"#C {head}\n" + L.to_rle(g0, rule).rstrip())
                            continue
                        # A smaller stator can leave separate oscillators side by side: list each new one
                        ph = [g0]
                        for _ in range(info["period"] - 1):
                            ph.append(frozenset(L.step(ph[-1], fin.table)))
                        for cyc, p, k, alone in oscillator_parts(ph, fin.table):
                            if not alone:   # not expected: a stator found for one rotor joins no other
                                continue
                            if k in shown or len(written) >= a.limit:
                                continue
                            shown.add(k)
                            if a.max_cells and len(cyc[0]) > a.max_cells:
                                continue
                            head = f"p{p} oscillator, {len(cyc[0])} cells, from the reaction of result #{res['n']}"
                            if info["whole"] and p == info["period"] and len(cyc[0]) == len(g0):
                                if str(res.get("known")) == "True":
                                    head += ", known rotor" + (f": {res['name']}" if res.get("name") else "")
                                elif "known" in res and rule.upper() == "B3/S23":
                                    head += ", rotor not in the known rotors list"
                            head += ", billiard table" if not L.exposed(cyc[0], p, fin.table) else ""
                            head += ", " + spark_note(cyc)
                            head += " (couldn't be shrunk)" if info.get("unshrunk") else ""
                            written.append(f"#C {head}\n" + L.to_rle(cyc[0], rule).rstrip())
                            final[written[-1]] = spark_key(cyc, a.sort)
                        continue
                    if a.max_cells and g0 is not None and len(g0) > a.max_cells:
                        continue
                    if key in ("clean", "damaging", "no-spark"):
                        p = res["period"]
                        head = f"p{p} oscillator, {len(g0)} cells, oscillating from gen {res['gen'] - p}"
                        head += ", billiard table" if not L.exposed(g0, p, fin.table) and key == "clean" else ""
                        if info.get("damage"):
                            head += f", {info['damage']} still-life cells changed for good"
                        h = [g0]
                        for _ in range(res["gen"] + p - 1):
                            h.append(frozenset(L.step(h[-1], fin.table)))
                        cyc = h[res["gen"]:]
                        head += ", " + spark_note(cyc)
                        spark = spark_key(cyc, a.sort)
                    elif key == "catalyst":
                        head = f"catalyst, {len(g0)} cells, reaction lasts {res['gen']} gens"
                    elif key == "converter":
                        head = f"converter, {len(g0)} cells: {info['what']}"
                    elif key == "escape":
                        head = f"escape, {len(g0)} cells, still life back at gen {res['gen']} with outside: {info['what']}"
                    else:
                        head = f"signal: {info['what']} (result #{res['n']} in {os.path.basename(jsonl)})"
                    if info.get("unshrunk"):
                        head += " (couldn't be shrunk)"
                    written.append(f"#C {head}\n" + (L.to_rle(g0, rule).rstrip() if g0 is not None else ""))
                    if key in ("clean", "damaging", "no-spark"):
                        final[written[-1]] = spark
            if not items:
                continue
            if a.sort != "period" and key in ("clean", "damaging", "no-spark", "extracted"):
                written.sort(key=lambda w: final.get(w, (9,)))   # trivial-part notes have no key: last
            if key == "extracted":   # counted after shrinking and splitting, so only up to --limit
                if not written:
                    continue
                n = f"{len(written)}+" if len(written) >= a.limit else str(len(written))
                summary.append(f"{n} {title.split(' (')[0].lower()}")
                lines.append(f"## {title}: {n}" + (" (stopped at --limit)" if n.endswith("+") else ""))
                lines.append("")
                lines += [w + "\n" for w in written]
                continue
            summary.append(f"{len(items)} {title.split(' (')[0].lower()}")
            lines.append(f"## {title}: {len(items)}" + (f" (showing {len(written)})" if len(written) < len(items) else ""))
            lines.append("")
            lines += [w + "\n" for w in written]
    lines[2] = "# Found: " + (", ".join(summary) if summary else "nothing usable")
    if counts["trivial"]:
        lines[2] += (f"\n# {counts['trivial']} trivial oscillators (rotor parts more than 2 cells apart, so they "
                     "can't interact) not listed whole; their parts are under \"Oscillators found\" (--keep-trivial lists them)")
    if counts["unchecked"]:
        lines[2] += f"\n# {counts['unchecked']} lower-priority results not checked (time limit)"
    open(out, "w").write("\n".join(lines) + "\n")

    names = {"clean": "clean oscillators", "catalyst": "catalysts", "converter": "spaceship converters",
             "escape": "escapes",
             "signal": "signals", "damaging": "damaging oscillators", "no-spark": "oscillators without a spark in their cycle",
             "debris": "debris (dropped)", "incomplete": "couldn't be completed",
             "trivial": "trivial oscillators (rotor parts more than 2 cells apart; only the parts are listed)",
             "unchecked": "not checked (--max-minutes ran out; lowest periods / shortest reactions)"}
    for k, name in names.items():
        if counts[k]:
            print(f"  {counts[k]:4d}  {name}")
    print(f"Saved to {out}")
    if counts["no-spark"] and not a.all:
        print("  (oscillators without a spark in their cycle aren't listed; add --all)")
    if not (counts["clean"] + counts["trivial"] + counts["catalyst"] + counts["converter"] + counts["escape"] + counts["signal"] + counts["damaging"]):
        skip = " ".join(l.split("=", 1)[1] for l in open(a.config) if re.match(r"\s*skip\s*=", l))
        print("Nothing usable was found. Things to try:")
        if "fizzle" in skip:
            print("  - catalysts were skipped: remove 'fizzle' from skip")
        print("  - looser limits (max-changed, size), or put the spark next to unknown cells")


if __name__ == "__main__":
    main()
