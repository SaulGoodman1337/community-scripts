#!/usr/bin/env python3
"""
WB2A / VDensHO1 single-session TCP start logger.

Keeps exactly one TCP connection to optolink-splitter open and performs
multiple read commands sequentially inside that session.

Current fast set:
  - 0x55D3 len 11: GFA/burner runtime block
  - 0xA305 len 1: Vitosoft nvoBoilerState_BLR_value / Modulationsgrad

No writes are performed.
"""

import argparse
import csv
import socket
import sys
import time
from datetime import datetime
from pathlib import Path


class OptolinkTcp:
    def __init__(self, host: str, port: int, timeout: float = 5.0, idle_timeout: float = 0.35):
        self.host = host
        self.port = port
        self.timeout = timeout
        self.idle_timeout = idle_timeout
        self.sock = None
        self.rxbuf = bytearray()

    def connect(self):
        self.close()
        self.sock = socket.create_connection((self.host, self.port), timeout=self.timeout)
        self.sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        self.rxbuf.clear()

    def close(self):
        if self.sock is not None:
            try:
                self.sock.close()
            except OSError:
                pass
        self.sock = None
        self.rxbuf.clear()

    def _recv_response(self) -> str:
        if self.sock is None:
            raise ConnectionError("TCP socket is not connected")

        # First consume a complete line already buffered.
        if b"\n" in self.rxbuf:
            line, _, rest = self.rxbuf.partition(b"\n")
            self.rxbuf = bytearray(rest)
            return line.decode("utf-8", errors="replace").strip("\r\0 ")

        self.sock.settimeout(self.timeout)

        while True:
            try:
                chunk = self.sock.recv(4096)
            except socket.timeout:
                if self.rxbuf:
                    # Compatibility with splitter variants that return no LF.
                    line = bytes(self.rxbuf)
                    self.rxbuf.clear()
                    return line.decode("utf-8", errors="replace").strip("\r\n\0 ")
                raise TimeoutError("timeout waiting for optolink-splitter response")

            if not chunk:
                raise ConnectionError("optolink-splitter closed the TCP connection")

            self.rxbuf.extend(chunk)

            if b"\n" in self.rxbuf:
                line, _, rest = self.rxbuf.partition(b"\n")
                self.rxbuf = bytearray(rest)
                return line.decode("utf-8", errors="replace").strip("\r\0 ")

            # Some installations intentionally omit the trailing LF.
            # Once bytes have arrived, use a short idle timeout to detect EOT.
            self.sock.settimeout(self.idle_timeout)

    def request_any(self, command: str) -> str:
        if self.sock is None:
            raise ConnectionError("TCP socket is not connected")

        self.sock.sendall((command + "\n").encode("ascii"))
        return self._recv_response()

    def request(self, command: str) -> tuple[str, str]:
        response = self.request_any(command)

        parts = response.split(";", 2)
        if len(parts) != 3:
            raise RuntimeError(f"unexpected response: {response!r}")

        retcode, address, payload = parts

        if retcode != "1":
            raise RuntimeError(
                f"Optolink error for {command!r}: "
                f"retcode={retcode}, address={address}, payload={payload}"
            )

        return payload.strip(), response


def parse_args():
    p = argparse.ArgumentParser(
        description="WB2A burner-start logger using one persistent optolink-splitter TCP session"
    )
    p.add_argument("--host", default="127.0.0.1", help="splitter host (default: 127.0.0.1)")
    p.add_argument("--port", type=int, default=65234, help="splitter TCP port (default: 65234)")
    p.add_argument(
        "--interval",
        type=float,
        default=0.0,
        help="minimum delay between completed cycles in seconds; 0 = as fast as possible",
    )
    p.add_argument(
        "--output",
        help="CSV path; default: /root/wb2a_single_session_YYYYmmdd_HHMMSS.csv",
    )
    return p.parse_args()


