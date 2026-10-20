#!/usr/bin/env python3
"""Survey a rule: run a battery of drift searches at once and collect what they find.

    python3 tools/survey.py B3/S135                 # 10 minutes, all cores
    python3 tools/survey.py B3/S135 --minutes 30 --threads 8
    python3 tools/survey.py B3/S135 --resume --minutes 30   # continue unfinished searches

Searches (pick some with --jobs; --list shows them):
  osc        one spark cell in an unknown background, 6 changed cells in 4x4:
             oscillators and catalysts
  osc-big    the same with 8 cells in 5x5 (much bigger; usually stopped by the clock)
  sparky     oscillators whose own cycle throws a spark into empty space
  signals    disturbances still travelling at max gen: wires and signals
  drifters   drifters that keep moving onto fresh cells (no-rechange 8,80)
  converter  a spark in, a different spark out, and the still life recovers
  SHIP-...   for each small spaceship of the rule (found automatically, or --ship FILE):
             SHIP-eaters (eaters and oscillators), SHIP-converter (ship in,
             something travelling out), SHIP-drifter (ship -> drifting signal)

All searches run at the same time, sharing --threads cores. When one finishes,
its cores go to the others straight away (drift --threads-file). At the time
limit every search still running saves a checkpoint, so --resume continues it.
Each finished search is completed and checked by finish.py, and SUMMARY.md lists
the best of everything.

Output in surveys/<rule>/ (or --out DIR): one config per search, its results
(NAME-results.txt/.jsonl), complete patterns (NAME-finished.txt), a log, and
SUMMARY.md.
"""
import argparse
import itertools
import json
import math
import os
import re
import signal
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import driftlib as L  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
DRIFT = os.path.abspath(os.path.join(HERE, "..", "drift"))
FINISH = os.path.join(HERE, "finish.py")
WIRECHECK = os.path.join(HERE, "wirecheck.py")
SPARK = "x = 1, y = 1, rule = LifeHistory\nC!"

# name -> (description, config body without the rule line, pattern)
BASIC = {
    "osc": ("oscillators and catalysts (6 cells in 4x4)", """
max-changed = 6
size = 4x4
skip = stable
""", SPARK),
    "osc-big": ("oscillators and catalysts (8 cells in 5x5)", """
max-changed = 8
size = 5x5
skip = stable
per-rotor = 3
""", SPARK),
    "sparky": ("sparky oscillators (8 cells in 5x5, empty space above)", """
max-changed = 8
size = 5x5
clear = r -60 -60 -1 60
must-reach = r -60 -60 -1 60
skip = fizzle, stable
min-period = 3
per-rotor = 5
""", SPARK),
    "signals": ("signals still travelling at max gen (6 cells in 4x4)", """
max-changed = 6
size = 4x4
margin = 50
max-gen = 80
skip = oscillator, fizzle, stable
per-rotor = 3
""", SPARK),
    "drifters": ("drifters onto fresh cells (9 cells in 4x4, no-rechange 8,80)", """
max-changed = 9
size = 4x4
margin = 40
max-gen = 120
skip = stable, oscillator
per-rotor = 0
max-results = 3000
no-rechange = 8,80
""", SPARK),
    # spark at (0,0); still life in rows -4..4, cols 1..9; output spark outside that box
    "converter": ("spark converters (10 cells in 6x6, still life in a 9x9 box)", """
max-changed = 10
size = 6x6
clear = r -60 -60 -5 80
clear = r 5 -60 60 80
clear = r -4 -60 4 0
clear = r -4 10 4 80
must-reach = r -60 4 -5 80
must-reach = r 5 4 60 80
must-reach = r -60 10 60 80
must-reach = r -60 -60 -4 3
must-reach = r 4 -60 60 3
skip = oscillator, stable
per-rotor = 3
""", SPARK),
}

# Limits grow with the ship: {c} = its largest phase's population + extra cells,
# {w}x{h} = its largest phase's box + extra room; {nr} is measured (see write_configs).
SHIPJOBS = {
    "eaters": ("eaters and oscillators made by a {ship} ({c} cells in {w}x{h})", (6, 3), """
max-changed = {c}
size = {w}x{h}
skip = stable
"""),
    "converter": ("{ship} -> something travelling out ({c} cells in {w}x{h})", (10, 9), """
max-changed = {c}
size = {w}x{h}
skip = oscillator, fizzle, stable
per-rotor = 0
margin = 50
max-gen = 120
"""),
    "drifter": ("{ship} -> a drifting signal ({c} cells in {w}x{h}, no-rechange {nr},60)", (5, 3), """
max-changed = {c}
size = {w}x{h}
skip = stable, oscillator
margin = 40
max-gen = 150
per-rotor = 3
no-rechange = {nr},60
"""),
}

