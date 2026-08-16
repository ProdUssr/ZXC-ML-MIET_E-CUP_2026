#!/usr/bin/env sh
set -eu
root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
test -f "$root/submission/metadata.json"
python - "$root" <<'PY'
import json, pathlib, sys, zipfile
root = pathlib.Path(sys.argv[1]); source = root / 'submission'; output = root / 'submission.zip'
meta = json.loads((source / 'metadata.json').read_text(encoding='utf-8'))
assert meta['entry_point'] == 'python -u run.py'
with zipfile.ZipFile(output, 'w', zipfile.ZIP_DEFLATED) as z:
    for p in source.rglob('*'):
        assert '.git' not in p.parts and '__pycache__' not in p.parts
        if p.is_file(): z.write(p, p.relative_to(source))
assert output.stat().st_size < 5 * 1024**3
print(output)
PY
