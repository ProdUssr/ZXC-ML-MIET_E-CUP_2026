# E-CUP 2026 Quality — Phase 0 baseline

The baseline is an offline, CPU-only predictor cascade. It creates the output
header before reading input, then writes a complete atomic `id,result` snapshot
before optional predictors start. Input order is preserved even when
predictions arrive out of order.

```sh
python -m unittest discover -s tests
python tools/make_synthetic.py -n 10 -o /tmp/test.csv
python submission/run.py -i /tmp/test.csv -o /tmp/submit.csv
```

Runtime configuration is the typed JSON file `submission/config.json`. To add a
predictor, create one registered module under `submission/predictors/` and name
it in `stages`; `run.py`, the router, orchestrator, and sink do not need edits.
The `embedding.py` and `vlm.py` modules are Phase 1 contract placeholders.

Rule code emits an evidence signature rather than assigning its direction.
`submission/calibration.json` maps that signature to `p_regulated`; reproduce
the group-safe train-only fit with `python train/fit_calibration.py`. The
shipped table records `fit_rows` and `split_id`; holdout results live separately
in `train/metrics.json`. Category thresholds are fitted on train only.

Build the evaluator payload with `sh tools/build_submission.sh`. On a POSIX
host, `sh tools/dry_run.sh` validates N=10/1600/4000 and edge cases. See
`docs/phase0_report.md` for metrics, timings, architecture seams, and residual
environment risks. The organiser mapping is fixed as `label=1 -> not ban`.