def main():
    args = parse_args()

    if args.output:
        logfile = Path(args.output)
    else:
        logfile = Path(f"/root/wb2a_single_session_{datetime.now():%Y%m%d_%H%M%S}.csv")

    client = OptolinkTcp(args.host, args.port)

    print("WB2A single-session TCP logger")
    print("==============================")
    print(f"Splitter: {args.host}:{args.port}")
    print(f"CSV:      {logfile}")
    print("Reads:    0x55D3/11 + 0xA305/1")
    print("Writes:   none")
    print("Ctrl-C beendet")
    print()

    try:
        client.connect()
    except OSError as e:
        print(f"TCP connect failed: {e}", file=sys.stderr)
        return 2

    # One-time read-only probes for candidate startup-delay/ramp parameters.
    # These address semantics are NOT proven for VDensHO1/20C2; the values are
    # captured only to test correlations found in other Viessmann/GWG families.
    probe_commands = [
        ("K15_candidate_actuator_runtime", "read;0x5715;1"),
        ("K1A_candidate_start_optimization", "read;0x571A;1"),
        ("K1B_candidate_regulation_delay", "read;0x571B;1"),
        ("K1C_candidate_burner_start_delay", "read;0x571C;1"),
        ("GFA_candidate_regulation_delay", "read;0x0083;1"),
        ("coding_plug_0x1038_candidate_100", "read;0x1038;1"),
        ("RKR_candidate_power_setpoint_direct", "read;0x555C;1"),
        ("RKR_candidate_burner_power_direct", "read;0x55E0;1"),
        ("RKR_candidate_555A_struct", "read;0x555A;4"),
        ("GFA_candidate_55D3_extended", "read;0x55D3;14"),
    ]

    probe_path = logfile.with_suffix(".probes.txt")
    print("Candidate read-only probes:")
    with probe_path.open("w", encoding="utf-8") as pf:
        pf.write("# WB2A candidate startup/ramp probes\n")
        pf.write("# Read-only. Address semantics are hypotheses unless noted.\n")
        pf.write(f"# {datetime.now().isoformat(timespec='seconds')}\n")
        for label, command in probe_commands:
            try:
                response = client.request_any(command)
            except Exception as e:
                response = f"ERROR: {e}"
            line = f"{label:38s} {command:20s} -> {response}"
            print("  " + line)
            pf.write(line + "\n")
    print(f"Probe file: {probe_path}")
    print()

    fields = [
        "timestamp",
        "sample_dt_ms",
        "cycle_ms",
        "read_55d3_ms",
        "read_a305_ms",
        "a305_offset_ms",
        "raw_55d3",
        "value_55dc",
        "status_55dd",
        "flame",
        "lockout",
        "gfa_word_6_7",
        "seconds_since_flame",
        "raw_a305",
        "a305_raw",
        "a305_pct",
    ]

    last_sample_mid = None
    flame_start = None
    previous_flame = False

    with logfile.open("w", newline="", buffering=1) as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()

        try:
            while True:
                cycle_start = time.monotonic()

                # ------------------------------------------------------
                # Read 1: GFA runtime block
                # ------------------------------------------------------
                q1_start = time.monotonic()
                payload55, _ = client.request("read;0x55D3;11")
                q1_end = time.monotonic()

                try:
                    raw55 = bytes.fromhex(payload55)
                except ValueError:
                    raise RuntimeError(f"invalid 0x55D3 hex payload: {payload55!r}")

                if len(raw55) < 11:
                    raise RuntimeError(
                        f"0x55D3 returned {len(raw55)} bytes, expected at least 11: {payload55}"
                    )

                sample_mid = (q1_start + q1_end) / 2.0

                # Hardware-verified in this WB2A project:
                # byte 5 bit 0x20 = flame
                # byte 5 bit 0x40 = GFA lockout
                flame = bool(raw55[5] & 0x20)
                lockout = bool(raw55[5] & 0x40)

                # bytes 6..7 are an unresolved GFA runtime word. An earlier
                # hypothesis called this blower rpm, but high-resolution logs
                # show it remains ~2914 while modulation falls 66 -> 33 %.
                gfa_word_6_7 = (raw55[6] << 8) | raw55[7]

                # byte 9 / 0x55DC is hardware-correlated 1:1 with the scaled
                # A305 live Modulationsgrad (%). byte 10 / 0x55DD is a status
                # byte with observed 01/09/29/21 patterns.
                value55dc = raw55[9]
                status55dd = raw55[10]

                if flame and not previous_flame:
                    flame_start = sample_mid
                    event = " FLAME_START"
                elif not flame and previous_flame:
                    flame_start = None
                    event = " FLAME_STOP"
                else:
                    event = ""

                previous_flame = flame

                if flame_start is None:
                    flame_age = None
                else:
                    flame_age = sample_mid - flame_start

                # ------------------------------------------------------
                # Read 2: official Vitosoft Modulationsgrad
                # Same TCP session; no second client connection.
                # ------------------------------------------------------
                q2_start = time.monotonic()
                payload305, _ = client.request("read;0xA305;1")
                q2_end = time.monotonic()

                try:
                    raw305 = bytes.fromhex(payload305)
                except ValueError:
                    raise RuntimeError(f"invalid 0xA305 hex payload: {payload305!r}")

                if len(raw305) < 1:
                    raise RuntimeError("0xA305 returned no data")

                a305_raw = raw305[0]

                # Existing hardware verification in this project uses *0.5.
                a305_pct = a305_raw * 0.5

                a305_mid = (q2_start + q2_end) / 2.0
                a305_offset_ms = (a305_mid - sample_mid) * 1000.0

                cycle_end = time.monotonic()

                if last_sample_mid is None:
                    sample_dt_ms = None
                else:
                    sample_dt_ms = (sample_mid - last_sample_mid) * 1000.0
                last_sample_mid = sample_mid

                row = {
                    "timestamp": datetime.now().isoformat(timespec="milliseconds"),
                    "sample_dt_ms": "" if sample_dt_ms is None else f"{sample_dt_ms:.0f}",
                    "cycle_ms": f"{(cycle_end - cycle_start) * 1000.0:.0f}",
                    "read_55d3_ms": f"{(q1_end - q1_start) * 1000.0:.0f}",
                    "read_a305_ms": f"{(q2_end - q2_start) * 1000.0:.0f}",
                    "a305_offset_ms": f"{a305_offset_ms:.0f}",
                    "raw_55d3": raw55.hex(),
                    "value_55dc": value55dc,
                    "status_55dd": f"{status55dd:02x}",
                    "flame": int(flame),
                    "lockout": int(lockout),
                    "gfa_word_6_7": gfa_word_6_7,
                    "seconds_since_flame": "" if flame_age is None else f"{flame_age:.3f}",
                    "raw_a305": raw305.hex(),
                    "a305_raw": a305_raw,
                    "a305_pct": f"{a305_pct:.1f}",
                }
                writer.writerow(row)

                age_txt = "-" if flame_age is None else f"{flame_age:6.2f}"
                dt_txt = "-" if sample_dt_ms is None else f"{sample_dt_ms:4.0f}"

                print(
                    f"{datetime.now().strftime('%H:%M:%S.%f')[:-3]}  "
                    f"55DC={value55dc:3d}  "
                    f"A305={a305_pct:5.1f}% (raw {a305_raw:3d})  "
                    f"GFA67={gfa_word_6_7:4d}  "
                    f"FL={int(flame)}  "
                    f"55DD=0x{status55dd:02X}  "
                    f"T={age_txt}s  "
                    f"dt={dt_txt}ms  "
                    f"A305off={a305_offset_ms:+.0f}ms"
                    f"{event}"
                )

                if args.interval > 0:
                    remaining = args.interval - (time.monotonic() - cycle_start)
                    if remaining > 0:
                        time.sleep(remaining)

        except KeyboardInterrupt:
            print()
            print(f"Gespeichert: {logfile}")
        except Exception as e:
            print()
            print(f"Logger aborted: {e}", file=sys.stderr)
            print(f"Partial CSV: {logfile}", file=sys.stderr)
            return 1
        finally:
            try:
                # Politely tell the splitter to close this one TCP session.
                if client.sock is not None:
                    client.sock.sendall(b"exit\n")
            except OSError:
                pass
            client.close()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
