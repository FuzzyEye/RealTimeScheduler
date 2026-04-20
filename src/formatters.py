from src.sim.scheduler import SchedulingResult, ScheduleEvent, EventType
from src.sim.timeline import build_execution_segments

RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"

TASK_COLORS = [
    "\033[91m",
    "\033[92m",
    "\033[93m",
    "\033[94m",
    "\033[95m",
    "\033[96m",
    "\033[97m",
]

NAME_TO_COLOR = {}


def _get_color(name: str) -> str:
    if name not in NAME_TO_COLOR:
        idx = len(NAME_TO_COLOR) % len(TASK_COLORS)
        NAME_TO_COLOR[name] = TASK_COLORS[idx]
    return NAME_TO_COLOR[name]


def _build_segments(result: SchedulingResult) -> list:
    return build_execution_segments(result)


def format_gantt(result: SchedulingResult, max_width: int = 80) -> str:
    if not result.events:
        return "  (no scheduling events)"

    segments = _build_segments(result)
    if not segments:
        return "  (no execution segments)"

    total = int(result.total_time)
    if total <= 0:
        total = 1.0

    avail_width = max_width - 4
    if avail_width < 10:
        avail_width = 80

    scale = avail_width / total

    seen_names = []
    for _, _, name in segments:
        if name not in seen_names:
            seen_names.append(name)

    def draw_row() -> list:
        spans = []
        cur = 0
        for start_t, end_t, task_name in segments:
            sc = max(0, min(int(start_t * scale), avail_width))
            ec = max(sc, min(int(end_t * scale), avail_width))
            if sc > cur:
                spans.append(("space", cur, sc))
            spans.append((_get_color(task_name), sc, ec, task_name))
            cur = ec
        if cur < avail_width:
            spans.append(("space", cur, avail_width))
        return spans

    parts = []
    for span in draw_row():
        if span[0] == "space":
            parts.append(" " * (span[2] - span[1]))
            continue
        color, sc, ec, task_name = span
        width = ec - sc
        if width <= 0:
            continue
        bar = ["─"] * width
        label = task_name[:width]
        if label:
            start = max(0, (width - len(label)) // 2)
            for i, ch in enumerate(label):
                if start + i < width:
                    bar[start + i] = ch
        parts.append(f"{color}{''.join(bar)}{RESET}")

    ruler = [" "] * avail_width
    num_ticks = min(avail_width // 10, 20) or 1
    for i in range(num_ticks + 1):
        col = int(i * avail_width / num_ticks)
        val = int(total * i / num_ticks)
        label = f"{val}"
        for j, ch in enumerate(label):
            if col + j < avail_width:
                ruler[col + j] = ch

    output_lines = [
        f"  {DIM}{'─' * avail_width}{RESET}",
        "  " + "".join(parts),
        "  " + "".join(ruler),
        "  Legend: " + "  ".join(f"{_get_color(n)}{n}{RESET}" for n in seen_names),
    ]
    return "\n".join(output_lines)


def format_metrics(result: SchedulingResult, strategy_name: str) -> str:
    lines = []
    lines.append(f"  {BOLD}Metrics:{RESET}")

    util = result.cpu_utilization()
    lines.append(f"    CPU Utilization  :  {util:.1f}%")
    lines.append(f"    Throughput        :  {result.throughput()} tasks completed")

    miss_count = result.deadline_miss_count()
    if miss_count > 0:
        lines.append(f"    Deadline Misses   :  {miss_count} {DIM}({', '.join(result.missed_deadlines)}){RESET}")
    else:
        lines.append(f"    Deadline Misses   :  0")

    if result.task_response_times:
        avg_rt = sum(result.task_response_times.values()) / len(result.task_response_times)
        lines.append(f"    Avg Response Time :  {avg_rt:.3f}")

    return "\n".join(lines)


def format_strategy_summary(results: dict, max_width: int = 80) -> str:
    lines = []
    header = f"  {BOLD}Strategy Comparison ({len(results)} strategies){RESET}"
    lines.append(header)
    lines.append(f"  {'─' * 60}")
    lines.append(f"  {DIM}{'Strategy':<20} {'CPU%':>7}  {'Done':>5}  {'Miss':>5}  {'AvgRT':>8}{RESET}")

    for name, result in results.items():
        util = result.cpu_utilization()
        done = result.throughput()
        miss = result.deadline_miss_count()
        avg_rt = 0.0
        if result.task_response_times:
            avg_rt = sum(result.task_response_times.values()) / len(result.task_response_times)

        lines.append(f"  {name:<20} {util:>6.1f}%  {done:>5}  {miss:>5}  {avg_rt:>8.3f}")

    lines.append(f"  {'─' * 60}")
    return "\n".join(lines)
