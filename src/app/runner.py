from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from src.app.cli import build_parser
from src.core.config import Config
from src.core.config_loader import load_config, register_strategies
from src.core.registry import registry
from src.app.output import to_html, to_png, to_svg, to_tikz
from src.formatters import format_strategy_summary
from src.render.console import print_banner, print_gantt, print_header, print_metrics
from src.reports import ReportExporter
from src.sim import EngineConfig, run_simulation
from src.sim.task_builder import build_tasks

RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"
GREEN = "\033[92m"
RED = "\033[91m"


def run_strategy(config: Config, strategy_name: str, start: float, end: float):
    tasks = build_tasks(config.tasks, start, end)
    sim_config = EngineConfig(
        start=start,
        end=end,
        strategy_name=strategy_name,
        num_processors=config.simulation.num_processors,
        preemptive=config.simulation.preemptive,
        strategy_params=config.simulation.params,
    )
    return run_simulation(tasks, sim_config)


def list_strategies(config: Config):
    cyan = "\033[96m"
    print(f"\n  {BOLD}Available strategies:{RESET}")
    for strategy in config.strategies:
        desc = strategy.description or f"type={strategy.type}"
        print(f"    {cyan}{strategy.name:<25}{RESET}  {DIM}{desc}{RESET}")
    print()


def run_app(args: argparse.Namespace) -> int:
    config_path = Path(args.config)
    if not config_path.exists():
        print(f"Error: Config file not found: {args.config}", file=sys.stderr)
        return 1

    try:
        config = load_config(args.config)
    except Exception as exc:
        print(f"Error loading config: {exc}", file=sys.stderr)
        return 1

    register_strategies(config, registry)
    if args.list_strategies:
        list_strategies(config)
        return 0

    strategy = args.strategy or config.simulation.strategy
    start = float(args.start) if args.start is not None else float(config.simulation.start)
    end = float(args.end) if args.end is not None else float(config.simulation.end)
    num_processors = int(config.simulation.num_processors)
    if end <= start:
        print(f"Error: end ({end}) must be greater than start ({start})", file=sys.stderr)
        return 1
    if num_processors < 1:
        print(f"Error: num_processors must be >= 1, got {num_processors}", file=sys.stderr)
        return 1

    print_banner()
    result = None

    if strategy == "all":
        results = {}
        for s in config.strategies:
            sname = s.name
            ok, msg = registry.validate(sname)
            if not ok:
                print(f"  {DIM}Skipping {sname}: {msg}{RESET}")
                continue
            try:
                result = run_strategy(config, sname, start, end)
                results[sname] = result
            except Exception as exc:
                print(f"  {RED}Error running {sname}: {exc}{RESET}")

        output_mode = args.output
        if output_mode in ("console", "all"):
            print(format_strategy_summary(results, args.width))
            print()
            for sname, result in results.items():
                print(f"\n  {BOLD}--- {sname} ---{RESET}")
                print_gantt(result, args.width)
                print_metrics(result, verbose=args.verbose)

        if output_mode in ("tikz", "all"):
            for sname, result in results.items():
                suffix = f"_{sname}" if len(results) > 1 else ""
                base = args.output_file or f"schedule{suffix}.tex"
                fname = os.path.join("output", base)
                to_tikz(result, sname, fname)
                print(f"  {GREEN}TikZ saved:{RESET} {fname}")
            if output_mode == "tikz":
                return 0

        if output_mode in ("png", "all"):
            for sname, result in results.items():
                suffix = f"_{sname}" if len(results) > 1 else ""
                base = args.output_file or f"schedule{suffix}.png"
                fname = os.path.join("output", base)
                try:
                    to_png(result, sname, fname)
                    print(f"  {GREEN}PNG saved:{RESET} {fname}")
                except ImportError as exc:
                    print(f"  {RED}{exc}{RESET}")
            if output_mode == "png":
                return 0
    else:
        ok, msg = registry.validate(strategy)
        if not ok:
            print(f"Error: {msg}", file=sys.stderr)
            return 1

        result = run_strategy(config, strategy, start, end)
        output_mode = args.output
        if output_mode in ("console", "all"):
            print_header(strategy, start, end)
            print()
            print_gantt(result, args.width)
            print_metrics(result, verbose=args.verbose)

        if output_mode == "tikz":
            fname = os.path.join("output", args.output_file or "schedule.tex")
            to_tikz(result, strategy, fname)
            print(f"  {GREEN}TikZ saved:{RESET} {fname}")

        if output_mode == "png":
            fname = os.path.join("output", args.output_file or "schedule.png")
            try:
                to_png(result, strategy, fname)
                print(f"  {GREEN}PNG saved:{RESET} {fname}")
            except ImportError as exc:
                print(f"  {RED}{exc}{RESET}")

    if args.export_json and result is not None:
        ReportExporter.save_json({strategy: result}, args.export_json)
        print(f"  {GREEN}JSON saved:{RESET} {args.export_json}")

    if args.export_csv and result is not None:
        ReportExporter.save_csv({strategy: result}, args.export_csv)
        print(f"  {GREEN}CSV saved:{RESET} {args.export_csv}")

    if args.export_svg and result is not None:
        to_svg(result, strategy, args.export_svg)
        print(f"  {GREEN}SVG saved:{RESET} {args.export_svg}")

    if args.export_html and result is not None:
        to_html(result, strategy, args.export_html)
        print(f"  {GREEN}HTML saved:{RESET} {args.export_html}")

    if args.debug and result is not None:
        print(f"\n  {DIM}=== DEBUG INFO ==={RESET}")
        print(f"  {DIM}Events: {len(result.events)}")
        print(f"  {DIM}Completed: {result.completed_tasks}")
        print(f"  {DIM}Missed: {result.missed_deadlines}")
        print(f"  {DIM}Response times: {result.task_response_times}")
        print(f"  {DIM}Wait times: {result.task_wait_times}{RESET}")

    print()
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return run_app(args)


if __name__ == "__main__":
    raise SystemExit(main())

