from __future__ import annotations

from src.sim.scheduler import SchedulingResult
from src.formatters import format_gantt

RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"
GREEN = "\033[92m"
RED = "\033[91m"
CYAN = "\033[96m"


def print_banner() -> None:
    print(f"\n  {BOLD}{'=' * 60}{RESET}")
    print(f"  {BOLD}       AutoScheduler — Real-Time Scheduling Simulator       {RESET}")
    print(f"  {BOLD}{'=' * 60}{RESET}\n")


def print_header(strategy_name: str, start: float, end: float) -> None:
    print(
        f"  {BOLD}Strategy:{RESET} {CYAN}{strategy_name}{RESET}  "
        f"{BOLD}Window:{RESET} {start:.2f} → {end:.2f}  {BOLD}Processor:{RESET} 1"
    )
    print(f"  {DIM}{'-' * 60}{RESET}")


def print_gantt(result: SchedulingResult, width: int) -> None:
    print(format_gantt(result, max_width=width))


def print_metrics(result: SchedulingResult, verbose: bool = False) -> None:
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

