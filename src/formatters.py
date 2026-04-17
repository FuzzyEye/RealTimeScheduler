from src.scheduler import SchedulingResult, ScheduleEvent, EventType

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
    segments = []
    running = None
    seg_start = 0.0
    sorted_events = sorted(result.events, key=lambda e: e.time)

    for e in sorted_events:
        if e.event_type == EventType.SCHEDULE:
            if running is not None and seg_start < e.time:
                segments.append((seg_start, e.time, running))
            running = e.task_name
            seg_start = e.time
        elif e.event_type in (EventType.COMPLETE, EventType.PREEMPT, EventType.QUANTUM_EXPIRE):
            if running is not None:
                segments.append((seg_start, e.time, running))
                running = None
                seg_start = e.time

    if running is not None:
        segments.append((seg_start, result.total_time, running))

    return segments


def format_gantt(result: SchedulingResult, max_width: int = 80, num_processors: int = 1) -> str:
    if not result.events:
        return "  (no scheduling events)"

    segments = _build_segments(result)
    if not segments:
        return "  (no execution segments)"

    total = result.total_time
    if total <= 0:
        total = 1.0

    avail_width = max_width - 4
    if avail_width < 10:
        avail_width = 80

    scale = avail_width / total

    def time_to_col(t: float) -> int:
        return int(t * scale)

    seen_names = []
    for _, _, name in segments:
        if name not in seen_names:
            seen_names.append(name)

    output_lines = []

    ruler = [" "] * avail_width
    num_ticks = min(avail_width // 10, 20)
    if num_ticks == 0:
        num_ticks = 1
    for i in range(num_ticks + 1):
        col = int(i * avail_width / num_ticks)
        val = total * i / num_ticks
        label = f"{val:.1f}"
        for j, ch in enumerate(label):
            if col + j < avail_width:
                ruler[col + j] = ch

    output_lines.append(f"  {DIM}{'─' * avail_width}{RESET}")

    bar = [" "] * avail_width
    for start_t, end_t, task_name in segments:
        sc = max(0, min(time_to_col(start_t), avail_width - 1))
        ec = max(sc, min(time_to_col(end_t), avail_width))
        color = _get_color(task_name)
        label = task_name[:max(1, ec - sc)]
        for i in range(sc, ec):
            bar[i] = f"{color}─{RESET}"
        if ec - sc >= len(label):
            pos = sc + (ec - sc - len(label)) // 2
            bar[pos:pos + len(label)] = list(f"{color}{label}{RESET}")

    output_lines.append("  " + "".join(bar))

    output_lines.append("  " + "".join(ruler))

    legend = "  Legend: " + "  ".join(
        f"{_get_color(n)}{n}{RESET}" for n in seen_names
    )
    output_lines.append(legend)

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
