#!/usr/bin/env python3
"""Compare `drift --classic` with the original dr2.c on the inputs in
tests/classic/. Both programs are deterministic, so their outcome blocks must
match one for one. Long searches are cut off after a time limit and the common
prefix is compared.

dr2.c appends a stray (0,0) cell to every neighbour list, so its call counter
runs slightly ahead; the "computecellorbackup calls" progress blocks are
therefore ignored.

Usage: tests/regress.py [--dr2 PATH] [--seconds N] [NAME ...]
"""
import argparse
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

# Inputs dr2.c can't read, checked against an equivalent input instead.
ORACLE = {"life-as-int": "stillater"}

START = re.compile(r"^(\*\*\*\*\*|maxgenreached|computecellorbackup calls|Too many 2s|"
                   r"chgcount\[|5c/9 continues|No more objects)")


def run(cmd, stdin_path, seconds, cwd):
    with open(stdin_path, "rb") as f:
        try:
            p = subprocess.run(cmd, stdin=f, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                               timeout=seconds, cwd=cwd)
            return p.stdout.decode("latin-1"), True
        except subprocess.TimeoutExpired as e:
            return (e.stdout or b"").decode("latin-1"), False


def blocks(text):
    lines = text.split("\n")
    try:
        lines = lines[lines.index("Beginning search") + 1:]
    except ValueError:
        return []
    out, cur = [], None
    for line in lines:
        if START.match(line):
            if cur is not None:
                out.append(cur)
            cur = [line]
        elif cur is not None:
            cur.append(line)
    if cur is not None:
        out.append(cur)
    return ["\n".join(b).rstrip("\n") for b in out if not b[0].startswith("computecellorbackup")]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dr2", default=os.path.join(ROOT, "..", "ref", "dr2fixed"))
    ap.add_argument("--seconds", type=float, default=10)
    ap.add_argument("names", nargs="*")
    a = ap.parse_args()
    drift = os.path.join(ROOT, "drift")
    refdir = os.path.dirname(os.path.abspath(a.dr2))
    names = a.names or sorted(f[:-3] for f in os.listdir(os.path.join(HERE, "classic"))
                              if f.endswith(".in"))
    bad = 0
    for name in names:
        inp = os.path.join(HERE, "classic", name + ".in")
        oracle = os.path.join(HERE, "classic", ORACLE.get(name, name) + ".in")
        ref, ref_done = run([os.path.abspath(a.dr2)], oracle, a.seconds, refdir)
        new, new_done = run([drift, "--classic"], inp, a.seconds, refdir)
        rb, nb = blocks(ref), blocks(new)
        # A run cut off by the time limit may end in a partial block.
        if not ref_done and rb:
            rb = rb[:-1]
        if not new_done and nb:
            nb = nb[:-1]
        n = min(len(rb), len(nb))
        if ref_done and new_done:
            n = max(len(rb), len(nb))
        mismatch = next((i for i in range(n) if i >= len(rb) or i >= len(nb) or rb[i] != nb[i]), None)
        status = "ok" if mismatch is None and n > 0 else "FAIL"
        if n == 0:
            status = "FAIL (no outcomes to compare)"
        note = "complete" if ref_done and new_done else "prefix"
        outcomes = sum(1 for b in rb[:n] if b.startswith("*****"))
        print(f"{name:18s} {status:4s}  {n} blocks ({outcomes} outcomes) compared, {note}")
        if mismatch is not None:
            bad += 1
            print("  first difference at block", mismatch)
            print("  --- dr2.c\n" + "\n".join("  " + l for l in (rb[mismatch] if mismatch < len(rb) else "<none>").split("\n")[:12]))
            print("  --- drift\n" + "\n".join("  " + l for l in (nb[mismatch] if mismatch < len(nb) else "<none>").split("\n")[:12]))
        elif n == 0:
            bad += 1
    print("all identical" if not bad else f"{bad} failing")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
