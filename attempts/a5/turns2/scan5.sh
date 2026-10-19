#!/bin/zsh
# 5c/11 wire: control, turns and reflectors with a radius-7 connector zone.
D=../../../drift/drift
export ZONE=7
: > scan5.log
run() {
  n=$1; shift
  python3 make_connector2.py "$@" 10 6x6 > $n.cfg 2>/dev/null || { rm -f $n.cfg; return; }
  $D $n.cfg --quiet --max-steps 1500000000 --jsonl $n.jsonl > $n.txt 2>&1
  echo "$n: $(grep -E '^Search' $n.txt | sed 's/ after.*//') found: $(grep -c '^\*\*\*\*\*' $n.txt) $(grep -o 'Highest generation reached: [0-9]*' $n.txt | sed 's/Highest generation reached/max gen/')" >> scan5.log
  [ -s $n.jsonl ] || rm -f $n.jsonl
}
run ctl-5c11 5c11 straight 3 0
for s in right left; do for A in 0 1 2 3 4 5 6 7 8 9; do for B in -4 -3 -2 -1 0 1 2 3 4 5 6; do
  run 5c11-$s-$A-$B 5c11 $s $A $B; done; done; done
for s in reflect-right reflect-left; do for A in -3 -2 -1 0 1 2 3 4; do for B in 12 13 14 15 16; do
  run 5c11-$s-$A-$B 5c11 $s $A $B; done; done; done
echo done >> scan5.log
