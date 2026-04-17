import os
import yaml
import sys
from pathlib import Path
from typing import List, Optional

from src.task import Task
from src.config import Config, ConfigTask, ConfigSimulation, ConfigStrategy
from src.simulator import SimulationEngine
from src.formatters import format_metrics, format_strategy_summary
from src.registry import registry
from src.plugins import load_plugin
from src.output import to_png, to_tikz, to_svg, to_html
from src.reports import ReportExporter

RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"
GREEN = "\033[92m"
RED = "\033[91m"
CYAN = "\033[96m"
YELLOW = "\033[93m"


def _read_yaml(path: Path) -> dict:
    with open(path, "r") as f:
        return yaml.safe_load(f) or {}


def load_config(config_dir: str) -> tuple[Config, dict]:
    base = Path(config_dir)
    tasks_path = base / "tasks.yaml"
    system_path = base / "system.yaml"
    policy_path = base / "policy.yaml"

    missing = [p.name for p in (tasks_path, system_path, policy_path) if not p.exists()]
    if missing:
        raise FileNotFoundError(
            f"Missing config files in '{config_dir}': {', '.join(missing)}"
        )

    tasks_raw = _read_yaml(tasks_path)
    system_raw = _read_yaml(system_path)
    policy_raw = _read_yaml(policy_path)

    tasks = []
    for t in tasks_raw.get("tasks", []):
        tasks.append(ConfigTask(
            name=t["name"],
            execution_time=t["execution_time"],
            period=t.get("period"),
            deadline=t.get("deadline"),
            priority=t.get("priority", 0),
            arrival_time=t.get("arrival_time", 0.0),
            value=t.get("value"),
        ))

    sim = system_raw.get("system", {}).get("simulation", {})
    simulation = ConfigSimulation(
        start=float(sim.get("start", 0.0)),
        end=float(sim.get("end", 10.0)),
        strategy=sim.get("strategy", "edf"),
        num_processors=int(sim.get("num_processors", 1)),
        preemptive=bool(sim.get("preemptive", True)),
        params=sim.get("params", {}),
    )

    strategies = []
    for s in policy_raw.get("strategies", []):
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

    return Config(tasks=tasks, simulation=simulation, strategies=strategies), system_raw


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
        preemptive=config.simulation.preemptive,
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


def print_metrics(result, strategy_name: str, verbose: bool = False):
    util = result.cpu_utilization()
    done = result.throughput()
    miss = result.deadline_miss_count()
    avg_rt = result.response_time_avg()
    max_rt = result.response_time_max()
    min_rt = result.response_time_min()
    jitter = result.response_time_jitter()
    avg_wait = result.waiting_time_avg()
    max_wait = result.waiting_time_max()
    preempt = result.preemption_count
    ctx_sw = result.context_switch_count

    print(f"\n  {BOLD}Metrics:{RESET}")
    print(f"    CPU Utilization  :  {util:.1f}%")
    print(f"    Throughput        :  {done} tasks completed")
    if miss > 0:
        print(f"    Deadline Misses   :  {RED}{miss}{RESET}  {DIM}({', '.join(result.missed_deadlines)}){RESET}")
    else:
        print(f"    Deadline Misses   :  {GREEN}0{RESET}")
    print(f"    Avg Response Time :  {avg_rt:.3f}")

    if verbose:
        print(f"    Max Response Time:  {max_rt:.3f}")
        print(f"    Min Response Time:  {min_rt:.3f}")
        print(f"    Response Jitter  :  {jitter:.3f}")
        print(f"    Avg Waiting Time :  {avg_wait:.3f}")
        print(f"    Max Waiting Time:  {max_wait:.3f}")
        print(f"    Preemptions      :  {preempt}")
        print(f"    Context Switches:  {ctx_sw}")


