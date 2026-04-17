from typing import Optional, List, Tuple
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
    show_preemptions: bool = True,
    show_deadlines: bool = True,
) -> str:
    segments = _build_segments(result, num_processors)
    if not segments:
        return "% No scheduling segments"

    total = result.total_time

    if num_processors > 1:
        num_rows = num_processors
        y_label = "Processor"
        row_labels = [f"P{i}" for i in range(num_processors)]
    else:
        task_order = list(dict.fromkeys(name for _, _, name, _ in segments))
        num_rows = len(task_order)
        y_label = "Task"
        row_labels = task_order

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

    for idx in range(num_rows):
        y = num_rows - idx
        label = row_labels[idx]
        lines.append(f"  \\node[left, font={{\\ttfamily\\footnotesized}}] at (-0.3, {y}) {{{label}}};")

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
            lines.append(f"  \\node[font={{\\ttfamily\\footnotesized}}, black!60!white, midway, yshift=0.15cm] at ({start + duration / 2}, {y}) {{{name}}};")

    preempt_events = [(e.time, e.task_name) for e in result.events if e.event_type == EventType.PREEMPT]
    if show_preemptions and preempt_events:
        lines.append("")
        lines.append("  % Preemption markers")
        for ptime, pname in preempt_events:
            for start, end, name, proc in segments:
                if name == pname and start < ptime < end:
                    if num_processors > 1:
                        y = num_rows - proc
                    else:
                        y = num_rows - row_labels.index(name)
                    lines.append(f"  \\draw[red, dashed, very thin] ({ptime}, {y - 0.38}) -- ({ptime}, {y + 0.38});")
                    break

    lines.append("")
    lines.append(f"  % Title")
    lines.append(f"  \\node[font={{\\bfseries}}, anchor=north west] at (0, {num_rows + 1.5}) {{Scheduler: {strategy_name}}};")
    pct_str = r"\%"
    lines.append(f"  \\node[anchor=north west, font={{\\footnotesized}}] at (0, {num_rows + 0.8}) {{Total: {total:.1f}  |  Procs: {num_processors}  |  Done: {result.throughput()}  |  Miss: {result.deadline_miss_count()}  |  CPU: {result.cpu_utilization():.1f}{pct_str}}};")
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
        f"{strategy_name}  |  Time: 0.0 - {total:.1f}  |  "
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
    plt.savefig(output_path, dpi=dpi, bbox_inches='tight', facecolor=fig.get_facecolor())
    plt.close()


