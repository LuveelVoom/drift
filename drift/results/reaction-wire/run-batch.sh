#!/bin/zsh
# usage: run-batch.sh CAP_SECONDS cfg... ; runs two at a time, 5 threads each
cd "${0:A:h}/../.."
cap=$1; shift
run1() { ./drift "$1" --threads 5 --max-time $cap --checkpoint "${1%.cfg}.ckpt" --no-finish --no-pics --progress 120 > "${1%.cfg}.log" 2>&1 }
while (( $# > 0 )); do
  a=$1; shift; b=${1:-}; [[ -n $b ]] && shift
  run1 $a & ; [[ -n $b ]] && { run1 $b & }
  wait
done
echo batch done
