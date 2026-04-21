#!/usr/bin/env python3
"""analyze_startup.py — Generate an interactive HTML startup report.

Correlates power/load metrics from monitor_power.py's JSONL log with
PHASE: markers emitted by Spotibox.__init__() and captured by journald.

Usage:
    # Auto-select most recent log, write startup_report.html
    python scripts/analyze_startup.py

    # Explicit log file and output path
    python scripts/analyze_startup.py --log /var/log/spotibox/power_20260421_120000.jsonl --output /tmp/report.html

    # Analyse a specific boot (journalctl --boot offset, default: 0 = current boot)
    python scripts/analyze_startup.py --boot 0

    # Add yourself to the systemd-journal group if journalctl access fails:
    #   sudo usermod -aG systemd-journal $USER   (then log out and back in)
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

LOG_DIR = Path("/var/log/spotibox")
DEFAULT_OUTPUT = Path("startup_report.html")


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

def _latest_log(log_dir: Path) -> Path:
    logs = sorted(log_dir.glob("power_*.jsonl"))
    if not logs:
        sys.exit(f"[analyze] No power_*.jsonl files found in {log_dir}")
    return logs[-1]


def _load_metrics(path: Path) -> list[dict]:
    records = []
    for line in path.read_text().splitlines():
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        if "_meta" in obj:
            continue   # skip header record
        records.append(obj)
    return records


def _load_phases(boot: int) -> list[dict]:
    """Fetch PHASE: log lines from journald for the given boot offset."""
    cmd = [
        "journalctl",
        f"--boot={boot}",
        "--unit=spotibox.service",
        "--output=json",
        "--no-pager",
    ]
    try:
        out = subprocess.check_output(cmd, text=True, timeout=30)
    except FileNotFoundError:
        print("[analyze] Warning: journalctl not found — phase markers unavailable", file=sys.stderr)
        return []
    except subprocess.CalledProcessError as exc:
        print(f"[analyze] Warning: journalctl error ({exc.returncode}) — phase markers unavailable", file=sys.stderr)
        return []

    phases = []
    for line in out.splitlines():
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            continue
        msg = entry.get("MESSAGE", "")
        if not msg.startswith("PHASE:"):
            continue
        # __REALTIME_TIMESTAMP is microseconds since epoch
        ts_us = int(entry.get("__REALTIME_TIMESTAMP", 0))
        ts_s = ts_us / 1_000_000
        phases.append({"ts": ts_s, "phase": msg})
    return phases


# ---------------------------------------------------------------------------
# Summary statistics
# ---------------------------------------------------------------------------

def _summarize(metrics: list[dict], phases: list[dict]) -> dict:
    if not metrics:
        return {}

    ts_list = [m["ts"] for m in metrics]
    t0 = ts_list[0]
    t_end = ts_list[-1]

    # Startup duration: from init_start phase to ready phase (if available)
    phase_ts = {p["phase"]: p["ts"] for p in phases}
    startup_s = None
    if "PHASE:init_start" in phase_ts and "PHASE:ready" in phase_ts:
        startup_s = round(phase_ts["PHASE:ready"] - phase_ts["PHASE:init_start"], 2)

    uv_now = sum(1 for m in metrics if m.get("under_voltage_now"))
    uv_occurred = any(m.get("under_voltage_occurred") for m in metrics)
    throttled_now = sum(1 for m in metrics if m.get("throttled_now"))

    temps = [m["temp_c"] for m in metrics if m.get("temp_c") is not None]
    cpus = [m["cpu_pct"] for m in metrics if m.get("cpu_pct") is not None]

    return {
        "log_duration_s": round(t_end - t0, 1),
        "startup_s": startup_s,
        "samples": len(metrics),
        "uv_now_samples": uv_now,
        "uv_occurred": uv_occurred,
        "throttled_samples": throttled_now,
        "peak_temp_c": max(temps, default=None),
        "peak_cpu_pct": max(cpus, default=None),
        "phase_count": len(phases),
    }


# ---------------------------------------------------------------------------
# HTML generation
# ---------------------------------------------------------------------------

_HTML_TEMPLATE = """\
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Spotibox Startup Report</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.3/dist/chart.umd.min.js"></script>
<style>
  body {{ font-family: system-ui, sans-serif; margin: 0; padding: 16px; background: #1a1a2e; color: #e0e0e0; }}
  h1 {{ color: #1db954; margin-bottom: 4px; }}
  .subtitle {{ color: #888; font-size: 0.85em; margin-bottom: 20px; }}
  .summary {{ display: flex; flex-wrap: wrap; gap: 12px; margin-bottom: 24px; }}
  .card {{ background: #16213e; border-radius: 8px; padding: 14px 20px; min-width: 160px; }}
  .card-label {{ font-size: 0.75em; color: #888; text-transform: uppercase; letter-spacing: .05em; }}
  .card-value {{ font-size: 1.8em; font-weight: 700; margin-top: 4px; }}
  .ok {{ color: #1db954; }}
  .warn {{ color: #f9a825; }}
  .crit {{ color: #e53935; }}
  .chart-container {{ background: #16213e; border-radius: 8px; padding: 16px; margin-bottom: 20px; }}
  .chart-container h2 {{ margin: 0 0 12px; font-size: 1em; color: #1db954; }}
  canvas {{ max-height: 260px; }}
  table {{ width: 100%; border-collapse: collapse; background: #16213e; border-radius: 8px; overflow: hidden; margin-bottom: 20px; }}
  th {{ background: #0f3460; color: #1db954; text-align: left; padding: 8px 12px; font-size: 0.8em; text-transform: uppercase; }}
  td {{ padding: 7px 12px; font-size: 0.9em; border-bottom: 1px solid #1a1a2e; }}
  tr:last-child td {{ border-bottom: none; }}
  .phase-name {{ font-family: monospace; color: #90caf9; }}
  footer {{ color: #555; font-size: 0.75em; margin-top: 24px; }}
</style>
</head>
<body>
<h1>Spotibox Startup Report</h1>
<p class="subtitle">Generated: {generated_at} &nbsp;|&nbsp; Log: {log_file}</p>

<!-- Summary cards -->
<div class="summary">
  <div class="card">
    <div class="card-label">Startup Duration</div>
    <div class="card-value {startup_cls}">{startup_val}</div>
  </div>
  <div class="card">
    <div class="card-label">Under-Voltage (now) Samples</div>
    <div class="card-value {uv_now_cls}">{uv_now_val}</div>
  </div>
  <div class="card">
    <div class="card-label">Under-Voltage Ever Occurred</div>
    <div class="card-value {uv_occurred_cls}">{uv_occurred_val}</div>
  </div>
  <div class="card">
    <div class="card-label">Throttled Samples</div>
    <div class="card-value {throttled_cls}">{throttled_val}</div>
  </div>
  <div class="card">
    <div class="card-label">Peak Temperature</div>
    <div class="card-value {temp_cls}">{temp_val}</div>
  </div>
  <div class="card">
    <div class="card-label">Peak CPU</div>
    <div class="card-value">{cpu_val}</div>
  </div>
  <div class="card">
    <div class="card-label">Log Duration</div>
    <div class="card-value">{log_duration_val}s</div>
  </div>
  <div class="card">
    <div class="card-label">Phases Detected</div>
    <div class="card-value {phases_cls}">{phases_val}</div>
  </div>
</div>

<!-- Chart 1: CPU & Load -->
<div class="chart-container">
  <h2>CPU % &amp; 1-min Load Average</h2>
  <canvas id="cpuChart"></canvas>
</div>

<!-- Chart 2: Temperature -->
<div class="chart-container">
  <h2>Temperature (°C)</h2>
  <canvas id="tempChart"></canvas>
</div>

<!-- Chart 3: Throttle flags -->
<div class="chart-container">
  <h2>Throttle Flags (Under-Voltage / Throttled)</h2>
  <canvas id="throttleChart"></canvas>
</div>

<!-- Chart 4: Memory -->
<div class="chart-container">
  <h2>Memory Used (MB)</h2>
  <canvas id="memChart"></canvas>
</div>

<!-- Phase timeline table -->
<h2 style="color:#1db954;">Phase Timeline</h2>
{phase_table}

<footer>Data sampled at {interval}s intervals &nbsp;|&nbsp; {samples} total samples</footer>

<script>
const METRICS = {metrics_json};
const PHASES  = {phases_json};

// Relative timestamps (seconds from first sample)
const t0 = METRICS.length ? METRICS[0].ts : 0;
const labels = METRICS.map(m => +((m.ts - t0).toFixed(2)));

// Phase annotation vertical lines shared across charts
function phaseAnnotations(chartHeight) {{
  return PHASES.map(p => ({{
    type: 'line',
    xMin: +((p.ts - t0).toFixed(2)),
    xMax: +((p.ts - t0).toFixed(2)),
    borderColor: 'rgba(255, 213, 79, 0.55)',
    borderWidth: 1,
    borderDash: [4, 3],
    label: {{
      content: p.phase.replace('PHASE:', ''),
      display: true,
      position: 'start',
      color: '#ffd54f',
      font: {{ size: 9 }},
      yAdjust: -4,
    }},
  }}));
}}

const commonOpts = (yLabel, extra) => ({{
  responsive: true,
  maintainAspectRatio: true,
  animation: false,
  plugins: {{
    legend: {{ labels: {{ color: '#ccc', boxWidth: 12 }} }},
    tooltip: {{ mode: 'index', intersect: false }},
  }},
  scales: {{
    x: {{
      type: 'linear',
      title: {{ display: true, text: 'Seconds since log start', color: '#888' }},
      ticks: {{ color: '#888', maxTicksLimit: 12 }},
      grid: {{ color: 'rgba(255,255,255,0.05)' }},
    }},
    y: {{
      title: {{ display: true, text: yLabel, color: '#888' }},
      ticks: {{ color: '#888' }},
      grid: {{ color: 'rgba(255,255,255,0.05)' }},
    }},
    ...extra,
  }},
}});

// ---- CPU Chart ----
new Chart(document.getElementById('cpuChart'), {{
  type: 'line',
  data: {{
    datasets: [
      {{
        label: 'CPU %',
        data: METRICS.map(m => ({{ x: +((m.ts - t0).toFixed(2)), y: m.cpu_pct }})),
        borderColor: '#1db954',
        backgroundColor: 'rgba(29,185,84,0.08)',
        borderWidth: 1.5,
        pointRadius: 0,
        fill: true,
        yAxisID: 'y',
      }},
      {{
        label: 'Load (1m)',
        data: METRICS.map(m => ({{ x: +((m.ts - t0).toFixed(2)), y: m.load1 }})),
        borderColor: '#90caf9',
        backgroundColor: 'transparent',
        borderWidth: 1.5,
        pointRadius: 0,
        borderDash: [5, 3],
        yAxisID: 'y2',
      }},
      ...PHASES.map(p => ({{
        label: p.phase.replace('PHASE:', ''),
        data: [{{ x: +((p.ts - t0).toFixed(2)), y: 0 }}, {{ x: +((p.ts - t0).toFixed(2)), y: 100 }}],
        borderColor: 'rgba(255,213,79,0.4)',
        borderWidth: 1,
        borderDash: [4, 3],
        pointRadius: 0,
        showInLegend: false,
        yAxisID: 'y',
      }})),
    ],
  }},
  options: {{
    ...commonOpts('CPU %', {{
      y2: {{
        type: 'linear',
        position: 'right',
        title: {{ display: true, text: 'Load avg', color: '#888' }},
        ticks: {{ color: '#888' }},
        grid: {{ drawOnChartArea: false }},
      }},
    }}),
  }},
}});

// ---- Temp Chart ----
new Chart(document.getElementById('tempChart'), {{
  type: 'line',
  data: {{
    datasets: [
      {{
        label: 'Temp °C',
        data: METRICS.map(m => ({{ x: +((m.ts - t0).toFixed(2)), y: m.temp_c }})),
        borderColor: '#ff7043',
        backgroundColor: 'rgba(255,112,67,0.08)',
        borderWidth: 1.5,
        pointRadius: 0,
        fill: true,
      }},
      {{
        label: 'Throttle onset (70°C)',
        data: [
          {{ x: labels[0], y: 70 }},
          {{ x: labels[labels.length - 1], y: 70 }},
        ],
        borderColor: 'rgba(229,57,53,0.5)',
        borderWidth: 1,
        borderDash: [6, 4],
        pointRadius: 0,
      }},
      ...PHASES.map(p => ({{
        label: p.phase.replace('PHASE:', ''),
        data: [{{ x: +((p.ts - t0).toFixed(2)), y: 0 }}, {{ x: +((p.ts - t0).toFixed(2)), y: 100 }}],
        borderColor: 'rgba(255,213,79,0.4)',
        borderWidth: 1,
        borderDash: [4, 3],
        pointRadius: 0,
        yAxisID: 'y',
      }})),
    ],
  }},
  options: commonOpts('°C', {{}}),
}});

// ---- Throttle Chart ----
new Chart(document.getElementById('throttleChart'), {{
  type: 'line',
  data: {{
    datasets: [
      {{
        label: 'Under-voltage NOW (bit 0)',
        data: METRICS.map(m => ({{ x: +((m.ts - t0).toFixed(2)), y: m.under_voltage_now }})),
        borderColor: '#e53935',
        backgroundColor: 'rgba(229,57,53,0.25)',
        borderWidth: 1,
        pointRadius: 0,
        fill: true,
        stepped: true,
      }},
      {{
        label: 'Throttled NOW (bit 2)',
        data: METRICS.map(m => ({{ x: +((m.ts - t0).toFixed(2)), y: m.throttled_now }})),
        borderColor: '#ff7043',
        backgroundColor: 'rgba(255,112,67,0.15)',
        borderWidth: 1,
        pointRadius: 0,
        fill: true,
        stepped: true,
      }},
      {{
        label: 'Under-voltage OCCURRED (bit 16)',
        data: METRICS.map(m => ({{ x: +((m.ts - t0).toFixed(2)), y: m.under_voltage_occurred }})),
        borderColor: '#ffd54f',
        backgroundColor: 'rgba(255,213,79,0.1)',
        borderWidth: 1,
        borderDash: [5, 3],
        pointRadius: 0,
        fill: false,
        stepped: true,
      }},
    ],
  }},
  options: {{
    ...commonOpts('Flag active (1=yes)', {{}}),
    scales: {{
      x: {{
        type: 'linear',
        title: {{ display: true, text: 'Seconds since log start', color: '#888' }},
        ticks: {{ color: '#888', maxTicksLimit: 12 }},
        grid: {{ color: 'rgba(255,255,255,0.05)' }},
      }},
      y: {{
        min: 0,
        max: 1.2,
        title: {{ display: true, text: 'Flag active (1=yes)', color: '#888' }},
        ticks: {{ color: '#888', stepSize: 1 }},
        grid: {{ color: 'rgba(255,255,255,0.05)' }},
      }},
    }},
  }},
}});

// ---- Memory Chart ----
new Chart(document.getElementById('memChart'), {{
  type: 'line',
  data: {{
    datasets: [
      {{
        label: 'Used MB',
        data: METRICS.map(m => ({{ x: +((m.ts - t0).toFixed(2)), y: m.mem_used_mb }})),
        borderColor: '#ab47bc',
        backgroundColor: 'rgba(171,71,188,0.12)',
        borderWidth: 1.5,
        pointRadius: 0,
        fill: true,
      }},
      ...PHASES.map(p => ({{
        label: p.phase.replace('PHASE:', ''),
        data: [{{ x: +((p.ts - t0).toFixed(2)), y: 0 }}, {{ x: +((p.ts - t0).toFixed(2)), y: 2000 }}],
        borderColor: 'rgba(255,213,79,0.4)',
        borderWidth: 1,
        borderDash: [4, 3],
        pointRadius: 0,
        yAxisID: 'y',
      }})),
    ],
  }},
  options: commonOpts('MB', {{}}),
}});
</script>
</body>
</html>
"""


def _phase_table_html(phases: list[dict]) -> str:
    if not phases:
        return "<p style='color:#888;'>No PHASE: markers found. Ensure spotibox.service ran and you have journalctl access.</p>"

    init_ts = next((p["ts"] for p in phases if p["phase"] == "PHASE:init_start"), phases[0]["ts"])
    rows = []
    prev_ts = None
    for p in phases:
        elapsed = round(p["ts"] - init_ts, 3)
        duration = round(p["ts"] - prev_ts, 3) if prev_ts is not None else "-"
        dt = datetime.fromtimestamp(p["ts"], tz=timezone.utc).strftime("%H:%M:%S.%f")[:-3]
        rows.append(
            f"<tr><td class='phase-name'>{p['phase']}</td>"
            f"<td>{dt} UTC</td>"
            f"<td>{elapsed}s</td>"
            f"<td>{duration}{'s' if duration != '-' else ''}</td></tr>"
        )
        prev_ts = p["ts"]

    rows_html = "\n".join(rows)
    return f"""<table>
<thead><tr><th>Phase</th><th>Wall Time (UTC)</th><th>Elapsed since init_start</th><th>Duration since prev</th></tr></thead>
<tbody>{rows_html}</tbody>
</table>"""


def _render(metrics: list[dict], phases: list[dict], log_path: Path, output: Path, boot: int) -> None:
    summary = _summarize(metrics, phases)
    interval = None
    if len(metrics) > 1:
        interval = round((metrics[-1]["ts"] - metrics[0]["ts"]) / max(len(metrics) - 1, 1), 3)

    def _cls(val, warn, crit, invert=False) -> str:
        if val is None:
            return ""
        if invert:
            return "crit" if val >= crit else "warn" if val >= warn else "ok"
        return "crit" if val >= crit else "warn" if val >= warn else "ok"

    startup_s = summary.get("startup_s")
    html = _HTML_TEMPLATE.format(
        generated_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        log_file=str(log_path),
        startup_val=f"{startup_s}s" if startup_s is not None else "N/A (no phases)",
        startup_cls="ok" if startup_s and startup_s < 30 else "warn" if startup_s else "",
        uv_now_val=summary.get("uv_now_samples", "N/A"),
        uv_now_cls="ok" if summary.get("uv_now_samples", 0) == 0 else "crit",
        uv_occurred_val="YES" if summary.get("uv_occurred") else "NO",
        uv_occurred_cls="ok" if not summary.get("uv_occurred") else "crit",
        throttled_val=summary.get("throttled_samples", "N/A"),
        throttled_cls="ok" if summary.get("throttled_samples", 0) == 0 else "warn",
        temp_val=f"{summary['peak_temp_c']}°C" if summary.get("peak_temp_c") is not None else "N/A",
        temp_cls=_cls(summary.get("peak_temp_c"), 65, 75),
        cpu_val=f"{summary['peak_cpu_pct']}%" if summary.get("peak_cpu_pct") is not None else "N/A",
        log_duration_val=summary.get("log_duration_s", "N/A"),
        phases_val=summary.get("phase_count", 0),
        phases_cls="ok" if summary.get("phase_count", 0) >= 10 else "warn",
        metrics_json=json.dumps(metrics),
        phases_json=json.dumps(phases),
        phase_table=_phase_table_html(phases),
        interval=interval or "?",
        samples=summary.get("samples", 0),
    )

    output.write_text(html)
    print(f"[analyze] Report written to {output.resolve()}")
    print(f"[analyze] Summary: {summary}")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Generate Spotibox startup HTML report")
    parser.add_argument(
        "--log",
        type=Path,
        default=None,
        metavar="FILE",
        help="Path to power_*.jsonl log (default: most recent in /var/log/spotibox/)",
    )
    parser.add_argument(
        "--log-dir",
        type=Path,
        default=LOG_DIR,
        metavar="DIR",
        help=f"Directory to search for logs (default: {LOG_DIR})",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        metavar="FILE",
        help=f"Output HTML file (default: {DEFAULT_OUTPUT})",
    )
    parser.add_argument(
        "--boot",
        type=int,
        default=0,
        metavar="N",
        help="journalctl --boot offset (0 = current, -1 = previous boot; default: 0)",
    )
    args = parser.parse_args()

    log_path = args.log or _latest_log(args.log_dir)
    print(f"[analyze] Reading metrics from {log_path}")

    metrics = _load_metrics(log_path)
    if not metrics:
        sys.exit(f"[analyze] No metric records found in {log_path}")

    print(f"[analyze] {len(metrics)} samples, fetching phase markers from journald (--boot={args.boot})")
    phases = _load_phases(args.boot)
    if not phases:
        print("[analyze] Warning: No PHASE: markers found in journald. Charts will show metrics only.")
        print("[analyze] Tip: Run: sudo usermod -aG systemd-journal $USER  (then re-login)")
    else:
        print(f"[analyze] {len(phases)} phase markers found")

    # Filter metrics to roughly the same time window as phases (±300s around phases)
    # to avoid huge charts spanning the full monitor uptime.
    if phases:
        phase_t0 = phases[0]["ts"] - 30   # 30s before first phase
        phase_t1 = phases[-1]["ts"] + 60  # 60s after last phase
        filtered = [m for m in metrics if phase_t0 <= m["ts"] <= phase_t1]
        if len(filtered) >= 5:
            metrics = filtered
            print(f"[analyze] Trimmed to {len(metrics)} samples around startup window")

    _render(metrics, phases, log_path, args.output, args.boot)


if __name__ == "__main__":
    main()
