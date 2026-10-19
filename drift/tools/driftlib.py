"""Shared code for drift's Python tools.

Rules: rule_for(rule_string) returns the rule table (any B/S, INT or MAP rule,
via the drift binary). Patterns are sets of live cells (row, col).

  parse_rle / to_rle        LifeHistory or two-state RLE in and out
  step                      one generation
  next3                     one cell's next state when some neighbours are unknown
  complete                  fill in a partial background with a still life (SAT)
  minimize                  smallest stator for a fixed reaction (SAT)
  needs_stator / exposed    oscillator tests (debris, billiard table)
  components / object_kind  split a pattern into objects and name them
  read_config / contains    read a drift config's pattern and regions
"""
import base64
import itertools
import os
import re
import subprocess
import sys
import threading
import time

DRIFT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "drift")


def rule_for(rule):
    """Rule table for any rule drift understands."""
    if rule.startswith("MAP"):
        return rule_table(rule)
    try:
        out = subprocess.run([DRIFT, "--show-rule", "--rule", rule], capture_output=True, text=True).stdout
        return rule_table(out.split("MAP:")[1].split()[0])
    except (IndexError, OSError):
        sys.exit(f"can't read rule {rule!r} (is drift built? {DRIFT})")


def need_pysat():
    try:
        import pysat  # noqa: F401
    except ImportError:
        sys.exit("This needs python-sat: pip install python-sat")


OFFS = [(-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 0), (0, 1), (1, -1), (1, 0), (1, 1)]


WEIGHT = [256, 128, 64, 32, 16, 8, 4, 2, 1]


def rule_table(rule):
    """table[k] for k = 256*NW + 128*N + 64*NE + 32*W + 16*C + 8*E + 4*SW + 2*S + SE"""
    if rule.startswith("MAP"):
        s = rule[3:]
        s += "=" * (-len(s) % 4)
        bits = "".join(f"{b:08b}" for b in base64.b64decode(s))
        return [bits[k] == "1" for k in range(512)]
    m = re.fullmatch(r"B(\d*)/S(\d*)", rule)
    if not m:
        sys.exit(f"can't read rule {rule!r}; use rule_for() for INT rules")
    birth, surv = set(map(int, m.group(1))), set(map(int, m.group(2)))
    table = []
    for k in range(512):
        n = bin(k & ~16).count("1")
        table.append(n in surv if k & 16 else n in birth)
    return table


def parse_rle(text):
    lines = [l for l in text.split("\n") if l and not l.startswith("#") and not l.startswith("x")]
    body = "".join(lines)
    cells, r, c, run = {}, 0, 0, ""
    for ch in body:
        if ch.isdigit():
            run += ch
            continue
        n = int(run) if run else 1
        run = ""
        if ch == "!":
            break
        if ch == "$":
            r += n
            c = 0
        elif ch in ".b":
            c += n
        else:
            state = 1 if ch == "o" else ord(ch) - ord("A") + 1
            for _ in range(n):
                cells[(r, c)] = state
                c += 1
    return cells


def next3(table, window, cache={}):
    """window: 9 values (0, 1 or None) -> 0, 1 or None (undetermined)"""
    key = (id(table), window)
    if key in cache:
        return cache[key]
    unk = [i for i, v in enumerate(window) if v is None]
    seen = set()
    for bits in itertools.product((0, 1), repeat=len(unk)):
        w = list(window)
        for i, b in zip(unk, bits):
            w[i] = b
        seen.add(table[sum(WEIGHT[i] for i in range(9) if w[i])])
        if len(seen) == 2:
            break
    res = int(seen.pop()) if len(seen) == 1 else None
    cache[key] = res
    return res


def step(live, table):
    cand = {(r + dr, c + dc) for r, c in live for dr, dc in OFFS}
    out = set()
    for r, c in cand:
        w = sum(WEIGHT[k] for k, (dr, dc) in enumerate(OFFS) if (r + dr, c + dc) in live)
        if table[w]:
            out.add((r, c))
    return out


def to_rle(live, rule):
    if not live:
        return f"x = 0, y = 0, rule = {rule}\n!"
    rs = [r for r, c in live]
    cs = [c for r, c in live]
    lines = []
    for r in range(min(rs), max(rs) + 1):
        row = "".join("o" if (r, c) in live else "b" for c in range(min(cs), max(cs) + 1)).rstrip("b")
        lines.append(row)
    body = "$".join(lines)
    # simple run-length compression
    out, i = "", 0
    while i < len(body):
        j = i
        while j < len(body) and body[j] == body[i]:
            j += 1
        out += (str(j - i) if j - i > 1 else "") + body[i]
        i = j
    return f"x = {max(cs) - min(cs) + 1}, y = {max(rs) - min(rs) + 1}, rule = {rule}\n{out}!"