def to_svg(
    result: SchedulingResult,
    strategy_name: str,
    output_path: Optional[str] = None,
    width: int = 800,
    height: int = 300,
    num_processors: int = 1,
) -> str:
    segments = _build_segments(result, num_processors)
    if not segments:
        return "<!-- No scheduling segments -->"

    total = result.total_time
    margin_left = 60
    margin_right = 20
    margin_top = 40
    margin_bottom = 30

    chart_width = width - margin_left - margin_right
    chart_height = height - margin_top - margin_bottom

    if num_processors > 1:
        rows = num_processors
        row_labels = [f"P{i}" for i in range(num_processors)]
    else:
        rows = len(set(name for _, _, name, _ in segments))
        row_labels = list(dict.fromkeys(name for _, _, name, _ in segments))

    row_height = chart_height / rows if rows > 0 else chart_height

    def time_to_x(t: float) -> float:
        return margin_left + (t / total) * chart_width

    def row_to_y(idx: int) -> float:
        return margin_top + (rows - 1 - idx) * row_height + row_height / 2

    lines = []
    lines.append(f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">')
    lines.append(f'  <defs>')
    lines.append(f'    <style>')
    lines.append(f'      .segment {{ stroke: #333; stroke-width: 1; opacity: 0.9; }}')
    lines.append(f'      .label {{ font-family: monospace; font-size: 10px; fill: #666; }}')
    lines.append(f'      .title {{ font-family: sans-serif; font-size: 14px; fill: #333; font-weight: bold; }}')
    lines.append(f'      .metric {{ font-family: sans-serif; font-size: 10px; fill: #666; }}')
    lines.append(f'      .axis {{ stroke: #ccc; stroke-width: 1; }}')
    lines.append(f'      .grid {{ stroke: #eee; stroke-width: 1; }}')
    lines.append(f'    </style>')
    lines.append(f'  </defs>')

    lines.append(f'  <rect width="{width}" height="{height}" fill="#fafafa"/>')

    lines.append(f'  <line x1="{margin_left}" y1="{height - margin_bottom}" x2="{width - margin_right}" y2="{height - margin_bottom}" class="axis"/>')
    lines.append(f'  <line x1="{margin_left}" y1="{margin_top}" x2="{margin_left}" y2="{height - margin_bottom}" class="axis"/>')

    num_ticks = min(int(total), 10)
    for i in range(num_ticks + 1):
        x = time_to_x(i * total / num_ticks)
        lines.append(f'  <line x1="{x}" y1="{margin_top}" x2="{x}" y2="{height - margin_bottom}" class="grid"/>')
        lines.append(f'  <text x="{x}" y="{height - 10}" text-anchor="middle" class="label">{i * total / num_ticks:.1f}</text>')

    for idx, label in enumerate(row_labels):
        y = row_to_y(idx)
        lines.append(f'  <text x="{margin_left - 5}" y="{y + 3}" text-anchor="end" class="label">{label}</text>')

    for start, end, name, proc in segments:
        if num_processors > 1:
            y_idx = proc
        else:
            y_idx = row_labels.index(name)
        y = row_to_y(y_idx)
        color = _get_color(name)
        x1 = time_to_x(start)
        x2 = time_to_x(end)
        lines.append(f'  <rect x="{x1}" y="{y - row_height * 0.4}" width="{x2 - x1}" height="{row_height * 0.8}" fill="{color}" class="segment"/>')

    lines.append(f'  <text x="{margin_left}" y="20" class="title">{strategy_name}</text>')

    util = result.cpu_utilization()
    done = result.throughput()
    miss = result.deadline_miss_count()
    lines.append(f'  <text x="{width - margin_right}" y="20" text-anchor="end" class="metric">CPU: {util:.1f}% | Done: {done} | Miss: {miss}</text>')

    lines.append(f'</svg>')

    svg_code = "\n".join(lines)

    if output_path:
        import os
        os.makedirs(os.path.dirname(output_path) if os.path.dirname(output_path) else "output", exist_ok=True)
        with open(output_path, "w") as f:
            f.write(svg_code)

    return svg_code


def to_html(
    result: SchedulingResult,
    strategy_name: str,
    output_path: Optional[str] = None,
    width: int = 900,
    height: int = 400,
    num_processors: int = 1,
) -> str:
    segments = _build_segments(result, num_processors)
    if not segments:
        html = "<!-- No scheduling segments -->"
        if output_path:
            with open(output_path, "w") as f:
                f.write(html)
        return html

    total = result.total_time
    margin_left = 80
    margin_right = 20
    margin_top = 60
    margin_bottom = 40

    chart_width = width - margin_left - margin_right
    chart_height = height - margin_top - margin_bottom

    if num_processors > 1:
        rows = num_processors
        row_labels = [f"Processor {i}" for i in range(num_processors)]
    else:
        rows = len(set(name for _, _, name, _ in segments))
        row_labels = list(dict.fromkeys(name for _, _, name, _ in segments))

    row_height = chart_height / rows if rows > 0 else chart_height

    def time_to_x(t: float) -> float:
        return margin_left + (t / total) * chart_width

    def row_to_y(idx: int) -> float:
        return margin_top + (rows - 1 - idx) * row_height + row_height / 2

    task_data = []
    for start, end, name, proc in segments:
        if num_processors > 1:
            y_idx = proc
        else:
            y_idx = row_labels.index(name)
        color = _get_color(name)
        duration = end - start
        task_data.append({
            "name": name,
            "start": start,
            "end": end,
            "duration": duration,
            "y_idx": y_idx,
            "color": color,
        })

    util = result.cpu_utilization()
    done = result.throughput()
    miss = result.deadline_miss_count()
    avg_rt = result.response_time_avg()

    unique_tasks = []
    seen = set()
    for d in task_data:
        if d["name"] not in seen:
            seen.add(d["name"])
            unique_tasks.append(d)

    grid_lines = "".join(f'<line x1="{time_to_x(i * total / 10)}" y1="{margin_top}" x2="{time_to_x(i * total / 10)}" y2="{height - margin_bottom}" class="grid-line"/>' for i in range(11))
    time_labels = "".join(f'<text x="{time_to_x(i * total / 10)}" y="{height - margin_bottom + 15}" text-anchor="middle" class="axis-text">{i * total / 10:.1f}</text>' for i in range(11))
    y_labels = "".join(f'<text x="{margin_left - 10}" y="{row_to_y(idx) + 3}" text-anchor="end" class="axis-text">{label}</text>' for idx, label in enumerate(row_labels))
    rects = "".join(f'<rect x="{time_to_x(d["start"])}" y="{row_to_y(d["y_idx"]) - row_height * 0.4}" width="{time_to_x(d["end"]) - time_to_x(d["start"])}" height="{row_height * 0.8}" fill="{d["color"]}" class="segment-rect" data-name="{d["name"]}" data-start="{d["start"]:.2f}" data-end="{d["end"]:.2f}" data-duration="{d["duration"]:.2f}"/>' for d in task_data)
    legend_items = "".join(f'<div class="legend-item"><div class="legend-color" style="background: {d["color"]}"></div><span>{d["name"]}</span></div>' for d in unique_tasks)

    html = f'''<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>{strategy_name} - Real-Time Scheduling</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #f5f5f5; padding: 20px; }}
        .container {{ max-width: {width}px; margin: 0 auto; background: white; border-radius: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); overflow: hidden; }}
        .header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 20px; }}
        .header h1 {{ font-size: 20px; margin-bottom: 5px; }}
        .header .metrics {{ display: flex; gap: 20px; font-size: 13px; opacity: 0.9; }}
        .chart-container {{ padding: 20px; position: relative; }}
        svg {{ display: block; }}
        .tooltip {{ position: absolute; background: #333; color: white; padding: 8px 12px; border-radius: 4px; font-size: 12px; pointer-events: none; opacity: 0; transition: opacity 0.2s; z-index: 100; white-space: nowrap; }}
        .tooltip.visible {{ opacity: 1; }}
        .legend {{ display: flex; flex-wrap: wrap; gap: 10px; padding: 15px 20px; border-top: 1px solid #eee; }}
        .legend-item {{ display: flex; align-items: center; gap: 5px; font-size: 12px; }}
        .legend-color {{ width: 12px; height: 12px; border-radius: 2px; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>{strategy_name}</h1>
            <div class="metrics">
                <span>CPU: {util:.1f}%</span>
                <span>Done: {done}</span>
                <span>Miss: {miss}</span>
                <span>Avg RT: {avg_rt:.3f}</span>
            </div>
        </div>
        <div class="chart-container">
            <svg width="{width}" height="{height}" viewBox="0 0 {width} {height}">
                <defs>
                    <style>
                        .axis-text {{ font-family: monospace; font-size: 10px; fill: #666; }}
                        .grid-line {{ stroke: #eee; stroke-width: 1; }}
                        .axis-line {{ stroke: #ccc; stroke-width: 1; }}
                        .segment-rect {{ cursor: pointer; stroke: #333; stroke-width: 1; }}
                    </style>
                </defs>
                <line x1="{margin_left}" y1="{height - margin_bottom}" x2="{width - margin_right}" y2="{height - margin_bottom}" class="axis-line"/>
                <line x1="{margin_left}" y1="{margin_top}" x2="{margin_left}" y2="{height - margin_bottom}" class="axis-line"/>
                {grid_lines}
                {time_labels}
                {y_labels}
                {rects}
            </svg>
            <div class="tooltip" id="tooltip"></div>
        </div>
        <div class="legend">
            {legend_items}
        </div>
    </div>
    <script>
        const segments = document.querySelectorAll('.segment-rect');
        const tooltip = document.getElementById('tooltip');

        segments.forEach(seg => {{
            seg.addEventListener('mouseenter', (e) => {{
                const name = seg.dataset.name;
                const start = seg.dataset.start;
                const end = seg.dataset.end;
                const duration = seg.dataset.duration;
                tooltip.innerHTML = `<strong>${{name}}</strong><br>Start: ${{start}}<br>End: ${{end}}<br>Duration: ${{duration}}`;
                tooltip.classList.add('visible');
            }});
            seg.addEventListener('mousemove', (e) => {{
                tooltip.style.left = (e.pageX + 10) + 'px';
                tooltip.style.top = (e.pageY - 30) + 'px';
            }});
            seg.addEventListener('mouseleave', () => {{
                tooltip.classList.remove('visible');
            }});
        }});
    </script>
</body>
</html>'''

    if output_path:
        import os
        os.makedirs(os.path.dirname(output_path) if os.path.dirname(output_path) else "output", exist_ok=True)
        with open(output_path, "w") as f:
            f.write(html)

    return html