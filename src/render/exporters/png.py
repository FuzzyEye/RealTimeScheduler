from __future__ import annotations

from src.sim.scheduler import SchedulingResult
from src.render.exporters.common import build_segments, get_color


def to_png(
    result: SchedulingResult,
    strategy_name: str,
    output_path: str = "output/schedule.png",
    figsize: tuple = (14, 5),
    dpi: int = 150,
) -> None:
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import matplotlib.patches as mpatches
    except ImportError:
        raise ImportError("matplotlib is required for PNG output. Install it with: pip install matplotlib")

    segments = build_segments(result)
    if not segments:
        return

    total = int(result.total_time)
    row_labels = list(dict.fromkeys(name for _, _, name in segments))
    num_rows = len(row_labels)

    fig_h = max(figsize[1], num_rows * 0.75 + 2.2)
    fig, ax = plt.subplots(figsize=(figsize[0], fig_h))
    fig.patch.set_facecolor("#FFFFFF")
    ax.set_facecolor("#FFFFFF")

    for start, end, name in segments:
        y_idx = row_labels.index(name)
        color = get_color(name)
        duration = end - start
        rect = mpatches.FancyBboxPatch(
            (start, y_idx - 0.38),
            duration,
            0.76,
            boxstyle="round,pad=0.02",
            facecolor=color,
            edgecolor="#3A3A3A",
            linewidth=0.8,
            alpha=0.95,
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
                fontweight="normal",
                color="#111111",
                zorder=4,
            )

    ax.set_xlim(-0.5, total + 1)
    ax.set_ylim(-0.8, num_rows)
    ax.set_yticks(range(num_rows))
    ax.set_yticklabels(row_labels, fontsize=9, fontfamily="serif")
    ax.set_xticks(list(range(0, total + 2)))
    ax.set_xlabel("Time (ticks)", fontsize=10, color="#111111", fontfamily="serif")
    ax.set_ylabel("Task", fontsize=10, color="#111111", fontfamily="serif")
    ax.set_title(
        f"{strategy_name.upper()} Scheduling Timeline  |  Horizon: {total}  |  "
        f"Done: {result.throughput()}  |  Miss: {result.deadline_miss_count()}  |  "
        f"CPU: {int(round(result.cpu_utilization()))}%",
        fontsize=11,
        fontweight="bold",
        color="#111111",
        pad=12,
        fontfamily="serif",
    )
    ax.tick_params(colors="#333333", labelsize=9)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["bottom"].set_color("#222222")
    ax.spines["left"].set_color("#222222")
    for spine in ax.spines.values():
        spine.set_linewidth(0.9)
    ax.grid(axis="x", color="#D0D0D0", linewidth=0.6, alpha=0.8)
    ax.grid(axis="y", color="#E5E5E5", linewidth=0.5, alpha=0.7)
    ax.axhline(y=-0.5, color="#888888", linewidth=0.7)

    legend_patches = [mpatches.Patch(facecolor=get_color(name), edgecolor="#333", label=name) for name in row_labels]
    ax.legend(
        handles=legend_patches,
        loc="upper right",
        ncol=min(len(legend_patches), 8),
        fontsize=8,
        framealpha=1.0,
        labelcolor="#111111",
        facecolor="#FFFFFF",
        edgecolor="#B0B0B0",
    )

    plt.tight_layout()
    plt.savefig(output_path, dpi=dpi, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close()