# Common spaceships, tried in every rule as well as the small-pattern scan.
KNOWN_SHIPS = {
    "glider": "bo$2bo$3o!",
    "lwss": "bo2bo$o$o3bo$4o!",
    "mwss": "3bo$bo3bo$o$o4bo$5o!",
    "hwss": "3b2o$bo4bo$o$o5bo$6o!",
}


# ---------------------------------------------------------------- spaceships

def normalize(cells):
    r0 = min(r for r, c in cells)
    c0 = min(c for r, c in cells)
    return frozenset((r - r0, c - c0) for r, c in cells)


def transforms(cells):
    out = []
    for flip in (False, True):
        for rot in range(4):
            s = cells
            for _ in range(rot):
                s = {(c, -r) for r, c in s}
            if flip:
                s = {(r, -c) for r, c in s}
            out.append(normalize(s))
    return out


def ship_motion(cells, table, maxp=12):
    """(period, dr, dc) if cells is a spaceship, else None."""
    cur = set(cells)
    base = normalize(cells)
    r0, c0 = min(r for r, c in cells), min(c for r, c in cells)
    for p in range(1, maxp + 1):
        cur = L.step(cur, table)
        if not cur or len(cur) > 4 * len(cells) + 20:
            return None
        if normalize(cur) == base:
            dr = min(r for r, c in cur) - r0
            dc = min(c for r, c in cur) - c0
            return (p, dr, dc) if (dr, dc) != (0, 0) else None
    return None


def orient(cells, table):
    """Rotate/reflect a ship so it moves right (orthogonal) or down-right."""
    best = None
    for t in transforms(cells):
        p, dr, dc = ship_motion(t, table, 16)
        if dr >= 0 and dc > 0 and dr <= dc:
            key = (dr != 0, sorted(t))
            if best is None or key < best[0]:
                best = (key, t, (p, dr, dc))
    return best[1], best[2]


def soup_census(table, seconds=10, procs=None):
    """Run random soups on every core (tools/soups.c) and count the spaceships
    that escape from them. Returns ({key: [count, cells]}, soups run)."""
    exe = os.path.join(os.path.dirname(DRIFT), "build", "soups")
    src = os.path.join(HERE, "soups.c")
    if not os.path.exists(exe) or os.path.getmtime(exe) < os.path.getmtime(src):
        os.makedirs(os.path.dirname(exe), exist_ok=True)
        subprocess.run(["cc", "-O2", "-o", exe, src], check=True)
    bits = "".join("1" if t else "0" for t in table)
    ps = [subprocess.Popen([exe, bits, str(i + 1), str(seconds)], stdout=subprocess.PIPE, text=True)
          for i in range(procs or os.cpu_count())]
    objs, soups = {}, 0
    for p in ps:
        for line in p.stdout:
            if line.startswith("cells:"):
                objs[line] = objs.get(line, 0) + 1
            elif line.startswith("soups"):
                soups += int(line.split()[1])
        p.wait()
    found = {}
    for line, n in objs.items():
        cells = {tuple(map(int, x.split(","))) for x in line.split()[1:]}
        if ship_motion(cells, table, 16):
            key = ship_key(cells, table)
            found.setdefault(key, [0, cells])[0] += n
    return found, soups


def ship_key(cells, table):
    """The same for every phase, rotation and reflection of a ship."""
    p = ship_motion(cells, table, 16)[0]
    phases, cur = [], set(cells)
    for _ in range(p):
        phases.append(cur)
        cur = L.step(cur, table)
    return min(tuple(sorted(t)) for ph in phases for t in transforms(ph))


def smallest_phase(cells, table):
    p = ship_motion(cells, table, 16)[0]
    best, cur = None, set(cells)
    for _ in range(p):
        n = normalize(cur)
        h, w = max(r for r, c in n) + 1, max(c for r, c in n) + 1
        k = (len(n), h * w, sorted(n))
        if best is None or k < best[0]:
            best = (k, n)
        cur = L.step(cur, table)
    return set(best[1])