def complete(cells, table, margin, empty=None, free=None, fewest=0):
    """Returns {(r,c): 0/1} background, or None if no completion fits.
    empty(p): True for cells that must stay dead.
    free(p): True for cells whose stability isn't required (drift's no-check cells).
    fewest: if > 0, spend up to this many seconds minimising the live cells added."""
    rs = [r for r, c in cells]
    cs = [c for r, c in cells]
    r0, r1, c0, c1 = min(rs) - margin, max(rs) + margin, min(cs) - margin, max(cs) + margin
    var = {}
    for r in range(r0, r1 + 1):
        for c in range(c0, c1 + 1):
            var[(r, c)] = len(var) + 1
    need_pysat()
    from pysat.solvers import Cadical153, Glucose4
    s = Glucose4() if fewest else Cadical153()   # Cadical can't be interrupted
    fixed = {}   # cell -> 0/1 where the value is already known
    if empty:
        for p, v in var.items():
            if empty(p) and cells.get(p) not in (1, 4):
                fixed[p] = 0
    for p, st in cells.items():
        if st in (1, 4):
            fixed[p] = 1
        elif st in (2, 3):
            fixed[p] = 0
    for p, b in fixed.items():
        if p in var:
            s.add_clause([var[p] if b else -var[p]])
    # Every cell in the box and the ring around it is stable (outside = dead).
    # Only the unknown cells of each window are enumerated; known ones are
    # filled in, so every clause is over unknown cells only.
    for r in range(r0 - 1, r1 + 2):
        for c in range(c0 - 1, c1 + 2):
            if free and free((r, c)):
                continue
            base, unk = 0, []
            for k, (dr, dc) in enumerate(OFFS):
                q = (r + dr, c + dc)
                v = var.get(q)
                if v is None or q in fixed:
                    if v is not None and fixed[q]:
                        base |= WEIGHT[k]
                else:
                    unk.append((WEIGHT[k], v))
            for bits in range(1 << len(unk)):
                w, clause = base, []
                for i, (wt, v) in enumerate(unk):
                    if bits >> i & 1:
                        w |= wt
                        clause.append(-v)
                    else:
                        clause.append(v)
                if table[w] != bool(w & 16):   # this neighbourhood isn't stable
                    if not clause:
                        s.delete()
                        return None
                    s.add_clause(clause)
    if not s.solve():
        return None
    model = set(x for x in s.get_model() if x > 0)
    if fewest:
        from pysat.card import ITotalizer
        added = [v for p, v in var.items() if p not in cells]
        tot = ITotalizer(lits=added, ubound=len(added), top_id=len(var))
        s.append_formula(tot.cnf.clauses)
        deadline = time.time() + fewest
        while time.time() < deadline:
            k = sum(1 for v in added if v in model) - 1
            if k < 0:
                break
            timer = threading.Timer(deadline - time.time(), s.interrupt)
            timer.start()
            ok = s.solve_limited(assumptions=[-tot.rhs[k]], expect_interrupt=True)
            timer.cancel()
            s.clear_interrupt()
            if not ok:
                break
            model = set(x for x in s.get_model() if x > 0)
    return {p: int(v in model) for p, v in var.items()}


