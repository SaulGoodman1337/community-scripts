#!/usr/bin/env python3
"""
WB2A / VDensHO1 single-session TCP start logger.

Keeps exactly one TCP connection to optolink-splitter open and performs
multiple read commands sequentially inside that session.

Current fast set:
  - 0x55D3 len 11: burner/GFA runtime block including 0x55DC and 0x55DD
  - 0xA380 len 2: raw CFDM production-command object
  - 0xA38F len 2: raw CFDM power-state object

The previously tested 0x555C and 0x55E0 are intentionally not used as
power values on VDensHO1/20C2: a full burner run showed them fixed at 0 and 1
while verified modulation changed from 66 % to 33 %. 0xA305 is also omitted
because scaled A305 tracks 0x55DC essentially 1:1.

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
    print("Reads:    0x55D3/11 + 0xA380/2 + 0xA38F/2")
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
        "read_a380_ms",
        "read_a38f_ms",
        "a380_offset_ms",
        "a38f_offset_ms",
        "raw_55d3",
        "modulation_55dc_pct",
        "status_55dd",
        "flame",
        "lockout",
        "gfa_word_6_7",
        "seconds_since_flame",
        "raw_a380",
        "a380_b0",
        "a380_b1",
        "raw_a38f",
        "a38f_b0",
        "a38f_b1",
        "a38f_b0_half",
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
                # Read 1: burner/GFA runtime block.
                # byte 9 / 0x55DC = hardware-correlated live modulation %
                # byte 10 / 0x55DD = burner/GFA status byte
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

                flame = bool(raw55[5] & 0x20)
                lockout = bool(raw55[5] & 0x40)
                gfa_word_6_7 = (raw55[6] << 8) | raw55[7]
                modulation_55dc = raw55[9]
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
                flame_age = None if flame_start is None else sample_mid - flame_start

                # ------------------------------------------------------
                # Read 2: raw CFDM production-command object.
                # Vitosoft cross-family name:
                # nviProdCmd_CFDM_state/value at 0xA380.
                # Encoding on this exact 20C2 is intentionally left raw.
                # ------------------------------------------------------
                q2_start = time.monotonic()
                payload380, _ = client.request("read;0xA380;2")
                q2_end = time.monotonic()

                try:
                    raw380 = bytes.fromhex(payload380)
                except ValueError:
                    raise RuntimeError(f"invalid 0xA380 hex payload: {payload380!r}")
                if len(raw380) < 2:
                    raise RuntimeError(
                        f"0xA380 returned {len(raw380)} bytes, expected at least 2: {payload380}"
                    )

                # ------------------------------------------------------
                # Read 3: raw CFDM power-state object.
                # Vitosoft cross-family name:
                # nvoPWRState_CFDM_state/value at 0xA38F.
                #
                # Earlier hardware logs show e.g. A305=0x84 (66.0 %) while
                # A38F=0x82 0x01. This makes byte0 * 0.5 a useful correlation
                # candidate, but it is NOT yet a proven decode.
                # ------------------------------------------------------
                q3_start = time.monotonic()
                payload38f, _ = client.request("read;0xA38F;2")
                q3_end = time.monotonic()

                try:
                    raw38f = bytes.fromhex(payload38f)
                except ValueError:
                    raise RuntimeError(f"invalid 0xA38F hex payload: {payload38f!r}")
                if len(raw38f) < 2:
                    raise RuntimeError(
                        f"0xA38F returned {len(raw38f)} bytes, expected at least 2: {payload38f}"
                    )

                a380_mid = (q2_start + q2_end) / 2.0
                a38f_mid = (q3_start + q3_end) / 2.0
                a380_offset_ms = (a380_mid - sample_mid) * 1000.0
                a38f_offset_ms = (a38f_mid - sample_mid) * 1000.0

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
                    "read_a380_ms": f"{(q2_end - q2_start) * 1000.0:.0f}",
                    "read_a38f_ms": f"{(q3_end - q3_start) * 1000.0:.0f}",
                    "a380_offset_ms": f"{a380_offset_ms:.0f}",
                    "a38f_offset_ms": f"{a38f_offset_ms:.0f}",
                    "raw_55d3": raw55.hex(),
                    "modulation_55dc_pct": modulation_55dc,
                    "status_55dd": f"{status55dd:02x}",
                    "flame": int(flame),
                    "lockout": int(lockout),
                    "gfa_word_6_7": gfa_word_6_7,
                    "seconds_since_flame": "" if flame_age is None else f"{flame_age:.3f}",
                    "raw_a380": raw380.hex(),
                    "a380_b0": raw380[0],
                    "a380_b1": raw380[1],
                    "raw_a38f": raw38f.hex(),
                    "a38f_b0": raw38f[0],
                    "a38f_b1": raw38f[1],
                    "a38f_b0_half": f"{raw38f[0] * 0.5:.1f}",
                }
                writer.writerow(row)

                age_txt = "-" if flame_age is None else f"{flame_age:6.2f}"
                dt_txt = "-" if sample_dt_ms is None else f"{sample_dt_ms:4.0f}"

                print(
                    f"{datetime.now().strftime('%H:%M:%S.%f')[:-3]}  "
                    f"MOD={modulation_55dc:3d}%  "
                    f"A380={raw380.hex()}  "
                    f"A38F={raw38f.hex()} "
                    f"(b0/2={raw38f[0] * 0.5:5.1f})  "
                    f"FL={int(flame)}  "
                    f"55DD=0x{status55dd:02X}  "
                    f"T={age_txt}s  "
                    f"dt={dt_txt}ms  "
                    f"off380={a380_offset_ms:+.0f}ms "
                    f"off38F={a38f_offset_ms:+.0f}ms"
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
                if client.sock is not None:
                    client.sock.sendall(b"exit\n")
            except OSError:
                pass
            client.close()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