def ships_from(cells, table, name, count=0):
    cells = smallest_phase(cells, table)
    if name.startswith("ship"):
        name = f"ship{len(cells)}"
    oc, (p, dr, dc) = orient(cells, table)
    d = max(abs(dr), abs(dc))
    g = math.gcd(d, p)
    speed = f"{'' if d == g else d // g}c/{p // g}"
    kind = "orthogonal" if dr == 0 else "diagonal" if dr == dc else "oblique"
    return {"name": name, "cells": sorted(oc), "period": p, "move": (dr, dc),
            "speed": f"{kind} {speed}", "soups": count}


def find_ships(table, seconds=10, procs=None):
    """Spaceships of the rule, most common in random soups first; the common
    Life ships are tried too, in case soups make none."""
    census, soups = soup_census(table, seconds, procs)
    found = {k: (n, f"ship{len(c)}", c) for k, (n, c) in census.items()}
    for name, rle in KNOWN_SHIPS.items():
        cells = {p for p, s in L.parse_rle(rle).items() if s == 1}
        if ship_motion(cells, table, 16):
            k = ship_key(cells, table)
            n = found[k][0] if k in found else 0
            found[k] = (n, name, cells)
    ships = [ships_from(cells, table, name, count) for count, name, cells in found.values()]
    ships.sort(key=lambda s: (-s["soups"], len(s["cells"])))
    used = set()
    for s in ships:   # unique names: ship5, ship5b, ...
        n, k = s["name"], 0
        while n in used:
            k += 1
            n = s["name"] + "bcdefghij"[k - 1]
        s["name"] = n
        used.add(n)
    return ships, soups


def ship_extent(ship, table):
    """(largest population, height, width) over the ship's phases."""
    cur, pop, h, w = set(map(tuple, ship["cells"])), 0, 0, 0
    for _ in range(ship["period"]):
        rs = [r for r, c in cur]
        cs = [c for r, c in cur]
        pop, h, w = max(pop, len(cur)), max(h, max(rs) - min(rs) + 1), max(w, max(cs) - min(cs) + 1)
        cur = L.step(cur, table)
    return pop, h, w


def ship_pattern(ship):
    """LifeHistory pattern: the ship (on in gen 0 only) in a ring of known-off cells."""
    cells = set(map(tuple, ship["cells"]))
    h = max(r for r, c in cells) + 3
    w = max(c for r, c in cells) + 3
    rows = ["".join("C" if (r - 1, c - 1) in cells else "B" for c in range(w)) for r in range(h)]
    return f"x = {w}, y = {h}, rule = LifeHistory\n" + "$".join(rows) + "!", h, w


def ship_clears(ship, h, w):
    """Empty space behind the ship (where it came from)."""
    if ship["move"][0] == 0:   # moving right: empty to the left, above and below its rows
        return [f"clear = r -40 -40 40 -1", f"clear = r -40 0 -1 {w - 1}", f"clear = r {h} 0 40 {w - 1}"]
    return [f"clear = r -40 -40 {h - 1} -1", f"clear = r -40 -40 -1 {w - 1}"]


# ---------------------------------------------------------------- jobs

class Job:
    def __init__(self, name, desc, cfg):
        self.name, self.desc, self.cfg = name, desc, cfg
        self.base = cfg[:-4]
        self.ckpt = self.base + ".ckpt"
        self.tfile = self.base + ".threads"
        self.log = self.base + ".log"
        self.proc = self.fin = None
        self.state = "waiting"      # waiting, running, finishing, done
        self.complete = False       # the search space was exhausted
        self.threads = 0
        self.started = None
        self.seconds = 0.0

    def set_threads(self, n):
        if n != self.threads:
            with open(self.tfile, "w") as f:
                f.write(f"{n}\n")
            self.threads = n


def rule_dirname(rule):
    return re.sub(r"[^A-Za-z0-9_-]+", "-", rule if not rule.startswith("MAP") else "MAP" + rule[3:15]).strip("-")


