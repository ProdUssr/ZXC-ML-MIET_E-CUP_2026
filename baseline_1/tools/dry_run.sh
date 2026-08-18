#!/usr/bin/env sh
set -eu
root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
tmp=${TMPDIR:-/tmp}/ecup-phase0-$$
image=odsai/ecup26-quality-baseline:1.0
mkdir -p "$tmp/images"
trap 'rm -rf "$tmp"' EXIT

mode=process
if command -v docker >/dev/null 2>&1 \
   && docker info >/dev/null 2>&1 \
   && docker image inspect "$image" >/dev/null 2>&1; then
  mode=docker-network-none
fi

run_submission() {
  input=$1
  output=$2
  log=$3
  if [ "$mode" = docker-network-none ]; then
    cp "$input" "$tmp/container-input.csv"
    docker run --rm --network none --cpus 20 --memory 100g \
      -v "$root/submission:/work:ro" -v "$tmp:/data" -w /work \
      "$image" python -u run.py -i /data/container-input.csv -o /data/container-output.csv \
      2>"$log"
    cp "$tmp/container-output.csv" "$output"
  else
    python "$root/submission/run.py" -i "$input" -o "$output" 2>"$log"
  fi
}

for n in 10 1600 4000; do
  python "$root/tools/make_synthetic.py" -n "$n" -o "$tmp/input.csv"
  run_submission "$tmp/input.csv" "$tmp/out.csv" "$tmp/run_$n.log"
  python "$root/tests/validate_csv.py" "$tmp/input.csv" "$tmp/out.csv"
  python - "$tmp/run_$n.log" <<'PY'
import json, pathlib, sys
summary=json.loads(pathlib.Path(sys.argv[1]).read_text(encoding='utf-8',errors='replace').splitlines()[-1])['run_summary']
print('init_sec=%.6f predict_sec=%.6f' % (summary['timings_ms'].get('init',0)/1000, sum(v for k,v in summary['timings_ms'].items() if k.startswith('predict:'))/1000))
PY
done

run_submission "$root/tests/edge_cases.csv" "$tmp/edge_out.csv" "$tmp/edge.log"
python "$root/tests/validate_csv.py" "$root/tests/edge_cases.csv" "$tmp/edge_out.csv"
echo "dry run passed mode=$mode"
