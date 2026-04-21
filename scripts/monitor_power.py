#!/usr/bin/env python3
"""monitor_power.py — Continuous power/load metrics collector for Spotibox.

Samples CPU%, temperature, memory, load, and Pi throttle flags from
/proc and vcgencmd at a configurable interval and appends JSON Lines
records to a per-boot log file in OUTPUT_DIR.

Throttle flag bits (vcgencmd get_throttled):
  Bit 0  — under-voltage detected NOW
  Bit 1  — arm frequency capped NOW
  Bit 2  — currently throttled
  Bit 3  — soft temperature limit active NOW
  Bit 16 — under-voltage has occurred since last reboot
  Bit 17 — arm frequency capped since last reboot
  Bit 18 — throttling has occurred since last reboot
  Bit 19 — soft temperature limit has occurred since last reboot

Usage (standalone):
    python scripts/monitor_power.py [--interval 0.25] [--output-dir /var/log/spotibox] [--max-files 20]

Designed to run as a systemd service (see scripts/spotibox-monitor.service).
"""
from __future__ import annotations

import argparse
import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path


# ---------------------------------------------------------------------------
# Globals
# ---------------------------------------------------------------------------
_running = True
_log_fh = None   # open file handle, closed on SIGTERM


# ---------------------------------------------------------------------------
# Signal handling
# ---------------------------------------------------------------------------
def _handle_sigterm(signum, frame):  # noqa: ARG001
    global _running
    _running = False


signal.signal(signal.SIGTERM, _handle_sigterm)
signal.signal(signal.SIGINT, _handle_sigterm)


# ---------------------------------------------------------------------------
# Metric readers
# ---------------------------------------------------------------------------
def _read_cpu_stat() -> tuple[int, int]:
    """Return (idle_jiffies, total_jiffies) from /proc/stat cpu line."""
    line = Path("/proc/stat").read_text().splitlines()[0]
    # cpu  user nice system idle iowait irq softirq steal guest guest_nice
    fields = [int(x) for x in line.split()[1:]]
    idle = fields[3] + (fields[4] if len(fields) > 4 else 0)   # idle + iowait
    total = sum(fields)
    return idle, total


def _cpu_percent(prev: tuple[int, int], curr: tuple[int, int]) -> float:
    """Compute CPU usage % from two consecutive /proc/stat snapshots."""
    d_idle = curr[0] - prev[0]
    d_total = curr[1] - prev[1]
    if d_total == 0:
        return 0.0
    return round(100.0 * (1.0 - d_idle / d_total), 1)


def _read_temp_c() -> float | None:
    """Read CPU temperature via vcgencmd or /sys/class/thermal."""
    # Try vcgencmd first (Pi-native, most accurate)
    try:
        out = subprocess.check_output(
            ["vcgencmd", "measure_temp"], text=True, timeout=1
        )
        # Output: "temp=47.7'C\n"
        return float(out.strip().removeprefix("temp=").removesuffix("'C"))
    except Exception:
        pass
    # Fallback: /sys/class/thermal/thermal_zone0/temp (millidegrees)
    thermal = Path("/sys/class/thermal/thermal_zone0/temp")
    if thermal.exists():
        try:
            return round(int(thermal.read_text().strip()) / 1000.0, 1)
        except Exception:
            pass
    return None


def _read_throttled() -> tuple[int, str]:
    """Return (throttled_int, throttled_hex) from vcgencmd get_throttled."""
    try:
        out = subprocess.check_output(
            ["vcgencmd", "get_throttled"], text=True, timeout=1
        )
        # Output: "throttled=0x50000\n"
        raw = out.strip().removeprefix("throttled=")
        val = int(raw, 16)
        return val, raw
    except Exception:
        return 0, "N/A"


def _read_mem_mb() -> tuple[float, float]:
    """Return (used_mb, total_mb) from /proc/meminfo."""
    info: dict[str, int] = {}
    for line in Path("/proc/meminfo").read_text().splitlines():
        parts = line.split()
        if parts[0] in ("MemTotal:", "MemAvailable:"):
            info[parts[0].rstrip(":")] = int(parts[1])  # kB
        if len(info) == 2:
            break
    total_kb = info.get("MemTotal", 0)
    avail_kb = info.get("MemAvailable", 0)
    used_kb = total_kb - avail_kb
    return round(used_kb / 1024, 1), round(total_kb / 1024, 1)


def _read_load1() -> float:
    """Return 1-minute load average from /proc/loadavg."""
    return float(Path("/proc/loadavg").read_text().split()[0])


# ---------------------------------------------------------------------------
# Log file management
# ---------------------------------------------------------------------------
def _open_log(output_dir: Path, max_files: int) -> tuple[object, Path]:
    """Create a new JSONL log file and prune old ones if needed."""
    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    log_path = output_dir / f"power_{timestamp}.jsonl"

    # Prune oldest files
    existing = sorted(output_dir.glob("power_*.jsonl"))
    while len(existing) >= max_files:
        existing.pop(0).unlink(missing_ok=True)

    fh = log_path.open("w", buffering=1)   # line-buffered
    return fh, log_path


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> None:
    global _running, _log_fh

    parser = argparse.ArgumentParser(description="Spotibox power/load monitor")
    parser.add_argument(
        "--interval",
        type=float,
        default=0.25,
        metavar="SECS",
        help="Sampling interval in seconds (default: 0.25)",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("/var/log/spotibox"),
        metavar="DIR",
        help="Directory to write JSONL log files (default: /var/log/spotibox)",
    )
    parser.add_argument(
        "--max-files",
        type=int,
        default=20,
        metavar="N",
        help="Maximum number of log files to keep (default: 20)",
    )
    args = parser.parse_args()

    _log_fh, log_path = _open_log(args.output_dir, args.max_files)
    print(f"[monitor_power] Logging to {log_path}", flush=True)
    print(f"[monitor_power] Sampling every {args.interval}s", flush=True)

    # Write a header comment as first line (not valid JSONL — readers skip it)
    _log_fh.write(
        json.dumps({
            "_meta": "spotibox-power-log",
            "_version": 1,
            "started_at": time.time(),
            "interval_s": args.interval,
            "pid": os.getpid(),
        }) + "\n"
    )

    # Seed CPU stat snapshot
    prev_cpu = _read_cpu_stat()
    time.sleep(args.interval)

    while _running:
        ts = time.time()
        curr_cpu = _read_cpu_stat()
        cpu_pct = _cpu_percent(prev_cpu, curr_cpu)
        prev_cpu = curr_cpu

        temp = _read_temp_c()
        throttled_int, throttled_hex = _read_throttled()
        mem_used, mem_total = _read_mem_mb()
        load1 = _read_load1()

        record = {
            "ts": round(ts, 3),
            "temp_c": temp,
            "cpu_pct": cpu_pct,
            "mem_used_mb": mem_used,
            "mem_total_mb": mem_total,
            "throttled": throttled_int,
            "throttled_hex": throttled_hex,
            "under_voltage_now": int(bool(throttled_int & (1 << 0))),
            "under_voltage_occurred": int(bool(throttled_int & (1 << 16))),
            "throttled_now": int(bool(throttled_int & (1 << 2))),
            "load1": load1,
        }
        _log_fh.write(json.dumps(record) + "\n")

        # Sleep in small increments so SIGTERM is handled promptly
        deadline = ts + args.interval
        while _running and time.time() < deadline:
            time.sleep(0.05)

    # Graceful shutdown
    _log_fh.flush()
    _log_fh.close()
    print(f"[monitor_power] Stopped. Log: {log_path}", flush=True)
    sys.exit(0)


if __name__ == "__main__":
    main()
