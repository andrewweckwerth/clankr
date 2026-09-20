#!/usr/bin/env python3
"""Turn a benchmark run's resource samples into a portable HTML report.

The script intentionally has no third-party dependencies. It reads the ignored
result files created by the benchmark harness and writes ``analysis.html`` plus
``analysis.json`` beside them, so results can be opened locally or attached to
a comparison without a notebook, database, or metrics service.
"""

from __future__ import annotations

import argparse
import html
import json
import math
import re
import statistics
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any


SERVICE_NAMES = ("demucs", "orchestrator", "db", "redis", "minio", "minio_init", "benchmark-runner")
COLORS = ("#0f62fe", "#6929c4", "#007d79", "#ff832b", "#da1e28", "#198038", "#525252")


def read_ndjson(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for number, line in enumerate(path.read_text().splitlines(), start=1):
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError as error:
            raise ValueError(f"{path}:{number} is not JSON: {error}") from error
        if isinstance(value, dict):
            rows.append(value)
    return rows


def parse_timestamp(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def parse_cpu(value: object) -> float | None:
    if not isinstance(value, str) or not value.endswith("%"):
        return None
    try:
        return float(value[:-1])
    except ValueError:
        return None


def parse_mib(value: object) -> float | None:
    """Parse the used half of Docker's human-readable ``MemUsage`` field."""
    if not isinstance(value, str):
        return None
    used = value.split(" / ", 1)[0].strip()
    match = re.fullmatch(r"([0-9.]+)\s*(B|KiB|MiB|GiB|TiB)", used)
    if not match:
        return None
    amount, unit = match.groups()
    multipliers = {"B": 1 / (1024 * 1024), "KiB": 1 / 1024, "MiB": 1, "GiB": 1024, "TiB": 1024 * 1024}
    return float(amount) * multipliers[unit]


def service_name(container_name: object) -> str:
    name = str(container_name)
    if "-benchmark-runner-" in name:
        return "benchmark-runner"
    for service in SERVICE_NAMES:
        if re.search(rf"-{re.escape(service)}-\d+$", name):
            return service
    return name.rsplit("-", 1)[0]


def percentile(values: list[float], fraction: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    index = (len(ordered) - 1) * fraction
    lower = math.floor(index)
    upper = math.ceil(index)
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (index - lower)


def grouped_series(rows: list[dict[str, Any]], field: str, parser: Any) -> dict[str, list[tuple[datetime, float]]]:
    grouped: dict[tuple[str, datetime], list[float]] = defaultdict(list)
    for row in rows:
        try:
            timestamp = parse_timestamp(str(row["timestamp"]))
        except (KeyError, TypeError, ValueError):
            continue
        value = parser(row.get(field))
        if value is not None:
            grouped[(service_name(row.get("Name", "unknown")), timestamp)].append(value)
    series: dict[str, list[tuple[datetime, float]]] = defaultdict(list)
    for (service, timestamp), values in grouped.items():
        # CPU and memory are summed: two Demucs replicas should visibly consume
        # about twice the aggregate capacity of one replica.
        series[service].append((timestamp, sum(values)))
    return {service: sorted(points) for service, points in series.items()}


def seconds_from(start: datetime, timestamp: datetime) -> float:
    return (timestamp - start).total_seconds()


def time_label(seconds: float) -> str:
    seconds = max(0, round(seconds))
    return f"{seconds // 60}:{seconds % 60:02d}"


def svg_line_chart(
    title: str,
    y_label: str,
    series: dict[str, list[tuple[datetime, float]]],
    start: datetime,
) -> str:
    width, height = 1000, 370
    left, right, top, bottom = 76, 24, 44, 58
    plot_width, plot_height = width - left - right, height - top - bottom
    all_points = [point for points in series.values() for point in points]
    if not all_points:
        return f"<section><h2>{html.escape(title)}</h2><p>No samples were recorded.</p></section>"
    max_x = max(seconds_from(start, point[0]) for point in all_points)
    max_x = max(max_x, 1)
    max_y = max(point[1] for point in all_points)
    max_y = max(max_y * 1.1, 1)

    def x(value: float) -> float:
        return left + plot_width * value / max_x

    def y(value: float) -> float:
        return top + plot_height * (1 - value / max_y)

    output = [f'<section><h2>{html.escape(title)}</h2><svg viewBox="0 0 {width} {height}" role="img" aria-label="{html.escape(title)}">']
    output.append(f'<rect x="{left}" y="{top}" width="{plot_width}" height="{plot_height}" class="frame"/>')
    for index in range(6):
        fraction = index / 5
        value = max_y * (1 - fraction)
        ypos = top + plot_height * fraction
        output.append(f'<line x1="{left}" y1="{ypos:.1f}" x2="{width - right}" y2="{ypos:.1f}" class="grid"/>')
        output.append(f'<text x="{left - 9}" y="{ypos + 4:.1f}" text-anchor="end" class="tick">{value:.0f}</text>')
    for index in range(6):
        elapsed = max_x * index / 5
        xpos = x(elapsed)
        output.append(f'<text x="{xpos:.1f}" y="{height - 34}" text-anchor="middle" class="tick">{time_label(elapsed)}</text>')
    for index, (service, points) in enumerate(sorted(series.items())):
        color = COLORS[index % len(COLORS)]
        path = " ".join(
            f"{'M' if position == 0 else 'L'} {x(seconds_from(start, timestamp)):.1f} {y(value):.1f}"
            for position, (timestamp, value) in enumerate(points)
        )
        output.append(f'<path d="{path}" stroke="{color}" class="series"/>')
        legend_x = left + (index % 4) * 165
        legend_y = 22 + (index // 4) * 16
        output.append(f'<line x1="{legend_x}" y1="{legend_y}" x2="{legend_x + 18}" y2="{legend_y}" stroke="{color}" class="legend-line"/>')
        output.append(f'<text x="{legend_x + 24}" y="{legend_y + 4}" class="legend">{html.escape(service)}</text>')
    output.append(f'<text x="{left + plot_width / 2:.1f}" y="{height - 8}" text-anchor="middle" class="axis">Elapsed time (mm:ss)</text>')
    output.append(f'<text x="18" y="{top + plot_height / 2:.1f}" text-anchor="middle" class="axis" transform="rotate(-90 18 {top + plot_height / 2:.1f})">{html.escape(y_label)}</text>')
    output.append("</svg></section>")
    return "\n".join(output)


def format_value(value: float | None) -> str:
    return "—" if value is None else f"{value:.1f}"


def analyze(run_dir: Path) -> dict[str, Any]:
    stats = read_ndjson(run_dir / "docker-stats.ndjson")
    manifest_path = run_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_text()) if manifest_path.exists() else {}
    cpu_series = grouped_series(stats, "CPUPerc", parse_cpu)
    memory_series = grouped_series(stats, "MemUsage", parse_mib)
    all_times = [timestamp for points in cpu_series.values() for timestamp, _ in points]
    if not all_times:
        raise ValueError(f"No usable Docker CPU samples in {run_dir / 'docker-stats.ndjson'}")
    start = min(all_times)
    service_summary: dict[str, dict[str, float | int | None]] = {}
    for service in sorted(cpu_series):
        cpu_values = [value for _, value in cpu_series[service]]
        memory_values = [value for _, value in memory_series.get(service, [])]
        service_summary[service] = {
            "samples": len(cpu_values),
            "cpu_average_percent": round(statistics.fmean(cpu_values), 1),
            "cpu_p95_percent": round(percentile(cpu_values, 0.95) or 0, 1),
            "cpu_max_percent": round(max(cpu_values), 1),
            "memory_average_mib": round(statistics.fmean(memory_values), 1) if memory_values else None,
            "memory_max_mib": round(max(memory_values), 1) if memory_values else None,
        }
    return {
        "run_id": manifest.get("run_id", run_dir.name),
        "host": manifest.get("host"),
        "demucs_replicas": manifest.get("demucs_replicas"),
        "samples_started_at": start.isoformat(),
        "samples_ended_at": max(all_times).isoformat(),
        "duration_seconds": round((max(all_times) - start).total_seconds(), 1),
        "container_samples": len(stats),
        "service_summary": service_summary,
    }


def render_html(analysis: dict[str, Any], run_dir: Path) -> str:
    stats = read_ndjson(run_dir / "docker-stats.ndjson")
    cpu_series = grouped_series(stats, "CPUPerc", parse_cpu)
    memory_series = grouped_series(stats, "MemUsage", parse_mib)
    start = min(timestamp for points in cpu_series.values() for timestamp, _ in points)
    rows = []
    for service, summary in analysis["service_summary"].items():
        rows.append(
            "<tr>"
            f"<td>{html.escape(service)}</td><td>{summary['samples']}</td>"
            f"<td>{format_value(summary['cpu_average_percent'])}</td>"
            f"<td>{format_value(summary['cpu_p95_percent'])}</td>"
            f"<td>{format_value(summary['cpu_max_percent'])}</td>"
            f"<td>{format_value(summary['memory_average_mib'])}</td>"
            f"<td>{format_value(summary['memory_max_mib'])}</td></tr>"
        )
    return f"""<!doctype html>
<html lang=\"en\"><head><meta charset=\"utf-8\"><meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">
<title>Clankr benchmark analysis: {html.escape(str(analysis['run_id']))}</title>
<style>
body {{ font-family: system-ui, sans-serif; margin: 0 auto; max-width: 1040px; padding: 28px; color: #17202a; background: #fff; }}
h1 {{ margin-bottom: 4px; }} .muted {{ color: #52616b; }} section {{ margin: 30px 0; }}
svg {{ width: 100%; height: auto; border: 1px solid #c9d2d8; background: #fff; }} .frame {{ fill: none; stroke: #8c9aa5; }}
.grid {{ stroke: #e6ebee; }} .series {{ fill: none; stroke-width: 2; }} .tick, .legend {{ font-size: 12px; fill: #3d4b53; }}
.axis {{ font-size: 13px; fill: #17202a; }} .legend-line {{ stroke-width: 3; }} .marker {{ stroke: #d12771; stroke-width: 1.5; stroke-dasharray: 4 3; }} .marker-label {{ font-size: 11px; fill: #a2195b; }}
table {{ border-collapse: collapse; width: 100%; font-variant-numeric: tabular-nums; }} th, td {{ padding: 8px; border-bottom: 1px solid #d8e0e5; text-align: right; }} th:first-child, td:first-child {{ text-align: left; }} th {{ background: #f2f6f8; }}
.note {{ border-left: 4px solid #0f62fe; padding: 10px 14px; background: #edf5ff; }} code {{ background: #f2f4f5; padding: 2px 4px; }}
</style></head><body>
<h1>Clankr benchmark analysis</h1>
<p class=\"muted\">Run <code>{html.escape(str(analysis['run_id']))}</code> · {analysis['demucs_replicas']} Demucs replica(s) · {analysis['duration_seconds']:.0f}s sampled · {analysis['container_samples']} container samples</p>
{svg_line_chart('Aggregate container CPU usage', 'CPU usage (%)', cpu_series, start)}
{svg_line_chart('Aggregate container memory usage', 'Memory (MiB)', memory_series, start)}
<section><h2>Resource summary</h2><table><thead><tr><th>Service</th><th>Samples</th><th>CPU avg (%)</th><th>CPU p95 (%)</th><th>CPU max (%)</th><th>Memory avg (MiB)</th><th>Memory max (MiB)</th></tr></thead><tbody>{''.join(rows)}</tbody></table></section>
<p class=\"muted\">CPU values are Docker-reported aggregate usage. A multi-threaded or emulated container can exceed 100%.</p>
</body></html>"""


def main() -> None:
    parser = argparse.ArgumentParser(description="Create an HTML resource analysis for one benchmark result directory.")
    parser.add_argument("--run", required=True, help="Path to benchmarks/results/<run-id>")
    args = parser.parse_args()
    run_dir = Path(args.run).resolve()
    analysis = analyze(run_dir)
    (run_dir / "analysis.json").write_text(json.dumps(analysis, indent=2) + "\n")
    (run_dir / "analysis.html").write_text(render_html(analysis, run_dir))
    print(f"Wrote {run_dir / 'analysis.html'}")
    print(f"Wrote {run_dir / 'analysis.json'}")


if __name__ == "__main__":
    main()
