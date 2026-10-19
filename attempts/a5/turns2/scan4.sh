#!/bin/zsh
# Connector searches with a radius-3 connector zone (the straight control is
# found there; wider zones don't finish). One line per run in scan4.log.
D=../../../drift/drift
export ZONE=${ZONE:-3}
: > scan4.log
run() {
  n=$1; shift
  python3 make_connector2.py "$@" > $n.cfg 2>/dev/null || { rm -f $n.cfg; return; }
  $D $n.cfg --quiet --max-steps 3000000000 --jsonl $n.jsonl > $n.txt 2>&1
  echo "$n: $(grep -E '^Search' $n.txt | sed 's/ after.*//') found: $(grep -c '^\*\*\*\*\*' $n.txt) $(grep -o 'Highest generation reached: [0-9]*' $n.txt | sed 's/Highest generation reached/max gen/')" >> scan4.log
  [ -s $n.jsonl ] || rm -f $n.jsonl
}
run ctl-2c3 2c3 straight 7 0
run ctl-5c11 5c11 straight 9 0
for w in 2c3 5c11; do
  for s in right left; do for A in 3 4 5 6 7 8 9 10 11; do for B in -3 -2 -1 0 1 2 3 4 5; do
    run $w-$s-$A-$B $w $s $A $B; done; done; done
  if [ $w = 2c3 ]; then BS=(7 8 9 10 11); else BS=(12 13 14 15 16); fi
  for s in reflect-right reflect-left; do for A in -3 -2 -1 0 1 2 3 4; do for B in $BS; do
    run $w-$s-$A-$B $w $s $A $B; done; done; done
done
echo done >> scan4.log
