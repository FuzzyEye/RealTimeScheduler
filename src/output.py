from typing import Optional
from src.scheduler import SchedulingResult, EventType


TASK_COLORS = [
    "#FF6B6B",
    "#4ECDC4",
    "#FFE66D",
    "#95E1D3",
    "#F38181",
    "#AA96DA",
    "#FCBAD3",
    "#A8D8EA",
    "#FFAAA5",
    "#98DDCA",
]

NAME_TO_COLOR_IDX = {}


def _get_color(name: str) -> str:
    if name not in NAME_TO_COLOR_IDX:
        NAME_TO_COLOR_IDX[name] = len(NAME_TO_COLOR_IDX) % len(TASK_COLORS)
    return TASK_COLORS[NAME_TO_COLOR_IDX[name]]


def _build_segments(result: SchedulingResult, num_processors: int = 1):
    segments = []
    running = {}
    seg_start = {}

    sorted_events = sorted(result.events, key=lambda e: e.time)

    for e in sorted_events:
        if e.event_type == EventType.SCHEDULE:
            proc = 0
            details = getattr(e, "details", "") or ""
            if "P" in details:
                try:
                    proc = int(details.split("P")[1].split()[0]) - 1
                except (IndexError, ValueError):
                    proc = 0
            running[proc] = e.task_name
            seg_start[proc] = e.time
        elif e.event_type in (EventType.COMPLETE, EventType.PREEMPT, EventType.QUANTUM_EXPIRE):
            for proc in list(running.keys()):
                segments.append((seg_start[proc], e.time, running[proc], proc))
                del running[proc]
                del seg_start[proc]

    for proc, task in running.items():
        segments.append((seg_start[proc], result.total_time, task, proc))

    return segments


def to_tikz(
    result: SchedulingResult,
    strategy_name: str,
    output_path: Optional[str] = None,
    width_cm: float = 20.0,
    row_height: float = 0.8,
    num_processors: int = 1,
) -> str:
    segments = _build_segments(result, num_processors)
    if not segments:
        return "% No scheduling segments"

    total = result.total_time

    if num_processors > 1:
        num_rows = num_processors
        y_label = "Processor"
        row_labels = [f"P{i}" for i in range(num_processors)]
        y_scale = 1
    else:
        task_order = list(dict.fromkeys(name for _, _, name, _ in segments))
        num_rows = len(task_order)
        y_label = "Task"
        row_labels = task_order

    height = num_rows * row_height + 2.5

    lines = []
    lines.append(r"\begin{tikzpicture}[")
    lines.append(f"  x={width_cm / (total + 2)}cm,")
    lines.append(f"  y={row_height}cm,")
    lines.append("  scale=1.0,")
    lines.append("  transform shape")
    lines.append("]")
    lines.append("")

    lines.append("  % Axes")
    lines.append(f"  \\draw[->] (0, 0) -- ({total + 1}, 0) node[right] {{$t$}};")
    lines.append(f"  \\draw[->] (0, 0) -- (0, {num_rows + 1}) node[above] {{{y_label}}};")
    lines.append("")

    lines.append("  % Grid lines")
    lines.append(f"  \\foreach \\x in {{0,1,...,{int(total) + 1}}} {{")
    lines.append(f"    \\draw[gray!30, thin] (\\x, 0) -- (\\x, {num_rows + 1});")
    lines.append("  }")
    lines.append("")

    lines.append("  % Time labels")
    lines.append(f"  \\foreach \\x in {{0,1,...,{int(total) + 1}}} {{")
    lines.append(f"    \\node[below, font=\\footnotesize] at (\\x, -0.3) {{\\x}};")
    lines.append("  }")
    lines.append("")

    for idx in range(num_rows):
        y = num_rows - idx
        label = row_labels[idx]
        lines.append(f"  \\node[left, font={{\\ttfamily\\footnotesize}}] at (-0.3, {y}) {{{label}}};")
        lines.append(f"  \\draw[gray!50!black!30, thin] (-0.1, {y}) -- ({total + 1}, {y});")

    lines.append("")

    for start, end, name, proc in segments:
        if num_processors > 1:
            y_idx = proc
        else:
            y_idx = row_labels.index(name)
        y = num_rows - y_idx
        color = _get_color(name)
        duration = end - start
        lines.append(f"  \\draw[fill={color}, draw={color}!70!black]")
        lines.append(f"    ({start}, {y - 0.38}) rectangle ({end}, {y + 0.38});")
        if duration > 0.4:
            lines.append(f"  \\node[font={{\\ttfamily\\footnotesize}}, black!60!white, midway, yshift=0.15cm] at ({start + duration / 2}, {y}) {{{name}}};")

    lines.append("")
    lines.append(f"  % Title")
    lines.append(f"  \\node[font={{\\bfseries}}, anchor=north west] at (0, {num_rows + 1.5}) {{Scheduler: {strategy_name}}};")
    lines.append(f"  \\node[anchor=north west, font={{\\footnotesize}}] at (0, {num_rows + 0.8}) {{Total: {total:.1f}  |  Procs: {num_processors}  |  Done: {result.throughput()}  |  Miss: {result.deadline_miss_count()}  |  CPU: {result.cpu_utilization():.1f}\\%}};")
    lines.append("")
    lines.append(r"\end{tikzpicture}")

    code = "\n".join(lines)

    if output_path:
        with open(output_path, "w") as f:
            f.write(code)

    return code