def minimize(states, table, cyclic, margin=4, seconds=20, empty=None):
    """states: list of sets of live cells. empty(p): True for cells that must stay dead.
    Returns (live cells of states[0] with the smallest stator found, population)
    or None if no stator fits in the box."""
    need_pysat()
    from pysat.card import ITotalizer
    from pysat.solvers import Glucose4
    T = len(states)
    allc = set().union(*states)
    active = {p for p in allc if any((p in s) != (p in states[0]) for s in states)}
    if not active:
        return None
    rs = [r for r, c in active]
    cs = [c for r, c in active]
    r0, r1, c0, c1 = min(rs) - margin, max(rs) + margin, min(cs) - margin, max(cs) + margin
    var = {}
    for r in range(r0, r1 + 1):
        for c in range(c0, c1 + 1):
            if (r, c) not in active:
                var[(r, c)] = len(var) + 2   # 0 and 1 are the constants dead/alive
    clauses = []
    if empty:
        for p, v in var.items():
            if empty(p):
                clauses.append([-v])

    def value(p, t):   # constant 0/1 (dead/alive) or a variable number >= 2
        if p in active:
            return int(p in states[t])
        return var.get(p, 0)   # outside the box: dead

    def add(x, t, t2):
        """Cell x stepping from state t to state t2."""
        win = [value((x[0] + dr, x[1] + dc), t) for dr, dc in OFFS]
        target = value(x, t2)
        vs = sorted({v for v in win + [target] if v > 1})
        for a in range(1 << len(vs)):
            asg = {v: (a >> i) & 1 for i, v in enumerate(vs)}
            w = sum(WEIGHT[k] for k, v in enumerate(win) if (asg[v] if v not in (0, 1) else v))
            want = asg[target] if target not in (0, 1) else target
            if int(table[w]) != want:
                if not vs:
                    return False   # violated by constants alone
                clauses.append([-v if asg[v] else v for v in vs])
        return True

    if cyclic is True:
        steps = [(t, (t + 1) % T) for t in range(T)]
    elif cyclic is False:
        steps = [(t, t + 1) for t in range(T - 1)] + [(T - 1, T - 1)]
    else:   # lasso: the last state steps back to states[cyclic]
        steps = [(t, t + 1) for t in range(T - 1)] + [(T - 1, cyclic)]
    near = {(r + dr, c + dc) for r, c in active for dr in (-2, -1, 0, 1, 2) for dc in (-2, -1, 0, 1, 2)}
    for r in range(r0 - 1, r1 + 2):
        for c in range(c0 - 1, c1 + 2):
            x = (r, c)
            if x in near:
                for t, t2 in steps:
                    if not add(x, t, t2):
                        return None
            elif not add(x, 0, 0):   # far from the action: plain still life
                return None

    lits = list(var.values())
    s = Glucose4(bootstrap_with=clauses)
    tot = ITotalizer(lits=lits, ubound=len(lits))
    s.append_formula(tot.cnf.clauses)
    deadline = time.time() + seconds
    best, assume = None, []
    while True:
        left = deadline - time.time()
        if left <= 0:
            break
        timer = threading.Timer(left, s.interrupt)
        timer.start()
        ok = s.solve_limited(assumptions=assume, expect_interrupt=True)
        timer.cancel()
        s.clear_interrupt()
        if not ok:   # False = no smaller stator; None = out of time
            break
        model = set(x for x in s.get_model() if x > 0)
        live = {p for p, v in var.items() if v in model}
        best = live
        k = len(live) - 1
        if k < 0:
            break
        assume = [-tot.rhs[k]]
    s.delete()
    if best is None:
        return None
    g0 = (states[0] & active) | best
    return g0, len(g0)


def needs_stator(phase, period, table):
    """False if the rotor oscillates on its own once the stator is removed."""
    ph = [frozenset(phase)]
    for _ in range(period - 1):
        ph.append(frozenset(step(ph[-1], table)))
    stator = frozenset.intersection(*ph)
    h = [ph[0] - stator]
    for _ in range(2 * period):
        h.append(frozenset(step(h[-1], table)))
    return not (h[period] == h[0] and h[2 * period] == h[0])


def exposed(g0, period, table):
    """True if some rotor cell can be reached from outside the pattern without
    crossing a live stator cell (4-connected steps, so a diagonal chain of
    stator cells counts as a wall). False = billiard table."""
    phases = [frozenset(g0)]
    for _ in range(period - 1):
        phases.append(frozenset(step(phases[-1], table)))
    cells = set().union(*phases)
    stator = frozenset.intersection(*phases)
    rotor = cells - stator
    rs = [r for r, c in cells]
    cs = [c for r, c in cells]
    r0, r1, c0, c1 = min(rs) - 1, max(rs) + 1, min(cs) - 1, max(cs) + 1
    seen = {(r0, c0)}
    todo = [(r0, c0)]
    while todo:
        r, c = todo.pop()
        if (r, c) in rotor:
            return True
        for dr, dc in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            q = (r + dr, c + dc)
            if r0 <= q[0] <= r1 and c0 <= q[1] <= c1 and q not in seen and q not in stator:
                seen.add(q)
                todo.append(q)
    return False


def components(cells, d=2):
    cells, out = set(cells), []
    while cells:
        todo = [cells.pop()]
        comp = {todo[0]}
        while todo:
            r, c = todo.pop()
            for a in range(-d, d + 1):
                for b in range(-d, d + 1):
                    q = (r + a, c + b)
                    if q in cells:
                        cells.remove(q)
                        comp.add(q)
                        todo.append(q)
        out.append(frozenset(comp))
    return out


def object_kind(comp, table):
    """still life, pN oscillator, spaceship (dr,dc)/p, or None."""
    x = [comp]
    for _ in range(60):
        x.append(frozenset(step(x[-1], table)))
    for p in range(1, 31):
        a, b = sorted(x[30]), sorted(x[30 + p])
        if a and len(a) == len(b):
            d = (b[0][0] - a[0][0], b[0][1] - a[0][1])
            if all((q[0] - s[0], q[1] - s[1]) == d for s, q in zip(a, b)):
                if d == (0, 0):
                    return "still life" if p == 1 else f"p{p} oscillator"
                return f"spaceship moving {d} every {p}"
    return None


