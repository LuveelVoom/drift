#!/usr/bin/env python3
"""Smallest stator for a known reaction.

Given the generations of a working pattern, the "active" cells (those that
don't stay constant) keep their exact values in every generation. Every other
cell in a box around them becomes a free stator cell that must stay constant,
and a SAT solver looks for the fewest live stator cells. Outside the box
everything is dead.

  cyclic=True : states are one period of an oscillator (the last state steps
                back to the first);
  cyclic=False: states run from gen 0 until the reaction is over (the last
                state must be stable), e.g. a spark converter.
"""
import threading
import time

from pysat.card import ITotalizer
from pysat.solvers import Glucose4

OFFS = [(-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 0), (0, 1), (1, -1), (1, 0), (1, 1)]
WEIGHT = [256, 128, 64, 32, 16, 8, 4, 2, 1]


def minimize(states, table, cyclic, margin=4, seconds=20, empty=None):
    """states: list of sets of live cells. empty(p): True for cells that must stay dead.
    Returns (live cells of states[0] with the smallest stator found, population)
    or None if no stator fits in the box."""
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

    steps = [(t, (t + 1) % T) for t in range(T)] if cyclic else \
        [(t, t + 1) for t in range(T - 1)] + [(T - 1, T - 1)]
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
