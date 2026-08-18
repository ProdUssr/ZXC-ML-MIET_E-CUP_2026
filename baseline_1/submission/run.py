import time

_T0 = time.monotonic()

import logging
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from contracts import RuntimeContext
from deadline import DeadlineManager
from io_utils import (
    initialize_output,
    parse_args,
    read_items,
    resource_root_for_csv,
)
from orchestrator import DefaultPolicy, Orchestrator
from predictors import REGISTRY
from router import Router
from settings import load_settings
from sink import ResultSink, repair_invalid_rows
from telemetry import Telemetry

LOG = logging.getLogger("phase0")


def main() -> int:
    args = parse_args()
    telemetry = None
    items = []
    sink = None
    router = None
    deadline = None
    defaults = None
    try:
        # A header is evaluator-visible before config, input, or optional stages.
        initialize_output(args.output_path)
        logging.basicConfig(
            level=logging.WARNING,
            stream=sys.stderr,
            format="%(levelname)s %(message)s",
        )
        telemetry = Telemetry()
        settings = load_settings(args.config or ROOT / "config.json")
        read_started = time.perf_counter()
        items = read_items(args.test_data_path)
        telemetry.timing("read", (time.perf_counter() - read_started) * 1000)

        defaults = DefaultPolicy(settings)
        sink = ResultSink(
            args.output_path, items, defaults.result_for_item, telemetry=telemetry
        )
        flush_started = time.perf_counter()
        sink.flush()
        telemetry.timing(
            "initial_flush", (time.perf_counter() - flush_started) * 1000
        )

        deadline = DeadlineManager(_T0, len(items), settings.deadline)
        context = RuntimeContext(ROOT, settings, telemetry)
        router = Router(settings.stages, REGISTRY)
        init_started = time.perf_counter()
        router.load(context)
        telemetry.timing("init", (time.perf_counter() - init_started) * 1000)
        deadline.start_processing(settings.batch_size)
        orchestrator = Orchestrator(
            router,
            deadline,
            sink,
            telemetry,
            settings,
            resource_root_for_csv(args.test_data_path),
        )
        orchestrator.run(items)
    except BaseException:
        LOG.exception("pipeline failed; valid output retained")
    finally:
        if router is not None:
            try:
                router.close()
            except BaseException:
                LOG.exception("router close failed")
        if sink is not None and defaults is not None:
            try:
                sink.finalize()
                repair_invalid_rows(
                    args.output_path, items, defaults.result_for_item
                )
            except BaseException:
                LOG.exception("final output repair failed")
        else:
            try:
                initialize_output(args.output_path)
            except BaseException:
                LOG.exception("could not recreate output header")
        if telemetry is None:
            telemetry = Telemetry()
        if deadline is not None:
            telemetry.set("deadline", deadline.summary())
        telemetry.set("sink_flushes", sink.flush_count if sink else 0)
        telemetry.timing("run_total", (time.monotonic() - _T0) * 1000)
        try:
            telemetry.dump()
        except BaseException:
            pass
    return 0


if __name__ == "__main__":
    exit_code = main()
    sys.stdout.flush()
    sys.stderr.flush()
    os._exit(exit_code)
