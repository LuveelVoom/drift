import time, threading
from driftlib import OFFS
from pysat.solvers import Glucose4
from pysat.card import ITotalizer

def min_complete(cells, table, margin, empty, seconds=60):
    rs = [r for r, c in cells]; cs = [c for r, c in cells]
    r0, r1, c0, c1 = min(rs) - margin, max(rs) + margin, min(cs) - margin, max(cs) + margin
    var = {}
    for r in range(r0, r1 + 1):
        for c in range(c0, c1 + 1):
            if not (empty((r, c)) and cells.get((r, c)) not in (1, 4)):
                var[(r, c)] = len(var) + 1
    s = Glucose4()
    for p, st in cells.items():
        if p in var:
            s.add_clause([var[p]] if st in (1, 4) else [-var[p]])
    for r in range(r0 - 1, r1 + 2):
        for c in range(c0 - 1, c1 + 2):
            nb = [var.get((r + dr, c + dc)) for dr, dc in OFFS]
            if all(v is None for v in nb):
                continue
            for w in range(512):
                bits = [(w >> (8 - k)) & 1 for k in range(9)]
                if table[w] == bool(bits[4]):
                    continue
                clause, possible = [], True
                for v, b in zip(nb, bits):
                    if v is None:
                        if b: possible = False; break
                    else:
                        clause.append(-v if b else v)
                if possible:
                    s.add_clause(clause)
    free = [v for p, v in var.items() if p not in cells]
    top = len(var) + 1
    tot = ITotalizer(lits=free, ubound=len(free), top_id=top)
    s.append_formula(tot.cnf.clauses)
    best, assume = None, []
    deadline = time.time() + seconds
    while time.time() < deadline:
        t = threading.Timer(deadline - time.time(), s.interrupt); t.start()
        ok = s.solve_limited(assumptions=assume, expect_interrupt=True)
        t.cancel(); s.clear_interrupt()
        if not ok: break
        m = set(x for x in s.get_model() if x > 0)
        best = {p for p, v in var.items() if v in m}
        k = sum(1 for p, v in var.items() if p not in cells and v in m) - 1
        print("  cap cells", k + 1, flush=True)
        if k < 0: break
        assume = [-tot.rhs[k]]
    return best