def write_configs(rule, out, names, ships, table):
    jobs = []
    for name, (desc, body, pat) in BASIC.items():
        if names and name not in names:
            continue
        cfg = os.path.join(out, name + ".cfg")
        with open(cfg, "w") as f:
            f.write(f"# survey of {rule}: {desc}\nrule = {rule}\nno-pics{body}\npattern:\n{pat}\n")
        jobs.append(Job(name, desc, cfg))
    for ship in ships:
        pat, h, w = ship_pattern(ship)
        pop, bh, bw = ship_extent(ship, table)
        for kind, (desc, (dc, db), body) in SHIPJOBS.items():
            name = f"{ship['name']}-{kind}"
            if names and name not in names and ship["name"] not in names:
                continue
            cfg = os.path.join(out, name + ".cfg")
            lim = dict(c=pop + dc, w=bw + db, h=bh + db, nr=4)
            def write():
                d = desc.format(ship=f"{ship['name']} ({ship['speed']})", **lim)
                with open(cfg, "w") as f:
                    f.write(f"# survey of {rule}: {d}\n# the ship flies in from empty space\n"
                            f"rule = {rule}\nno-pics{body.format(**lim)}" + "\n".join(ship_clears(ship, h, w)) +
                            f"\npattern:\n{pat}\n")
                return d
            d = write()
            if "{nr}" in body:   # the smallest no-rechange gap the ship survives, plus 1
                for nr in range(2, 4 * ship["period"]):
                    r = subprocess.run([DRIFT, cfg, "--no-rechange", f"{nr},60", "--threads", "1", "--quiet",
                                        "--no-save", "--no-finish", "--max-steps", "2000000"],
                                       capture_output=True, text=True).stdout
                    if "Search stopped" in r:
                        lim["nr"] = nr + 1
                        break
                d = write()
            jobs.append(Job(name, d, cfg))
    return jobs


def ckpt_complete(path):
    try:
        for line in open(path):
            if line.startswith("items "):
                return line.split()[1] == "0"
    except OSError:
        pass
    return False


def footer(job):
    """drift's last 'Search ...' and 'Found ...' lines."""
    try:
        text = open(job.log).read()
    except OSError:
        return "", ""
    s = re.findall(r"^Search .*$", text, re.M)
    f = re.findall(r"^Found .*$", text, re.M)
    return (s[-1] if s else ""), (f[-1] if f else "")


# ---------------------------------------------------------------- running