def to_png(
    result: SchedulingResult,
    strategy_name: str,
    output_path: str = "output/schedule.png",
    figsize: tuple = (14, 5),
    dpi: int = 150,
    num_processors: int = 1,
) -> None:
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import matplotlib.patches as mpatches
    except ImportError:
        raise ImportError(
            "matplotlib is required for PNG output. Install it with: pip install matplotlib"
        )

    segments = _build_segments(result, num_processors)
    if not segments:
        return

    total = result.total_time

    if num_processors > 1:
        num_rows = num_processors
        row_labels = [f"P{i}" for i in range(num_rows)]
    else:
        row_labels = list(dict.fromkeys(name for _, _, name, _ in segments))
        num_rows = len(row_labels)

    fig_h = max(figsize[1], num_rows * 0.8 + 2)
    fig, ax = plt.subplots(figsize=(figsize[0], fig_h))
    fig.patch.set_facecolor("#1E1E1E")
    ax.set_facecolor("#2D2D2D")

    for start, end, name, proc in segments:
        if num_processors > 1:
            y_idx = num_rows - 1 - proc
            label = f"P{proc}"
        else:
            y_idx = row_labels.index(name)
            label = name
        color = _get_color(name)
        duration = end - start

        rect = mpatches.FancyBboxPatch(
            (start, y_idx - 0.38),
            duration,
            0.76,
            boxstyle="round,pad=0.02",
            facecolor=color,
            edgecolor=color,
            linewidth=1.5,
            alpha=0.9,
            zorder=3,
        )
        ax.add_patch(rect)
        if duration > (total * 0.025) and duration > 0.3:
            ax.text(
                start + duration / 2,
                y_idx,
                name,
                ha="center",
                va="center",
                fontsize=6,
                fontweight="bold",
                color="black",
                zorder=4,
            )

    ax.set_xlim(-0.5, total + 1)
    ax.set_ylim(-0.8, num_rows)
    ax.set_yticks(range(num_rows))
    ax.set_yticklabels(row_labels, fontsize=8, fontfamily="monospace")
    ax.set_xlabel("Time", fontsize=9, color="#CCCCCC")
    ax.set_ylabel("Processor" if num_processors > 1 else "Task", fontsize=9, color="#CCCCCC")
    ax.set_title(
        f"{strategy_name}  |  Time: 0.0 → {total:.1f}  |  "
        f"Procs: {num_processors}  |  "
        f"Done: {result.throughput()}  |  Miss: {result.deadline_miss_count()}  |  "
        f"CPU: {result.cpu_utilization():.1f}%",
        fontsize=10,
        fontweight="bold",
        color="#FFFFFF",
        pad=12,
    )

    ax.tick_params(colors="#AAAAAA", labelsize=8)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["bottom"].set_color("#555555")
    ax.spines["left"].set_color("#555555")
    for spine in ax.spines.values():
        spine.set_linewidth(0.8)

    ax.grid(axis="x", color="#444444", linewidth=0.5, alpha=0.6)
    ax.axhline(y=-0.5, color="#555555", linewidth=0.8)

    if num_processors > 1:
        legend_patches = [
            mpatches.Patch(facecolor="#555555", edgecolor="#333", label=f"Processor {i}")
            for i in range(num_processors)
        ]
    else:
        legend_patches = [
            mpatches.Patch(facecolor=_get_color(name), edgecolor="#333", label=name)
            for name in row_labels
        ]

    ax.legend(
        handles=legend_patches,
        loc="upper right",
        ncol=min(len(legend_patches), 8),
        fontsize=7,
        framealpha=0.3,
        labelcolor="#DDDDDD",
        facecolor="#2D2D2D",
        edgecolor="#555555",
    )

    plt.tight_layout()
    plt.savefig(output_path, dpi=dpi, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close()
