# Pending task (asked 2026-11-16, do AFTER the reaction→wire question)

User request: investigate `drift/drift/wireset.txt` (copy also in
`findings/B3-S23-a5/wireset.txt`; scratch copy `ws.rle` here). It has two
"wA → weak spark" output converters (Converters row, 3rd and 4th items:
white wA ending in a green/magenta/pink catalyst cluster at the output (orange) end).
Question: how would you find more wire-to-weak-spark reactions?

Notes so far:
- Rule B3/S23-a5. Super states: white=1, wire bodies 17/11/15/19, input end 25 (yellow),
  output end 13 (orange), labels 4.
- Signal runs from the 25 end to the 13 end; the drawn wires are pre-fired
  (the stable idle wire = drawn wire run to stability, differs by 1 cell at the input).
- Rendered overview: full.png (img.py renders any region).
- Relevant project tools: drift (spark/catalyst search), tools/sparkconv.py,
  convanalyze.py, wirecheck.py, wirebuild.py, SPARK-CONVERTERS-PLAN.md.
- Idea to evaluate: treat the output end of wA (signal arriving) as a fixed
  "spark source" and run a drift catalyst search around it (unknown background
  next to the wire end, signal as the perturbation, fizzle + output-dist filter),
  or brute-force placements of known small still lifes/catalysts near the end.
