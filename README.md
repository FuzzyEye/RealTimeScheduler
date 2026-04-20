# RealTimeScheduler

RealTimeScheduler is a Python simulator for single-core real-time scheduling research and teaching.  
It runs event-driven scheduling on **discrete integer time ticks**, supports multiple strategies, and exports timelines for console, figures, and papers (including TikZ).

## Current Capabilities

- Multiple built-in strategies in one framework: `edf`, `llf`, `llf_threshold`, `rms`, `dms`, `fcfs`, `rr`, `hybrid_edf_llf`
- Discrete-time simulation (`start`, `end`, arrivals, period, deadline, execution, quantum are treated as integers)
- Event trace with arrivals, dispatch, preemption, completion, deadline and deadline miss
- Metrics: CPU utilization, throughput, deadline miss count, response/waiting time stats, lateness, context switches
- Timeline outputs:
  - terminal ASCII Gantt
  - PNG
  - SVG
  - HTML
  - TikZ (academic style, deadline arrows, missed-deadline cross marker)
- Report export: JSON / CSV / Markdown
- Strategy comparison mode (`--strategy all`)

## Quick Start

```bash
# Run with default config
python main.py --config config/tasks.yaml

# Run a specific strategy
python main.py --config config/tasks.yaml --strategy edf --start 0 --end 24

# Compare all configured strategies
python main.py --config config/tasks.yaml --strategy all

# List strategies from config
python main.py --config config/tasks.yaml --list-strategies

# Export timeline figures
python main.py -c config/tasks.yaml -o tikz --output-file schedule.tex
python main.py -c config/tasks.yaml -o png --output-file schedule.png
python main.py -c config/tasks.yaml --export-svg output/schedule.svg
python main.py -c config/tasks.yaml --export-html output/schedule.html

# Export metrics
python main.py -c config/tasks.yaml --export-json output/result.json
python main.py -c config/tasks.yaml --export-csv output/result.csv
```

## CLI Arguments

- `--config, -c`: YAML config path (default `config/tasks.yaml`)
- `--strategy, -s`: strategy name, or `all`
- `--start`: simulation start tick (integer)
- `--end`: simulation end tick (integer)
- `--list-strategies`: print strategy list and exit
- `--output, -o`: `console | png | tikz | all`
- `--output-file`: output filename used by `png/tikz`
- `--width`: console gantt width
- `--verbose`, `--debug`: extra logs
- `--export-json`, `--export-csv`, `--export-svg`, `--export-html`: extra export files

## Config File (`config/tasks.yaml`)

The config has three top-level sections: `tasks`, `simulation`, `strategies`.

### 1) `tasks` section

Each item describes one task template.

```yaml
tasks:
  - name: T1
    period: 4
    execution_time: 1
    deadline: 4
    priority: 1
    arrival_time: 0
    value: 10
```

Supported fields:

- `name` (string, required): task identifier
- `execution_time` (int, required): required CPU time per instance
- `period` (int, optional): periodic task period; if omitted, task is treated as aperiodic
- `deadline` (int, optional): relative deadline; if omitted and `period` exists, uses period as deadline
- `priority` (int, optional, default `0`): used by fixed-priority strategies
- `arrival_time` (int, optional, default `0`): first release tick
- `value` (optional): reserved for value-aware policies/templates

### 2) `simulation` section

```yaml
simulation:
  start: 0
  end: 24
  strategy: edf
  params: {}
```

Supported fields:

- `start` (int): simulation start tick
- `end` (int): simulation end tick (must be `> start`)
- `strategy` (string): default strategy name when CLI `--strategy` is not specified
- `params` (dict): runtime parameters passed to selected strategy/policy (numeric values are normalized to int)

### 3) `strategies` section

Each strategy entry defines a runnable strategy in registry.

```yaml
strategies:
  - name: edf
    type: dynamic
    selector: earliest_deadline
    description: "Earliest Deadline First"
    params: {}
```

Supported fields:

- `name` (string, required): strategy id used by `--strategy`
- `type` (string, required): strategy class type (`dynamic`, `fixed_priority`, `queue`, `round_robin`, `conditional`, ...)
- `description` (string, optional): shown in list output
- `selector` (string, optional): selector function name for selection-based types
- `fallback` (string, optional): fallback strategy name
- `priority_key` (string, optional): key for fixed-priority sort (e.g. `period`, `deadline`)
- `condition` (dict, optional): condition definition for conditional strategy
- `true_branch` / `false_branch` (string, optional): branch strategy names
- `params` (dict, optional): strategy-specific parameters (e.g. RR quantum, LLF threshold)
- `module` / `class_name` (string, optional): for custom strategy loading

## Example Config (Current Project)

```yaml
tasks:
  - name: T1
    period: 4
    execution_time: 1
    deadline: 4
    priority: 1
  - name: T2
    period: 6
    execution_time: 2
    deadline: 6
    priority: 2
  - name: T3
    period: 8
    execution_time: 3
    deadline: 8
    priority: 3

simulation:
  start: 0
  end: 24
  strategy: edf
  params: {}
```

## TikZ Output Notes (Academic Figure)

Current TikZ exporter includes:

- per-task horizontal timelines with arrow heads
- gray pulse blocks for execution intervals
- sparse tick labels for readability
- upward arrows for each instance deadline
- cross marker (`×`) on deadline arrow for missed instances

This style is suitable for direct use in papers with minor typography adjustments.

## Project Structure

```text
src/
├── app/                # CLI and app orchestration
├── core/               # task/config/registry models
├── sim/                # simulation engine and event models
├── render/             # console + figure exporters
├── policy/             # built-in scheduling policies
├── formatters.py       # console formatting
├── reports.py          # JSON/CSV/Markdown exporters
└── plugins.py          # plugin loader
```

## License

MIT
