"""
Read-only probe: can a real charger serve the measurement registers at a short
interval, and how fresh is its own meter reading?

Reads exactly what the integration reads on each measurement interval
(registers 300-345 and 1200-1215 of socket 1) and never writes. Run it while
Home Assistant stays connected, to see whether the charger copes with both.

Usage:
    python measure_live_rate.py                      # 10 min at 1 s
    python measure_live_rate.py --duration 30 --interval 2

Configuration:
    local_config.py with ALFEN_HOST and ALFEN_PORT (gitignored)
"""
import argparse
import itertools
import statistics
import struct
import time

from pymodbus.client import ModbusTcpClient

try:
    from local_config import ALFEN_HOST, ALFEN_PORT
except ImportError:
    print("ERROR: local_config.py not found (set ALFEN_HOST and ALFEN_PORT)")
    raise SystemExit(1)

SOCKET_UNIT = 1


def u64(registers):
    return struct.unpack(">Q", b"".join(r.to_bytes(2, "big") for r in registers))[0]


def f32(registers):
    return struct.unpack(">f", b"".join(r.to_bytes(2, "big") for r in registers))[0]


def percentile(values, pct):
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, int(len(ordered) * pct / 100))]


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    parser.add_argument("--duration", type=float, default=600, help="seconds (default 600)")
    parser.add_argument("--interval", type=float, default=1.0, help="seconds between reads (default 1)")
    args = parser.parse_args()

    client = ModbusTcpClient(host=ALFEN_HOST, port=ALFEN_PORT, timeout=3)
    if not client.connect():
        print(f"Cannot connect to {ALFEN_HOST}:{ALFEN_PORT}")
        raise SystemExit(1)

    ok = failed = reconnects = 0
    latencies, ages, powers, errors = [], [], [], []
    end = time.time() + args.duration
    next_read = time.time()
    while time.time() < end:
        start = time.time()
        try:
            meter = client.read_holding_registers(address=300, count=46, device_id=SOCKET_UNIT)
            status = client.read_holding_registers(address=1200, count=16, device_id=SOCKET_UNIT)
            if meter.isError() or status.isError():
                failed += 1
                errors.append(str(meter if meter.isError() else status))
            else:
                ok += 1
                latencies.append((time.time() - start) * 1000)
                ages.append(u64(meter.registers[1:5]))
                powers.append(round(f32(meter.registers[44:46]), 1))
        except Exception as exc:  # noqa: BLE001 - count it and keep measuring
            failed += 1
            errors.append(repr(exc))
            client.close()
            reconnects += 1
            client.connect()
        next_read += args.interval
        time.sleep(max(0.0, next_read - time.time()))
    client.close()

    total = ok + failed
    print(f"Charger {ALFEN_HOST}: {total} cycles of 2 reads at {args.interval:g} s over {args.duration:g} s")
    print(f"  ok {ok}, failed {failed}, reconnects {reconnects}")
    if latencies:
        print(f"  latency per cycle (ms): median {statistics.median(latencies):.0f}, "
              f"p95 {percentile(latencies, 95):.0f}, max {max(latencies):.0f}")
    if ages:
        print(f"  meter reading age (ms): median {statistics.median(ages):.0f}, "
              f"p95 {percentile(ages, 95):.0f}, max {max(ages)}")
        changes = sum(1 for a, b in itertools.pairwise(powers) if a != b)
        print(f"  real power sum: {changes} changes in {len(powers)} reads, last {powers[-1]} W")
    for err in errors[:5]:
        print(f"  error: {err}")
    raise SystemExit(0 if failed == 0 else 1)


if __name__ == "__main__":
    main()