def main():
    config_dir = os.getenv("RTS_CONFIG_DIR", "config")

    try:
        config, system_raw = load_config(config_dir)
    except Exception as e:
        print(f"Error loading modular config: {e}", file=sys.stderr)
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

    execution_cfg = system_raw.get("system", {}).get("execution", {})
    output_cfg = system_raw.get("system", {}).get("output", {})
    export_cfg = system_raw.get("system", {}).get("export", {})

    if bool(execution_cfg.get("list_strategies", False)):
        list_strategies(config)
        return

    strategy = execution_cfg.get("strategy", config.simulation.strategy)
    start = config.simulation.start
    end = config.simulation.end
    num_procs = config.simulation.num_processors
    output_mode = output_cfg.get("mode", "console")
    width = int(output_cfg.get("width", 70))
    output_file = output_cfg.get("output_file")
    verbose = bool(output_cfg.get("verbose", False))
    debug = bool(output_cfg.get("debug", False))

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

        if output_mode == "console" or output_mode == "all":
            print(format_strategy_summary(results, width))
            print()
            for sname, result in results.items():
                print(f"\n  {BOLD}--- {sname} ---{RESET}")
                print_gantt_simple(result, width, num_procs)
                print_metrics(result, sname, verbose=verbose)

        if output_mode == "tikz" or output_mode == "all":
            for sname, result in results.items():
                suffix = f"_{sname}" if len(results) > 1 else ""
                base = output_file or f"schedule{suffix}.tex"
                fname = os.path.join("output", base)
                code = to_tikz(result, sname, fname, num_processors=num_procs)
                print(f"  {GREEN}TikZ saved:{RESET} {fname}")
            if output_mode == "tikz":
                return

        if output_mode == "png" or output_mode == "all":
            for sname, result in results.items():
                suffix = f"_{sname}" if len(results) > 1 else ""
                base = output_file or f"schedule{suffix}.png"
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

        if output_mode == "console" or output_mode == "all":
            print_header(strategy, start, end, num_procs)
            print()
            print_gantt_simple(result, width, num_procs)
            print_metrics(result, strategy, verbose=verbose)

        if output_mode == "tikz":
            fname = os.path.join("output", output_file or "schedule.tex")
            code = to_tikz(result, strategy, fname, num_processors=num_procs)
            print(f"  {GREEN}TikZ saved:{RESET} {fname}")

        if output_mode == "png":
            fname = os.path.join("output", output_file or "schedule.png")
            try:
                to_png(result, strategy, fname, num_processors=num_procs)
                print(f"  {GREEN}PNG saved:{RESET} {fname}")
            except ImportError as e:
                print(f"  {RED}{e}{RESET}")

    report_results = results if strategy == "all" else {strategy: result}
    if export_cfg.get("json"):
        ReportExporter.save_json(report_results, export_cfg["json"])
        print(f"  {GREEN}JSON saved:{RESET} {export_cfg['json']}")

    if export_cfg.get("csv"):
        ReportExporter.save_csv(report_results, export_cfg["csv"])
        print(f"  {GREEN}CSV saved:{RESET} {export_cfg['csv']}")

    if export_cfg.get("svg") and strategy != "all":
        to_svg(result, strategy, export_cfg["svg"], num_processors=num_procs)
        print(f"  {GREEN}SVG saved:{RESET} {export_cfg['svg']}")

    if export_cfg.get("html") and strategy != "all":
        to_html(result, strategy, export_cfg["html"], num_processors=num_procs)
        print(f"  {GREEN}HTML saved:{RESET} {export_cfg['html']}")

    if debug and strategy != "all":
        print(f"\n  {DIM}=== DEBUG INFO ==={RESET}")
        print(f"  {DIM}Events: {len(result.events)}")
        print(f"  {DIM}Completed: {result.completed_tasks}")
        print(f"  {DIM}Missed: {result.missed_deadlines}")
        print(f"  {DIM}Response times: {result.task_response_times}")
        print(f"  {DIM}Wait times: {result.task_wait_times}{RESET}")

    print()


if __name__ == "__main__":
    main()
