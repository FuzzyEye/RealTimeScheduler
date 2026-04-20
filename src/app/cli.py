from __future__ import annotations

import argparse


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Real-Time Scheduling Simulator",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py --config config/tasks.yaml
  python main.py --config config/tasks.yaml --strategy rms --start 0 --end 24
  python main.py --config config/tasks.yaml --strategy all
  python main.py --config config/tasks.yaml --list-strategies
  python main.py -c config/tasks.yaml -o png -s edf
  python main.py -c config/tasks.yaml -o tikz --output-file my_schedule.tex
  python main.py -c config/tasks.yaml -o all --output-file results.png
        """,
    )
    parser.add_argument("--config", "-c", default="config/tasks.yaml", help="Path to YAML config file")
    parser.add_argument("--strategy", "-s", help="Scheduling strategy to use (overrides config)")
    parser.add_argument("--start", type=int, help="Simulation start time (integer, overrides config)")
    parser.add_argument("--end", type=int, help="Simulation end time (integer, overrides config)")
    parser.add_argument("--list-strategies", action="store_true", help="List available strategies and exit")
    parser.add_argument("--width", type=int, default=70, help="Gantt chart width (default: 70)")
    parser.add_argument(
        "--output",
        "-o",
        choices=["console", "png", "tikz", "all"],
        default="console",
        help="Output format: console (ASCII), png (image), tikz (LaTeX code), all (default: console)",
    )
    parser.add_argument("--output-file", help="Output file path (default: schedule.png / schedule.tex)")
    parser.add_argument("--verbose", "-v", action="store_true", help="Enable verbose/debug output")
    parser.add_argument("--debug", action="store_true", help="Enable detailed debug output")
    parser.add_argument("--export-json", help="Export results to JSON file")
    parser.add_argument("--export-csv", help="Export results to CSV file")
    parser.add_argument("--export-svg", help="Export results to SVG file")
    parser.add_argument("--export-html", help="Export results to interactive HTML file")
    return parser

