# B3/S23-a5: single-spark oscillators

`spark.cfg`: one cell switched on in an unknown background, at most 6 changed
cells in 4×4, period ≥ 4. The run was stopped after 3·10⁹ steps (22 s, 14 threads):

    ../../drift/drift spark.cfg --max-changed 6 --size 4x4 --max-steps 3000000000 --no-rle --jsonl fixed.jsonl
    python3 ../../drift/tests/complete.py fixed.jsonl --rule "$(../../drift/drift --rule B3/S23-a5 --show-rule | sed -n 's/^MAP: *//p')" --best oscillators.txt --minimize

`oscillators.txt` lists 180 distinct rotors (p4–p15) as complete, minimised
patterns in B3/S23-a5. Each was re-simulated by an independent implementation
of the rule. "Life rotor" means the rotor's descriptor matches a Life
oscillator in `knownrotors`.

## Spark converters

`make_converter.py H W C SIZE` writes a config:

- the input spark is at (0,0), in empty space;
- the still life is confined to an H×W box to its right;
- some cell just outside the box, at least 4 cells from the input, must come
  alive;
- the still life must then recover.

`conv-9x9-c10-6x6.cfg` (0.3 s) found one 18-cell still life that works with
two input positions. `converters.txt` has both as minimised patterns, checked
with the independent rule implementation. The output spark appears at gen 5,
3 cells up and 3 right of the input, and the still life recovers at gen 7.
The reaction also briefly puts cells out on the input side.
