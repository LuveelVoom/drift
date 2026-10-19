#!/bin/zsh
# Four drifter searches in one rule. Usage: batch.sh RULE DIR
RULE=$1; DIR=$2; cd $DIR
D=../../drift/drift
KR=../../drift/knownrotors
cat > spark.cfg <<C
rule = $RULE
known-rotors = $KR
max-changed = 6
size = 4x4
skip = fizzle, stable
min-period = 3
no-pics
pattern:
x = 1, y = 1, rule = LifeHistory
C!
C
cat > sparky.cfg <<C
rule = $RULE
known-rotors = $KR
max-changed = 8
size = 5x5
clear = r -60 -60 -1 60
must-reach = r -60 -60 -1 60
skip = fizzle, stable
min-period = 3
per-rotor = 5
no-pics
pattern:
x = 1, y = 1, rule = LifeHistory
C!
C
cat > signals.cfg <<C
rule = $RULE
max-changed = 6
size = 4x4
margin = 50
max-gen = 80
skip = oscillator, fizzle, stable
per-rotor = 3
no-pics
pattern:
x = 1, y = 1, rule = LifeHistory
C!
C
python3 ../a5/make_converter.py 9 9 10 6x6 | sed "s#^rule = .*#rule = $RULE#" > converter.cfg
for n in spark sparky signals converter; do
  $D $n.cfg --max-steps 12000000000 --quiet --jsonl $n.jsonl > $n.txt 2>&1
  echo "$n: $(grep -E '^Search' $n.txt | sed 's/ (.*//') | $(grep -E '^Found' $n.txt | sed 's/; printed.*//') | printed $(grep -c '^\*\*\*\*\*' $n.txt)" >> batch.log
done
echo done >> batch.log
