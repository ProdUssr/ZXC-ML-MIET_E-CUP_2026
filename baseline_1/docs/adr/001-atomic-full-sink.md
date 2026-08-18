# ADR 001: atomic full-file result sink

`ResultSink.flush()` rewrites all rows to a temporary file and atomically replaces the target. With only about 3,800 rows this costs roughly one megabyte per flush, while guaranteeing a complete, ordered and valid output at every observable instant, including a hard process kill. Out-of-order model batches therefore need no positional-prefix assumption.

Prediction batch size and durability cadence are independent. The orchestrator
flushes only after `flush_interval_sec` has elapsed and finalization always
performs one last snapshot. Thus a future VLM batch size of 8 does not turn 500
batches into 500 full-file rewrites; the configured five-second cadence keeps
the I/O cost proportional to run duration.
