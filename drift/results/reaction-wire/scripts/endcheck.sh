#!/bin/zsh
# endcheck.sh NAME  (e.g. end-A-lead12-r4): finish a snapshot, then clean-output test
S=${0:A:h}; D="/Users/leo/Desktop/Life tools/Vibecoded life tools/drift/drift/drift"
cp "$D/results/wire-end/$1-results.jsonl" "$S/snap-$1.jsonl"
cd "$D" && python3 tools/finish.py "results/wire-end/$1.cfg" --jsonl "$S/snap-$1.jsonl" --out "$S/$1-finished.txt" --all --min-output-dist 10 --jobs 2 >/dev/null 2>&1
cd "$S" && python3 - "$1" <<'PY'
import sys
exec(open('sparkdist.py').read())
txt=open(sys.argv[1]+'-finished.txt').read()
n=0;good=0
for m in re.finditer(r'#C ((?:spark converter|catalyst)[^\n]*)\n(x = [^\n]*\n(?:[^#\n][^\n]*\n?)+)',txt):
    n+=1; p=C.parse_rle(m.group(2)); g0=cells(p)
    best,still,out=weak_spark(g0,200); cl=clean_outputs(still,out)
    if cl:
        good+=1; open(f'{sys.argv[1]}-clean{good}.rle','w').write(p.to_rle()); print('CLEAN SPARK:',m.group(1)[:70],'clean cells',len(cl))
print(sys.argv[1],'checked',n,'patterns,',good,'with a clean output spark')
PY
