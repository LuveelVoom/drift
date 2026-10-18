#!/usr/bin/env python3
"""Speed of drift vs dr2.c on identical work.

Both programs print the same outcome sequence for a classic input (see
regress.py), so we time when each prints its K-th outcome, for the largest K
both reach within the time limit. The ratio of those times is the speedup.

Usage: tests/bench.py [--seconds N] [NAME ...]   (inputs in tests/classic/)
"""
import argparse
import os
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from regress import ROOT, HERE, ORACLE  # noqa: E402


def stamps(cmd, inp, seconds, cwd):
    """Times (since start) at which each outcome line was printed."""
    t0 = time.time()
    with open(inp, "rb") as f:
        p = subprocess.Popen(cmd, stdin=f, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, cwd=cwd)
    out = []
    os.set_blocking(p.stdout.fileno(), False)
    buf = b""
    while True:
        now = time.time() - t0
        if now > seconds:
            p.kill()
            break
        chunk = p.stdout.read()
        if chunk:
            buf += chunk
            *lines, buf = buf.split(b"\n")
            out.extend(now for l in lines if l.startswith(b"*****"))
        elif p.poll() is not None:
            break
        else:
            time.sleep(0.002)
    p.wait()
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dr2", default=os.path.join(ROOT, "..", "ref", "dr2fixed"))
    ap.add_argument("--seconds", type=float, default=5)
    ap.add_argument("names", nargs="*", default=["sokwe-rot90", "billiard-rot180", "stillater-big"])
    a = ap.parse_args()
    drift = os.path.join(ROOT, "drift")
    refdir = os.path.dirname(os.path.abspath(a.dr2))
    for name in a.names:
        inp = os.path.join(HERE, "classic", name + ".in")
        if not os.path.exists(inp):
            inp = os.path.join(HERE, "bench", name + ".in")
        oracle = os.path.join(os.path.dirname(inp), ORACLE.get(name, name) + ".in")
        ref = stamps([os.path.abspath(a.dr2)], oracle, a.seconds, refdir)
        new = stamps([drift, "--classic"], inp, a.seconds, refdir)
        k = min(len(ref), len(new))
        if k == 0:
            print(f"{name:18s} no outcomes within {a.seconds:g}s")
            continue
        print(f"{name:18s} outcome #{k}: dr2 {ref[k-1]:.2f}s, drift {new[k-1]:.2f}s  "
              f"-> {ref[k-1] / max(new[k-1], 1e-3):.2f}x")


if __name__ == "__main__":
    main()