CHARS = {"o": "on", "O": "on", "3": "on", ".": "off", ":": "off", "2": "off",
         "1": "spark_on", "0": "spark_off", ",": "unknown", "?": "unknown", "s": "unknown",
         "4": "unchecked"}


LH = {0: "unknown", 1: "on", 2: "off", 3: "spark_on", 4: "spark_off", 5: "on", 6: "off"}


def parse_region(text):
    t = text.split()
    kind = t[0] if t[0] in "rltp" else "r"
    nums = list(map(int, t[1:] if t[0] in "rltp" else t))
    return kind, nums


def contains(reg, r, c):
    kind, n = reg
    if kind == "p":
        return (r, c) == (n[0], n[1])
    if kind in "rl":
        r0, c0, r1, c1 = n
        if not (min(r0, r1) <= r <= max(r0, r1) and min(c0, c1) <= c <= max(c0, c1)):
            return False
        return kind == "r" or r0 * (c1 - c) + r1 * (c - c0) + r * (c0 - c1) == 0
    r0, c0, r1, c1, r2, c2 = n
    o = r0 * (c1 - c2) + r1 * (c2 - c0) + r2 * (c0 - c1)
    return (o * (r0 * (c1 - c) + r1 * (c - c0) + r * (c0 - c1)) >= 0 and
            o * (r0 * (c - c2) + r * (c2 - c0) + r2 * (c0 - c)) >= 0 and
            o * (r * (c1 - c2) + r1 * (c2 - c) + r2 * (c - c1)) >= 0)


def load_pattern(text):
    lines = [l.rstrip("\r") for l in text.split("\n")]
    lines = [l for l in lines if l.strip() and not l.strip().startswith(("#", ";"))]
    cells = {}
    if any(l.strip().startswith("x") and "=" in l for l in lines) or any("$" in l for l in lines):
        body = "".join(l.strip() for l in lines if not (l.strip().startswith("x") and "=" in l))
        r = c = 0
        run = ""
        for ch in body:
            if ch.isdigit():
                run += ch
                continue
            n = int(run) if run else 1
            run = ""
            if ch == "!":
                break
            if ch == "$":
                r += n
                c = 0
                continue
            st = 0 if ch in "b." else 1 if ch == "o" else ord(ch) - ord("A") + 1
            for _ in range(n):
                cells[(r, c)] = LH[st]
                c += 1
    else:
        for r, l in enumerate(lines):
            for c, ch in enumerate(l.strip()):
                if ch == "!":
                    return cells
                cells[(r, c)] = CHARS.get(ch, "unknown")
            if "!" in l:
                break
    return cells


def unchecked_cells(path):
    """Cells of a config's pattern drift doesn't check for stability: dr2's
    '2' '3' '4' characters and no-check regions (pattern-relative)."""
    _, regions = read_config(path)
    text, cells = open(path).read().split("\n"), set()
    block, inside = [], False
    for line in text:
        if inside:
            block.append(line)
            if "!" in line:
                break
        elif line.strip().rstrip(":= ") == "pattern" and line.strip().endswith((":", "=")):
            inside = True
    if block and not any("$" in l or l.strip().startswith("x") for l in block):
        r = 0
        for l in block:
            if not l.strip() or l.strip().startswith(("#", ";")):
                continue
            for c, ch in enumerate(l.strip()):
                if ch == "!":
                    break
                if ch in "234":
                    cells.add((r, c))
            r += 1
    return cells, [g for k, g in regions if k == "no-check"]


def read_config(path):
    text = open(path).read().split("\n")
    regions, pattern, i = [], None, 0
    base = os.path.dirname(os.path.abspath(path))
    while i < len(text):
        l = text[i].strip()
        i += 1
        if not l or l.startswith("#"):
            continue
        l = re.sub(r"\s+#.*$", "", l)
        if l.rstrip(":= ") == "pattern" and (l.endswith(":") or l.endswith("=")):
            block = []
            while i < len(text):
                block.append(text[i])
                i += 1
                if "!" in block[-1]:
                    break
            pattern = "\n".join(block)
            continue
        m = re.match(r"([a-z-]+)\s*=?\s*(.*)$", l)
        if not m:
            continue
        key, val = m.group(1), m.group(2)
        if key in ("clear", "no-change", "no-count", "no-check", "must-reach"):
            regions.append((key, parse_region(val)))
        elif key == "pattern":
            pattern = open(os.path.join(base, val)).read()
    return load_pattern(pattern), regions
