from __future__ import annotations

import os
from typing import Optional

from src.sim.scheduler import EventType, SchedulingResult
from src.render.exporters.common import build_segments


def to_tikz(
    result: SchedulingResult,
    strategy_name: str,
    output_path: Optional[str] = None,
    width_cm: float = 20.0,
    row_height: float = 0.8,
    show_preemptions: bool = True,
    show_deadlines: bool = True,
) -> str:
    segments = build_segments(result)
    if not segments:
        return "% No scheduling segments"

    total = int(result.total_time)
    row_labels = list(dict.fromkeys(name for _, _, name in segments))
    num_rows = len(row_labels)
    xscale = max(0.2, width_cm / max(total + 1, 1))
    yscale = max(0.7, row_height * 1.2)
    strategy_y = num_rows + 0.8
    task_to_y = {label: num_rows - idx - 1 for idx, label in enumerate(row_labels)}

    def _instance_from_details(details: str) -> int | None:
        if "instance=" not in details:
            return None
        try:
            raw = details.split("instance=")[1].split(")")[0].split()[0]
            return int(raw)
        except Exception:
            return None

    lines = [
        rf"\begin{{tikzpicture}}[xscale={xscale:.3f}, yscale={yscale:.3f}, every node/.style={{scale=1}}]",
        r"  \tikzset{>={stealth[scale=1.2]}}",
        "",
        "  % Academic timeline style",
        "  \\tikzset{pulse/.style={draw=black, fill=gray!50, line width=0.5pt}}",
        "",
        "  % Draw per-task timelines",
    ]

    for idx, label in enumerate(row_labels):
        y = task_to_y[label]
        lines.append(
            f"  \\draw[->, thick, -stealth] (0, {y}) -- ({total + 1}, {y}) "
            f"node[pos=0, left] {{$\\tau_{{{idx + 1}}}$({label})}};"
        )

    lines.extend(
        [
            "",
            "  % Time ticks",
            f"  \\foreach \\x in {{0,1,...,{total + 1}}} {{",
            "    \\draw (\\x, 0) -- (\\x, -3pt);",
            "  }",
            "  % Sparse tick labels",
            f"  \\foreach \\x in {{1,3,...,{total + 1 if (total + 1) % 2 == 1 else total}}} {{",
            "    \\node[below, font=\\small] at (\\x, -3pt) {\\x};",
            "  }",
            "",
            "  % Strategy marker",
            f"  \\draw[->, thick, -stealth] (0, 0) -- (0, {strategy_y:.1f});",
            f"  \\node[left, font=\\small\\bfseries] at (0, {strategy_y:.1f}) {{{strategy_name.upper()}}};",
            "",
            "  % Execution pulses",
        ]
    )

    for start, end, name in segments:
        y = task_to_y[name]
        lines.append(f"  \\draw[pulse] ({start}, {y}) rectangle ({end}, {y + 0.30});")

    if show_deadlines:
        deadline_events = sorted([e for e in result.events if e.event_type == EventType.DEADLINE], key=lambda e: e.time)
        if deadline_events:
            miss_keys = set()
            for ev in result.events:
                if ev.event_type != EventType.DEADLINE_MISS:
                    continue
                miss_keys.add((ev.task_name, int(ev.time), _instance_from_details(ev.details)))

            lines.extend(["", "  % Deadline arrows (upward); missed instances marked with cross"])
            for ev in deadline_events:
                x = int(ev.time)
                y = task_to_y.get(ev.task_name)
                if y is None:
                    continue

                lines.append(f"  \\draw[thick, ->] ({x}, {y}) -- ({x}, {y + 0.5});")

                key = (ev.task_name, x, _instance_from_details(ev.details))
                if key in miss_keys:
                    cx = x
                    cy = y + 0.58
                    lines.append(f"  \\draw[thick] ({cx - 0.10}, {cy - 0.08}) -- ({cx + 0.10}, {cy + 0.08});")
                    lines.append(f"  \\draw[thick] ({cx - 0.10}, {cy + 0.08}) -- ({cx + 0.10}, {cy - 0.08});")

    pct_str = r"\%"
    lines.extend(
        [
            "",
            "  % Metrics",
            f"  \\node[anchor=west, font=\\scriptsize] at (0, {-0.7}) "
            f"{{Horizon={total}, Done={result.throughput()}, Miss={result.deadline_miss_count()}, CPU={int(round(result.cpu_utilization()))}{pct_str}}};",
            r"\end{tikzpicture}",
        ]
    )

    code = "\n".join(lines)
    if output_path:
        os.makedirs(os.path.dirname(output_path) if os.path.dirname(output_path) else "output", exist_ok=True)
        with open(output_path, "w") as f:
            f.write(code)
    return code

