#!/bin/zsh
# Run every search in this folder (each finishes its own results).
for f in tspark-boxed tspark tspark-converter glider glider-converter; do
  echo "===== $f"
  ../drift $f.cfg --quiet
done
