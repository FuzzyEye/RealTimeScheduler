import argparse
import os
import yaml
import sys
from pathlib import Path
from typing import List

from src.task import Task
from src.config import Config, ConfigTask, ConfigSimulation, ConfigStrategy
from src.simulator import SimulationEngine
from src.formatters import format_metrics, format_strategy_summary
from src.registry import registry
from src.plugins import load_plugin
from src.output import to_png, to_tikz

RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"
GREEN = "\033[92m"
RED = "\033[91m"
CYAN = "\033[96m"
YELLOW = "\033[93m"


def load_config(path: str) -> Config:
    with open(path, "r") as f:
        raw = yaml.safe_load(f)

    tasks = []
    for t in raw.get("tasks", []):
        tasks.append(ConfigTask(
            name=t["name"],
            execution_time=t["execution_time"],
            period=t.get("period"),
            deadline=t.get("deadline"),
            priority=t.get("priority", 0),
            arrival_time=t.get("arrival_time", 0.0),
            value=t.get("value"),
        ))

    sim = raw.get("simulation", {})
    simulation = ConfigSimulation(
        start=float(sim.get("start", 0.0)),
        end=float(sim.get("end", 10.0)),
        strategy=sim.get("strategy", "edf"),
        num_processors=int(sim.get("num_processors", 1)),
        params=sim.get("params", {}),
    )

    strategies = []
    for s in raw.get("strategies", []):
        strategies.append(ConfigStrategy(
            name=s["name"],
            type=s["type"],
            description=s.get("description", ""),
            selector=s.get("selector"),
            fallback=s.get("fallback"),
            priority_key=s.get("priority_key"),
            condition=s.get("condition"),
            true_branch=s.get("true_branch"),
            false_branch=s.get("false_branch"),
            params=s.get("params", {}),
            module=s.get("module"),
            class_name=s.get("class_name"),
        ))

    return Config(tasks=tasks, simulation=simulation, strategies=strategies)


def build_tasks(config_tasks: List[ConfigTask], start: float, end: float) -> List[Task]:
    result: List[Task] = []
    for ct in config_tasks:
        if ct.period is not None and ct.period > 0:
            EPS = 1e-9
            num_instances = int((end - start - EPS) / ct.period) + 1
            num_instances = max(0, num_instances)
            for i in range(num_instances):
                arr = ct.arrival_time + i * ct.period
                if arr >= end:
                    break
                task = Task(
                    name=ct.name,
                    execution_time=ct.execution_time,
                    period=ct.period,
                    deadline=ct.deadline,
                    priority=ct.priority,
                    arrival_time=arr,
                    instance_id=i,
                    value=ct.value,
                )
                result.append(task)
        else:
            task = Task(
                name=ct.name,
                execution_time=ct.execution_time,
                period=None,
                deadline=ct.deadline,
                priority=ct.priority,
                arrival_time=ct.arrival_time,
                instance_id=0,
                value=ct.value,
            )
            result.append(task)
    return result


def run_strategy(config: Config, strategy_name: str, start: float, end: float, num_processors: int = 1):
    tasks = build_tasks(config.tasks, start, end)

    sim = SimulationEngine(
        tasks=tasks,
        start=start,
        end=end,
        strategy_name=strategy_name,
        strategy_params=config.simulation.params,
        num_processors=num_processors,
    )
    result = sim.run()
    return result


def list_strategies(config: Config):
    print(f"\n  {BOLD}Available strategies:{RESET}")
    for s in config.strategies:
        desc = s.description or f"type={s.type}"
        print(f"    {CYAN}{s.name:<25}{RESET}  {DIM}{desc}{RESET}")
    print()


def print_banner():
    print(f"\n  {BOLD}{'=' * 60}{RESET}")
    print(f"  {BOLD}       AutoScheduler — Real-Time Scheduling Simulator       {RESET}")
    print(f"  {BOLD}{'=' * 60}{RESET}\n")


