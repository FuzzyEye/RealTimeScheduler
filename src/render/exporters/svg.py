from __future__ import annotations

import os
from typing import Optional

from src.sim.scheduler import SchedulingResult
from src.render.exporters.common import build_segments, get_color


def to_svg(
    result: SchedulingResult,
    strategy_name: str,
    output_path: Optional[str] = None,
    width: int = 800,
    height: int = 300,
) -> str:
    segments = build_segments(result)
    if not segments:
        return "<!-- No scheduling segments -->"

    total = int(result.total_time)
    margin_left, margin_right, margin_top, margin_bottom = 60, 20, 40, 30
    chart_width = width - margin_left - margin_right
    chart_height = height - margin_top - margin_bottom

    row_labels = list(dict.fromkeys(name for _, _, name in segments))
    rows = len(row_labels)
    row_height = chart_height / rows if rows > 0 else chart_height

    def time_to_x(t: float) -> float:
        return margin_left + (t / total) * chart_width

    def row_to_y(idx: int) -> float:
        return margin_top + (rows - 1 - idx) * row_height + row_height / 2

    lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        "  <defs>",
        "    <style>",
        "      .segment { stroke: #2B2B2B; stroke-width: 0.9; opacity: 0.95; }",
        "      .label { font-family: serif; font-size: 10px; fill: #333; }",
        "      .title { font-family: serif; font-size: 14px; fill: #111; font-weight: 700; }",
        "      .metric { font-family: serif; font-size: 10px; fill: #333; }",
        "      .axis { stroke: #222; stroke-width: 1; }",
        "      .grid { stroke: #dcdcdc; stroke-width: 0.8; }",
        "    </style>",
        "  </defs>",
        f'  <rect width="{width}" height="{height}" fill="#fafafa"/>',
        f'  <line x1="{margin_left}" y1="{height - margin_bottom}" x2="{width - margin_right}" y2="{height - margin_bottom}" class="axis"/>',
        f'  <line x1="{margin_left}" y1="{margin_top}" x2="{margin_left}" y2="{height - margin_bottom}" class="axis"/>',
    ]

    num_ticks = max(1, total)
    for i in range(num_ticks + 1):
        x = time_to_x(i * total / num_ticks)
        lines.append(f'  <line x1="{x}" y1="{margin_top}" x2="{x}" y2="{height - margin_bottom}" class="grid"/>')
        lines.append(f'  <text x="{x}" y="{height - 10}" text-anchor="middle" class="label">{int(i * total / num_ticks)}</text>')

    for idx, label in enumerate(row_labels):
        y = row_to_y(idx)
        lines.append(f'  <text x="{margin_left - 5}" y="{y + 3}" text-anchor="end" class="label">{label}</text>')

    for start, end, name in segments:
        y = row_to_y(row_labels.index(name))
        x1, x2 = time_to_x(start), time_to_x(end)
        lines.append(f'  <rect x="{x1}" y="{y - row_height * 0.4}" width="{x2 - x1}" height="{row_height * 0.8}" fill="{get_color(name)}" class="segment"/>')

    util = result.cpu_utilization()
    done = result.throughput()
    miss = result.deadline_miss_count()
    lines.append(f'  <text x="{margin_left}" y="20" class="title">{strategy_name.upper()} Scheduling Timeline</text>')
    lines.append(f'  <text x="{width - margin_right}" y="20" text-anchor="end" class="metric">Horizon: {total} | CPU: {int(round(util))}% | Done: {done} | Miss: {miss}</text>')
    lines.append("</svg>")

    svg_code = "\n".join(lines)
    if output_path:
        os.makedirs(os.path.dirname(output_path) if os.path.dirname(output_path) else "output", exist_ok=True)
        with open(output_path, "w") as f:
            f.write(svg_code)
    return svg_code

