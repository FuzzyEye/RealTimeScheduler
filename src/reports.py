import json
import csv
from typing import Dict, List, Any, Optional
from io import StringIO


class ReportExporter:
    @staticmethod
    def to_json(results: Dict[str, Any], pretty: bool = True) -> str:
        return json.dumps(results, indent=2 if pretty else None, default=str)

    @staticmethod
    def to_csv(results: Dict[str, Any]) -> str:
        output = StringIO()
        writer = csv.writer(output)

        writer.writerow([
            "Strategy",
            "CPU Utilization (%)",
            "Throughput",
            "Deadline Misses",
            "Avg Response Time",
            "Max Response Time",
            "Min Response Time",
            "Response Time Jitter",
            "Avg Waiting Time",
            "Max Waiting Time",
            "Preemptions",
            "Context Switches",
            "Idle Time",
            "Lateness",
        ])

        for name, result in results.items():
            writer.writerow([
                name,
                f"{result.cpu_utilization():.2f}",
                result.throughput(),
                result.deadline_miss_count(),
                f"{result.response_time_avg():.3f}",
                f"{result.response_time_max():.3f}",
                f"{result.response_time_min():.3f}",
                f"{result.response_time_jitter():.3f}",
                f"{result.waiting_time_avg():.3f}",
                f"{result.waiting_time_max():.3f}",
                result.preemption_count,
                result.context_switch_count,
                f"{result.cpu_idle_time:.2f}",
                f"{result.lateness():.3f}",
            ])

        return output.getvalue()

    @staticmethod
    def to_markdown(results: Dict[str, Any]) -> str:
        lines = []
        lines.append(f"# Scheduling Strategy Comparison")
        lines.append("")
        lines.append(f"## Summary")
        lines.append("")
        lines.append(f"| Strategy | CPU% | Done | Miss | Avg RT |")
        lines.append(f"|----------|-----|------|-----|-------|")

        for name, result in results.items():
            lines.append(f"| {name} | {result.cpu_utilization():.1f} | {result.throughput()} | {result.deadline_miss_count()} | {result.response_time_avg():.3f} |")

        lines.append("")
        lines.append(f"## Detailed Metrics")
        lines.append("")

        for name, result in results.items():
            lines.append(f"### {name}")
            lines.append("")
            lines.append(f"- **CPU Utilization**: {result.cpu_utilization():.2f}%")
            lines.append(f"- **Throughput**: {result.throughput()} tasks")
            lines.append(f"- **Deadline Misses**: {result.deadline_miss_count()}")
            lines.append(f"- **Response Time (avg/max/min/jitter)**: {result.response_time_avg():.3f} / {result.response_time_max():.3f} / {result.response_time_min():.3f} / {result.response_time_jitter():.3f}")
            lines.append(f"- **Waiting Time (avg/max)**: {result.waiting_time_avg():.3f} / {result.waiting_time_max():.3f}")
            lines.append(f"- **Preemptions**: {result.preemption_count}")
            lines.append(f"- **Context Switches**: {result.context_switch_count}")
            lines.append(f"- **Idle Time**: {result.cpu_idle_time:.2f}")
            lines.append(f"- **Lateness**: {result.lateness():.3f}")
            lines.append("")

        return "\n".join(lines)

    @staticmethod
    def save_json(results: Dict[str, Any], output_path: str) -> None:
        output = format_results_as_dict(results)
        with open(output_path, "w") as f:
            json.dump(output, f, indent=2)

    @staticmethod
    def save_csv(results: Dict[str, Any], output_path: str) -> None:
        with open(output_path, "w", newline="") as f:
            f.write(ReportExporter.to_csv(results))

    @staticmethod
    def save_markdown(results: Dict[str, Any], output_path: str) -> None:
        with open(output_path, "w") as f:
            f.write(ReportExporter.to_markdown(results))


def export_results(
    results: Dict[str, Any],
    output_path: str,
    format: str = "json"
) -> None:
    if format == "json":
        ReportExporter.save_json(results, output_path)
    elif format == "csv":
        ReportExporter.save_csv(results, output_path)
    elif format == "markdown":
        ReportExporter.save_markdown(results, output_path)
    else:
        raise ValueError(f"Unknown format: {format}")


def format_results_as_dict(results: Dict[str, Any]) -> Dict[str, Dict]:
    output = {}
    for name, result in results.items():
        output[name] = {
            "cpu_utilization": result.cpu_utilization(),
            "throughput": result.throughput(),
            "deadline_misses": result.deadline_miss_count(),
            "avg_response_time": result.response_time_avg(),
            "max_response_time": result.response_time_max(),
            "min_response_time": result.response_time_min(),
            "response_time_jitter": result.response_time_jitter(),
            "avg_waiting_time": result.waiting_time_avg(),
            "max_waiting_time": result.waiting_time_max(),
            "preemptions": result.preemption_count,
            "context_switches": result.context_switch_count,
            "idle_time": result.cpu_idle_time,
            "lateness": result.lateness(),
        }
    return output