class Survey:
    def __init__(self, a, jobs):
        self.a, self.jobs = a, jobs
        self.threads = a.threads
        self.deadline = time.time() + a.minutes * 60
        self.stopping = False

    def start(self, job, seconds):
        cmd = [DRIFT]
        if self.a.resume and os.path.exists(job.ckpt):
            cmd += ["--resume", job.ckpt]
        else:
            cmd += [job.cfg, "--checkpoint", job.ckpt]
        cmd += ["--threads", str(self.threads), "--threads-file", job.tfile, "--max-time", str(int(seconds)),
                "--no-finish", "--progress", "60", "--checkpoint-every", "120"]
        log = open(job.log, "a")
        log.write(f"\n$ {' '.join(cmd)}\n")
        log.flush()
        job.proc = subprocess.Popen(cmd, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
        job.state, job.started = "running", time.time()

    def finish(self, job):
        job.seconds += time.time() - job.started
        job.complete = ckpt_complete(job.ckpt)
        s, f = footer(job)
        has = os.path.exists(job.base + "-results.jsonl") and os.path.getsize(job.base + "-results.jsonl") > 0
        self.say(f"{job.name}: {'complete' if job.complete else 'stopped'} — {s.split(' (')[0]}; "
                 f"{f.split(';')[0]}")
        if not has or self.a.no_finish:
            job.state = "done"
            return
        cmd = [sys.executable, FINISH, job.cfg, "--seconds", "1", "--limit", "20",
               "--max-minutes", str(self.a.finish_minutes)]
        job.fin = subprocess.Popen(cmd, stdout=open(job.base + "-finish.log", "w"), stderr=subprocess.STDOUT,
                                   start_new_session=True)
        job.state = "finishing"

    def rebalance(self):
        running = [j for j in self.jobs if j.state == "running"]
        finishing = sum(j.state == "finishing" for j in self.jobs)
        if not running:
            return
        free = max(len(running), self.threads - finishing)
        share, extra = divmod(free, len(running))
        for i, j in enumerate(running):
            j.set_threads(share + (i < extra))

    def say(self, msg):
        t = time.strftime("%H:%M:%S")
        print(f"[{t}] {msg}", flush=True)

    def status(self):
        parts = []
        for j in self.jobs:
            if j.state == "running":
                parts.append(f"{j.name}:{j.threads}t")
            elif j.state == "finishing":
                parts.append(f"{j.name}:finishing")
        left = max(0, self.deadline - time.time())
        done = sum(j.state == "done" for j in self.jobs)
        self.say(f"{done}/{len(self.jobs)} done, {left / 60:.1f} min left | " + " ".join(parts))

    def interrupt(self, *_):
        if self.stopping:
            return
        self.stopping = True
        self.say("stopping: each search saves a checkpoint (run again with --resume to continue)")
        for j in self.jobs:
            if j.proc and j.proc.poll() is None:
                j.proc.send_signal(signal.SIGINT)

    def run(self):
        signal.signal(signal.SIGINT, self.interrupt)
        for j in self.jobs:
            if self.a.resume and ckpt_complete(j.ckpt):
                j.state, j.complete = "done", True
                continue
            j.threads = 0
            j.set_threads(1)
        waiting = [j for j in self.jobs if j.state == "waiting"]
        for j in waiting:
            self.start(j, self.deadline - time.time())
        self.rebalance()
        self.say(f"{len(waiting)} searches on {self.threads} threads, "
                 f"{self.a.minutes:g} min: " + ", ".join(f"{j.name}:{j.threads}t" for j in waiting))
        last = time.time()
        while any(j.state in ("running", "finishing") for j in self.jobs):
            time.sleep(1)
            for j in self.jobs:
                if j.state == "running" and j.proc.poll() is not None:
                    self.finish(j)
                elif j.state == "finishing" and j.fin.poll() is not None:
                    j.state = "done"
                    self.say(f"{j.name}: {finished_line(j)}")
            self.rebalance()
            if time.time() - last >= self.a.status:
                self.status()
                last = time.time()


# ---------------------------------------------------------------- summary

def sections(path, limit=3):
    """[(title, count, [(comment, rle)])] from a -finished.txt file."""
    out, cur = [], None
    try:
        lines = open(path).read().split("\n")
    except OSError:
        return out
    i = 0
    while i < len(lines):
        l = lines[i]
        m = re.match(r"## (.*): (\d+)\+?( \((showing \d+|stopped at --limit)\))?$", l)
        if m:
            cur = (m.group(1), int(m.group(2)), [])
            out.append(cur)
        elif l.startswith("#C ") and cur is not None and len(cur[2]) < limit:
            j = i + 1
            rle = []
            while j < len(lines) and lines[j].strip():
                rle.append(lines[j])
                j += 1
            cur[2].append((l[3:], "\n".join(rle)))
            i = j
            continue
        i += 1
    return out


def finished_line(job):
    secs = sections(job.base + "-finished.txt", 0)
    return ", ".join(f"{n} {t.split(' (')[0].lower()}" for t, n, _ in secs) or "nothing usable"


def write_summary(a, jobs):
    out = os.path.join(a.out, "SUMMARY.md")
    L_ = [f"# Survey of {a.rule}", "",
          f"Each search's complete patterns are in `NAME-finished.txt`; raw results in `NAME-results.txt`.",
          "Patterns are generation 0 in plain RLE for this rule.", ""]
    if a.ships:
        L_ += ["## Spaceships used", ""]
        for s in a.ships:
            L_.append(f"- **{s['name']}**: {s['speed']}, {len(s['cells'])} cells, "
                      f"`{L.to_rle(set(map(tuple, s['cells'])), a.rule).split(chr(10))[-1]}`")
        L_.append("")
    L_ += ["## Searches", "", "| search | status | time | results | finished |", "|---|---|---|---|---|"]
    for j in jobs:
        s, f = footer(j)
        st = "complete" if ckpt_complete(j.ckpt) else ("stopped (resumable)" if os.path.exists(j.ckpt) else "not run")
        tm = re.search(r"after ([\d.]+s)", s)
        found = f.replace("Found ", "").split(";")[0] if f else ""
        L_.append(f"| {j.name} | {st} | {tm.group(1) if tm else ''} | {found} | {finished_line(j)} |")
    L_.append("")
    L_.append("## Best of each search")
    for j in jobs:
        secs = sections(j.base + "-finished.txt")
        if not any(n for _, n, _ in secs):
            continue
        L_ += ["", f"### {j.name}: {j.desc}", ""]
        for title, n, items in secs:
            L_.append(f"**{title}: {n}**")
            L_.append("")
            for comment, rle in items:
                L_ += ["```", f"#C {comment}", rle, "```"]
            L_.append("")
        wl = j.base + "-wires.txt"
        if os.path.exists(wl):
            L_ += ["Wire candidates (wirecheck.py):", "```", open(wl).read().strip(), "```", ""]
    with open(out, "w") as f:
        f.write("\n".join(L_) + "\n")
    print(f"\nSummary: {out}")


def wire_candidates(jobs):
    for j in jobs:
        js = j.base + "-results.jsonl"
        if (j.name in ("signals", "drifters") or j.name.endswith("-drifter")) and os.path.exists(js):
            r = subprocess.run([sys.executable, WIRECHECK, js, "--top", "5"], capture_output=True, text=True)
            with open(j.base + "-wires.txt", "w") as f:
                f.write(r.stdout)


# ---------------------------------------------------------------- main

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("rule")
    ap.add_argument("--minutes", type=float, default=10, help="wall-clock time for the whole survey (default 10)")
    ap.add_argument("--threads", type=int, default=os.cpu_count(), help="cores to share (default: all)")
    ap.add_argument("--out", help="output folder (default: surveys/<rule> next to drift/)")
    ap.add_argument("--jobs", help="comma-separated searches to run (default: all; e.g. osc,sparky,glider)")
    ap.add_argument("--ship", action="append", default=[],
                    help="a spaceship to use first: an RLE file, or the RLE itself in quotes "
                         "(may be repeated); adds SHIP-* searches")
    ap.add_argument("--census", type=float, default=10,
                    help="seconds of random soups to find the rule's common spaceships (default 10)")
    ap.add_argument("--no-ships", action="store_true", help="don't look for spaceships")
    ap.add_argument("--max-ships", type=int, default=2, help="spaceships to search with (most common in soups first; default 2)")
    ap.add_argument("--resume", action="store_true", help="continue the searches saved in the output folder")
    ap.add_argument("--no-finish", action="store_true", help="don't complete the results with finish.py")
    ap.add_argument("--finish-minutes", type=float, default=3,
                    help="time limit for finishing each search's results (default 3)")
    ap.add_argument("--status", type=float, default=60, help="seconds between status lines (default 60)")
    ap.add_argument("--list", action="store_true", help="show the searches that would run, and exit")
    ap.add_argument("--summary", action="store_true", help="only rewrite SUMMARY.md from the files there")
    a = ap.parse_args()
    if not os.path.exists(DRIFT):
        sys.exit(f"build drift first: cd {os.path.dirname(DRIFT)} && make")
    a.out = a.out or os.path.join(os.path.dirname(DRIFT), "..", "surveys", rule_dirname(a.rule))
    a.out = os.path.abspath(a.out)
    os.makedirs(a.out, exist_ok=True)
    table = L.rule_for(a.rule)
    names = set(a.jobs.split(",")) if a.jobs else None

    shipfile = os.path.join(a.out, "ships.json")
    if (a.resume or a.summary) and os.path.exists(shipfile):
        a.ships = json.load(open(shipfile))
    elif a.no_ships:
        a.ships = []
    else:
        print(f"looking for spaceships in random soups ({a.census:g} s; --census changes this)...", flush=True)
        ships, soups = find_ships(table, a.census, a.threads)
        a.soups = soups
        for k, text in enumerate(a.ship):   # an RLE file, or the RLE itself
            isfile = os.path.exists(text)
            cells = {p for p, s in L.parse_rle(open(text).read() if isfile else text.replace("\\n", "\n")).items()
                     if s == 1}
            if not cells or not ship_motion(cells, table, 16):
                sys.exit(f"--ship {text}: not a spaceship in {a.rule}")
            key = ship_key(cells, table)
            same = [s for s in ships if ship_key(set(map(tuple, s["cells"])), table) == key]
            ship = same[0] if same else dict(ships_from(cells, table, f"ship{len(cells)}"))
            if isfile:
                ship["name"] = os.path.splitext(os.path.basename(text))[0]
            if ship in ships:
                ships.remove(ship)
            ships.insert(k, ship)
        a.ships = ships[:max(a.max_ships, len(a.ship))]
        if ships:
            print(f"{soups} soups: " + ", ".join(f"{s['name']} {s['soups']}x" for s in ships[:6]))
        json.dump(a.ships, open(shipfile, "w"))
    if a.ships:
        print("searching with: " + ", ".join(f"{s['name']} ({s['speed']}, {len(s['cells'])} cells)" for s in a.ships))
    else:
        print("no small spaceships found (give one with --ship FILE)")
    jobs = write_configs(a.rule, a.out, names, a.ships, table)
    if a.list:
        for j in jobs:
            print(f"  {j.name:18} {j.desc}")
        return
    if a.summary:
        write_summary(a, jobs)
        return
    if not jobs:
        sys.exit("no searches selected (see --list)")
    print(f"output: {a.out}")
    Survey(a, jobs).run()
    wire_candidates(jobs)
    write_summary(a, jobs)


if __name__ == "__main__":
    main()
