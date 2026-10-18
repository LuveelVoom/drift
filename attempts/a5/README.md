# B3/S23-a5: single-spark oscillators

`spark.cfg`: one cell switched on in an unknown background, at most 6 changed
cells in 4×4, period ≥ 4. The run was stopped after 3·10⁹ steps (22 s, 14 threads):

    ../../drift/drift spark.cfg --max-changed 6 --size 4x4 --max-steps 3000000000 --no-rle --jsonl fixed.jsonl
    python3 ../../drift/tests/complete.py fixed.jsonl --rule "$(../../drift/drift --rule B3/S23-a5 --show-rule | sed -n 's/^MAP: *//p')" --best oscillators.txt --minimize

`oscillators.txt` lists 180 distinct rotors (p4–p15) as complete, minimised
patterns in B3/S23-a5. Each was re-simulated by an independent implementation
of the rule. "Life rotor" means the rotor's descriptor matches a Life
oscillator in `knownrotors`.
