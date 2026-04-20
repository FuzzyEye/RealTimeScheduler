from __future__ import annotations

import os
from typing import Optional

from src.sim.scheduler import SchedulingResult
from src.render.exporters.common import build_segments, get_color


def to_html(
    result: SchedulingResult,
    strategy_name: str,
    output_path: Optional[str] = None,
    width: int = 900,
    height: int = 400,
) -> str:
    segments = build_segments(result)
    if not segments:
        html = "<!-- No scheduling segments -->"
        if output_path:
            with open(output_path, "w") as f:
                f.write(html)
        return html

    total = result.total_time
    margin_left, margin_right, margin_top, margin_bottom = 80, 20, 60, 40
    chart_width = width - margin_left - margin_right
    chart_height = height - margin_top - margin_bottom
    row_labels = list(dict.fromkeys(name for _, _, name in segments))
    rows = len(row_labels)
    row_height = chart_height / rows if rows > 0 else chart_height

    def time_to_x(t: float) -> float:
        return margin_left + (t / total) * chart_width

    def row_to_y(idx: int) -> float:
        return margin_top + (rows - 1 - idx) * row_height + row_height / 2

    task_data = []
    for start, end, name in segments:
        idx = row_labels.index(name)
        task_data.append(
            {"name": name, "start": start, "end": end, "duration": end - start, "y_idx": idx, "color": get_color(name)}
        )

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

    grid_lines = "".join(
        f'<line x1="{time_to_x(i * total / 10)}" y1="{margin_top}" x2="{time_to_x(i * total / 10)}" y2="{height - margin_bottom}" class="grid-line"/>'
        for i in range(11)
    )
    time_labels = "".join(
        f'<text x="{time_to_x(i * total / 10)}" y="{height - margin_bottom + 15}" text-anchor="middle" class="axis-text">{i * total / 10:.1f}</text>'
        for i in range(11)
    )
    y_labels = "".join(
        f'<text x="{margin_left - 10}" y="{row_to_y(idx) + 3}" text-anchor="end" class="axis-text">{label}</text>'
        for idx, label in enumerate(row_labels)
    )
    rects = "".join(
        f'<rect x="{time_to_x(d["start"])}" y="{row_to_y(d["y_idx"]) - row_height * 0.4}" width="{time_to_x(d["end"]) - time_to_x(d["start"])}" height="{row_height * 0.8}" fill="{d["color"]}" class="segment-rect" data-name="{d["name"]}" data-start="{d["start"]:.2f}" data-end="{d["end"]:.2f}" data-duration="{d["duration"]:.2f}"/>'
        for d in task_data
    )
    legend_items = "".join(
        f'<div class="legend-item"><div class="legend-color" style="background: {d["color"]}"></div><span>{d["name"]}</span></div>'
        for d in unique_tasks
    )

    html = f"""<!DOCTYPE html>
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
            seg.addEventListener('mouseenter', () => {{
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
</html>"""

    if output_path:
        os.makedirs(os.path.dirname(output_path) if os.path.dirname(output_path) else "output", exist_ok=True)
        with open(output_path, "w") as f:
            f.write(html)
    return html