def print_header(strategy_name: str, start: float, end: float, num_processors: int = 1):
    proc_str = f"  {BOLD}Processors:{RESET} {num_processors}"
    print(f"  {BOLD}Strategy:{RESET} {CYAN}{strategy_name}{RESET}  {BOLD}Window:{RESET} {start:.2f} → {end:.2f}{proc_str}")
    print(f"  {DIM}{'-' * 60}{RESET}")


def print_gantt_simple(result, max_width: int = 70, num_processors: int = 1):
    schedule_events = []
    running = {}
    seg_start = {}

    for e in sorted(result.events, key=lambda x: x.time):
        if e.event_type.value == "schedule":
            proc = 0
            details = getattr(e, "details", "") or ""
            if "P" in details:
                try:
                    proc = int(details.split("P")[1].split()[0]) - 1
                except (IndexError, ValueError):
                    proc = 0
            running[proc] = e.task_name
            seg_start[proc] = e.time
        elif e.event_type.value in ("complete", "preempt", "quantum_expire"):
            for proc in list(running.keys()):
                schedule_events.append((seg_start[proc], e.time, running[proc], proc))
                del running[proc]
                del seg_start[proc]

    for proc, task in running.items():
        schedule_events.append((seg_start[proc], result.total_time, task, proc))

    if not schedule_events:
        print(f"  {DIM}(no execution segments){RESET}")
        return

    total = result.total_time
    if total <= 0:
        total = 1.0

    width = max_width - 4
    scale = width / total

    ANSI_COLORS = [
        "\033[91m", "\033[92m", "\033[93m", "\033[94m",
        "\033[95m", "\033[96m", "\033[97m",
    ]
    name_to_color = {}
    seen_names = []

    def get_color(name):
        if name not in name_to_color:
            name_to_color[name] = ANSI_COLORS[len(name_to_color) % len(ANSI_COLORS)]
            seen_names.append(name)
        return name_to_color[name]

    def draw_row(proc_events):
        spans = []
        cur = 0
        for start_t, end_t, task_name in proc_events:
            sc = max(0, min(int(start_t * scale), width))
            ec = max(sc, min(int(end_t * scale), width))
            if sc > cur:
                spans.append(("space", cur, sc))
            color = get_color(task_name)
            label = task_name[:max(0, ec - sc)]
            spans.append((color, sc, ec, label, task_name))
            cur = ec
        if cur < width:
            spans.append(("space", cur, width))
        return spans

    def print_spans(spans):
        parts = []
        for span in spans:
            if span[0] == "space":
                parts.append(" " * (span[2] - span[1]))
            else:
                color, sc, ec, label, _ = span
                bar = "─" * (ec - sc)
                if label:
                    pos = sc + (ec - sc - len(label)) // 2
                    bar = " " * (ec - sc)
                    bar = bar[:pos - sc] + label + bar[pos - sc + len(label):]
                parts.append(f"{color}{bar}{RESET}")
        print("  " + "".join(parts))

    def print_ruler_row(spans):
        ruler = [" "] * width
        num_ticks = min(width // 10, 20)
        if num_ticks == 0:
            num_ticks = 1
        for i in range(num_ticks + 1):
            col = int(i * width / num_ticks)
            val = total * i / num_ticks
            label = f"{val:.1f}"
            for j, ch in enumerate(label):
                if col + j < width:
                    ruler[col + j] = ch
        print("  " + DIM + "".join(ruler) + RESET)

    if num_processors > 1:
        for proc in range(num_processors):
            proc_events = [(s, e, t) for s, e, t, p in schedule_events if p == proc]
            print(f"  {DIM}P{proc}:{RESET}", end="")
            if not proc_events:
                print("  " + " " * width)
                continue
            spans = draw_row(proc_events)
            parts = []
            for span in spans:
                if span[0] == "space":
                    parts.append(" " * (span[2] - span[1]))
                else:
                    color, sc, ec, label, _ = span
                    bar = "─" * (ec - sc)
                    if label:
                        pos = sc + (ec - sc - len(label)) // 2
                        bar = " " * (ec - sc)
                        bar = bar[:pos - sc] + label + bar[pos - sc + len(label):]
                    parts.append(f"{color}{bar}{RESET}")
            print("  " + "".join(parts))
        ruler_spans = [("space", 0, width)]
        print_ruler_row(ruler_spans)
    else:
        proc_events = [(s, e, t) for s, e, t, _ in schedule_events]
        spans = draw_row(proc_events)
        parts = []
        for span in spans:
            if span[0] == "space":
                parts.append(" " * (span[2] - span[1]))
            else:
                color, sc, ec, label, _ = span
                bar = "─" * (ec - sc)
                if label:
                    pos = sc + (ec - sc - len(label)) // 2
                    bar = " " * (ec - sc)
                    bar = bar[:pos - sc] + label + bar[pos - sc + len(label):]
                parts.append(f"{color}{bar}{RESET}")
        print("  " + "".join(parts))
        print_ruler_row([("space", 0, width)])

    legend = "  Legend: " + "  ".join(
        f"{get_color(n)}{n}{RESET}" for n in seen_names
    )
    print(f"  {DIM}{'─' * width}{RESET}")
    print(legend)


def print_metrics(result, strategy_name: str):
    util = result.cpu_utilization()
    done = result.throughput()
    miss = result.deadline_miss_count()
    avg_rt = 0.0
    if result.task_response_times:
        avg_rt = sum(result.task_response_times.values()) / len(result.task_response_times)

    print(f"\n  {BOLD}Metrics:{RESET}")
    print(f"    CPU Utilization  :  {util:.1f}%")
    print(f"    Throughput        :  {done} tasks completed")
    if miss > 0:
        print(f"    Deadline Misses   :  {RED}{miss}{RESET}  {DIM}({', '.join(result.missed_deadlines)}){RESET}")
    else:
        print(f"    Deadline Misses   :  {GREEN}0{RESET}")
    print(f"    Avg Response Time :  {avg_rt:.3f}")


def main():
    parser = argparse.ArgumentParser(
        description="Real-Time Scheduling Simulator",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py --config config/tasks.yaml
  python main.py --config config/tasks.yaml --strategy rms --start 0 --end 24
  python main.py --config config/tasks.yaml --strategy all
  python main.py --config config/tasks.yaml --list-strategies
  python main.py -c config/tasks.yaml -o png -s edf
  python main.py -c config/tasks.yaml -o tikz --output-file my_schedule.tex
  python main.py -c config/tasks.yaml -o all --output-file results.png
        """
    )
    parser.add_argument("--config", "-c", default="config/tasks.yaml",
                        help="Path to YAML config file")
    parser.add_argument("--strategy", "-s",
                        help="Scheduling strategy to use (overrides config)")
    parser.add_argument("--start", type=float,
                        help="Simulation start time (overrides config)")
    parser.add_argument("--end", type=float,
                        help="Simulation end time (overrides config)")
    parser.add_argument("--list-strategies", action="store_true",
                        help="List available strategies and exit")
    parser.add_argument("--width", type=int, default=70,
                        help="Gantt chart width (default: 70)")
    parser.add_argument("--output", "-o",
                        choices=["console", "png", "tikz", "all"],
                        default="console",
                        help="Output format: console (ASCII), png (image), tikz (LaTeX code), all (default: console)")
    parser.add_argument("--output-file",
                        help="Output file path (default: schedule.png / schedule.tex)")
    parser.add_argument("--processors", "-p", type=int,
                        help="Number of processors (overrides config)")

    args = parser.parse_args()

    config_path = Path(args.config)
    if not config_path.exists():
        print(f"Error: Config file not found: {args.config}", file=sys.stderr)
        sys.exit(1)

    try:
        config = load_config(args.config)
    except Exception as e:
        print(f"Error loading config: {e}", file=sys.stderr)
        sys.exit(1)

    for s in config.strategies:
        registry.register(s.name, {
            "type": s.type,
            "selector": s.selector,
            "fallback": s.fallback,
            "priority_key": s.priority_key,
            "condition": s.condition,
            "true_branch": s.true_branch,
            "false_branch": s.false_branch,
            "params": s.params,
            "module": s.module,
            "class_name": s.class_name,
            "description": s.description,
        })

    if args.list_strategies:
        list_strategies(config)
        return

    strategy = args.strategy or config.simulation.strategy
    start = args.start if args.start is not None else config.simulation.start
    end = args.end if args.end is not None else config.simulation.end
    num_procs = args.processors if args.processors is not None else config.simulation.num_processors

    if num_procs < 1:
        print(f"Error: num_processors must be >= 1, got {num_procs}", file=sys.stderr)
        sys.exit(1)

    if end <= start:
        print(f"Error: end ({end}) must be greater than start ({start})", file=sys.stderr)
        sys.exit(1)

    print_banner()

    if strategy == "all":
        results = {}
        for s in config.strategies:
            sname = s.name
            ok, msg = registry.validate(sname)
            if not ok:
                print(f"  {DIM}Skipping {sname}: {msg}{RESET}")
                continue
            try:
                result = run_strategy(config, sname, start, end, num_procs)
                results[sname] = result
            except Exception as e:
                print(f"  {RED}Error running {sname}: {e}{RESET}")

        output_mode = args.output
        if output_mode == "console" or output_mode == "all":
            print(format_strategy_summary(results, args.width))
            print()
            for sname, result in results.items():
                print(f"\n  {BOLD}--- {sname} ---{RESET}")
                print_gantt_simple(result, args.width, num_procs)
                print_metrics(result, sname)

        if output_mode == "tikz" or output_mode == "all":
            for sname, result in results.items():
                suffix = f"_{sname}" if len(results) > 1 else ""
                base = args.output_file or f"schedule{suffix}.tex"
                fname = os.path.join("output", base)
                code = to_tikz(result, sname, fname, num_processors=num_procs)
                print(f"  {GREEN}TikZ saved:{RESET} {fname}")
            if output_mode == "tikz":
                return

        if output_mode == "png" or output_mode == "all":
            for sname, result in results.items():
                suffix = f"_{sname}" if len(results) > 1 else ""
                base = args.output_file or f"schedule{suffix}.png"
                fname = os.path.join("output", base)
                try:
                    to_png(result, sname, fname, num_processors=num_procs)
                    print(f"  {GREEN}PNG saved:{RESET} {fname}")
                except ImportError as e:
                    print(f"  {RED}{e}{RESET}")
            if output_mode == "png":
                return
    else:
        ok, msg = registry.validate(strategy)
        if not ok:
            print(f"Error: {msg}", file=sys.stderr)
            sys.exit(1)

        result = run_strategy(config, strategy, start, end, num_procs)

        output_mode = args.output
        if output_mode == "console" or output_mode == "all":
            print_header(strategy, start, end, num_procs)
            print()
            print_gantt_simple(result, args.width, num_procs)
            print_metrics(result, strategy)

        if output_mode == "tikz":
            fname = os.path.join("output", args.output_file or "schedule.tex")
            code = to_tikz(result, strategy, fname, num_processors=num_procs)
            print(f"  {GREEN}TikZ saved:{RESET} {fname}")

        if output_mode == "png":
            fname = os.path.join("output", args.output_file or "schedule.png")
            try:
                to_png(result, strategy, fname, num_processors=num_procs)
                print(f"  {GREEN}PNG saved:{RESET} {fname}")
            except ImportError as e:
                print(f"  {RED}{e}{RESET}")

    print()


if __name__ == "__main__":
    main()
