#!/usr/bin/env python3
"""
WB2A / VDensHO1 RKR + boiler-pause cycle logger.

Read-only logger for correlating the RKR demand/freigabe candidate with
boiler temperature, burner/flame state and unknown A395 status bits.

It keeps one persistent TCP connection to optolink-splitter and samples:
  0x5556 / 4   RKR structure candidate
  0x55E0 / 17  mirrored/GWG-RKR structure candidate
  0xA395 / 4   unresolved status object
  0xA305 / 1   verified modulation, 0.5 %/LSB
  0x55D3 / 11  GFA runtime block (flame, lockout, 55DC, 55DD)
  0x2544 / 2   flow setpoint candidate, little-endian / 10
  0x0810 / 2   boiler actual temperature, little-endian / 10
  0xA307 / 2   BLR setpoint, little-endian / 100

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

            self.sock.settimeout(self.idle_timeout)

    def request(self, command: str) -> bytes:
        if self.sock is None:
            raise ConnectionError("TCP socket is not connected")

        self.sock.sendall((command + "\n").encode("ascii"))
        response = self._recv_response()
        parts = response.split(";", 2)

        if len(parts) != 3:
            raise RuntimeError(f"unexpected response for {command!r}: {response!r}")

        retcode, address, payload = parts
        if retcode != "1":
            raise RuntimeError(
                f"Optolink error for {command!r}: "
                f"retcode={retcode}, address={address}, payload={payload}"
            )

        try:
            return bytes.fromhex(payload.strip())
        except ValueError as e:
            raise RuntimeError(f"invalid hex payload for {command!r}: {payload!r}") from e


def u16le(raw: bytes) -> int:
    return raw[0] | (raw[1] << 8)


def parse_args():
    p = argparse.ArgumentParser(
        description="WB2A RKR / boiler-pause logger using one persistent optolink TCP session"
    )
    p.add_argument("--host", default="127.0.0.1", help="splitter host (default: 127.0.0.1)")
    p.add_argument("--port", type=int, default=65234, help="splitter TCP port (default: 65234)")
    p.add_argument(
        "--interval",
        type=float,
        default=1.0,
        help="minimum cycle interval in seconds (default: 1.0; actual cycle may be slower)",
    )
    p.add_argument(
        "--output",
        help="CSV path; default: /root/wb2a_rkr_cycle_YYYYmmdd_HHMMSS.csv",
    )
    return p.parse_args()


def read_exact(client: OptolinkTcp, address: str, length: int) -> bytes:
    raw = client.request(f"read;{address};{length}")
    if len(raw) < length:
        raise RuntimeError(
            f"{address} returned {len(raw)} bytes, expected {length}: {raw.hex()}"
        )
    return raw[:length]


def main():
    args = parse_args()

    logfile = (
        Path(args.output)
        if args.output
        else Path(f"/root/wb2a_rkr_cycle_{datetime.now():%Y%m%d_%H%M%S}.csv")
    )

    client = OptolinkTcp(args.host, args.port)

    print("WB2A RKR / Kesselpause logger")
    print("============================")
    print(f"Splitter: {args.host}:{args.port}")
    print(f"CSV:      {logfile}")
    print("Interval: minimum %.2f s" % args.interval)
    print("Reads:    5556/4 55E0/17 A395/4 A305/1 55D3/11 2544/2 0810/2 A307/2")
    print("Writes:   none")
    print("Ctrl-C beendet")
    print()

    try:
        client.connect()
    except OSError as e:
        print(f"TCP connect failed: {e}", file=sys.stderr)
        return 2

    fields = [
        "timestamp",
        "cycle_ms",
        "event",
        "raw_5556",
        "rkr_enable",
        "rkr_kessel_soll_c",
        "rkr_leistung_raw",
        "raw_55e0",
        "mirror_5556_55e0",
        "gwg_rkr_enable",
        "gwg_rkr_kessel_soll_head_c",
        "gwg_rkr_kessel_soll_c",
        "raw_a395",
        "a395_b0",
        "a395_b1",
        "a395_b2",
        "a395_b3",
        "a395_b2_hex",
        "raw_a305",
        "a305_modulation_pct",
        "raw_55d3",
        "flame",
        "lockout",
        "modulation_55dc_pct",
        "status_55dd_hex",
        "seconds_since_flame_stop",
        "last_off_interval_s",
        "raw_2544",
        "vorlauf_soll_c",
        "raw_0810",
        "kessel_ist_c",
        "raw_a307",
        "blr_soll_c",
    ]

    previous_flame = None
    previous_rkr_enable = None
    previous_a395_b2 = None
    flame_stop_monotonic = None
    last_off_interval = None

    with logfile.open("w", newline="", buffering=1) as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()

        try:
            while True:
                cycle_start = time.monotonic()
                events = []

                try:
                    raw5556 = read_exact(client, "0x5556", 4)
                    raw55e0 = read_exact(client, "0x55E0", 17)
                    rawa395 = read_exact(client, "0xA395", 4)
                    rawa305 = read_exact(client, "0xA305", 1)
                    raw55d3 = read_exact(client, "0x55D3", 11)
                    raw2544 = read_exact(client, "0x2544", 2)
                    raw0810 = read_exact(client, "0x0810", 2)
                    rawa307 = read_exact(client, "0xA307", 2)
                except Exception as e:
                    print(
                        f"{datetime.now().strftime('%H:%M:%S.%f')[:-3]}  "
                        f"READ_ERROR {e}; reconnecting",
                        file=sys.stderr,
                    )
                    client.close()
                    time.sleep(0.25)
                    try:
                        client.connect()
                    except OSError as reconnect_error:
                        print(f"Reconnect failed: {reconnect_error}", file=sys.stderr)
                        time.sleep(1.0)
                    continue

                now_mono = time.monotonic()

                rkr_enable = raw5556[0]
                rkr_kessel_soll = u16le(raw5556[1:3]) / 10.0
                rkr_leistung_raw = raw5556[3]

                mirror_match = raw55e0[:4] == raw5556
                gwg_rkr_enable = raw55e0[0]
                gwg_head_soll = u16le(raw55e0[1:3]) / 10.0
                gwg_rkr_soll = u16le(raw55e0[10:12]) / 10.0

                a395_b2 = rawa395[2]
                a305_mod = rawa305[0] * 0.5

                flame = bool(raw55d3[5] & 0x20)
                lockout = bool(raw55d3[5] & 0x40)
                modulation_55dc = raw55d3[9]
                status_55dd = raw55d3[10]

                vorlauf_soll = u16le(raw2544) / 10.0
                kessel_ist = u16le(raw0810) / 10.0
                blr_soll = u16le(rawa307) / 100.0

                if previous_flame is not None and flame != previous_flame:
                    if flame:
                        if flame_stop_monotonic is not None:
                            last_off_interval = now_mono - flame_stop_monotonic
                            events.append(f"FLAME_START(off={last_off_interval:.1f}s)")
                        else:
                            events.append("FLAME_START")
                    else:
                        flame_stop_monotonic = now_mono
                        events.append("FLAME_STOP")

                if previous_rkr_enable is not None and rkr_enable != previous_rkr_enable:
                    events.append(f"RKR_ENABLE_{previous_rkr_enable:02x}->{rkr_enable:02x}")

                if previous_a395_b2 is not None and a395_b2 != previous_a395_b2:
                    events.append(f"A395_B2_{previous_a395_b2:02x}->{a395_b2:02x}")

                previous_flame = flame
                previous_rkr_enable = rkr_enable
                previous_a395_b2 = a395_b2

                off_age = (
                    None
                    if flame or flame_stop_monotonic is None
                    else now_mono - flame_stop_monotonic
                )

                cycle_end = time.monotonic()
                event_text = "|".join(events)

                row = {
                    "timestamp": datetime.now().isoformat(timespec="milliseconds"),
                    "cycle_ms": f"{(cycle_end - cycle_start) * 1000.0:.0f}",
                    "event": event_text,
                    "raw_5556": raw5556.hex(),
                    "rkr_enable": rkr_enable,
                    "rkr_kessel_soll_c": f"{rkr_kessel_soll:.1f}",
                    "rkr_leistung_raw": rkr_leistung_raw,
                    "raw_55e0": raw55e0.hex(),
                    "mirror_5556_55e0": int(mirror_match),
                    "gwg_rkr_enable": gwg_rkr_enable,
                    "gwg_rkr_kessel_soll_head_c": f"{gwg_head_soll:.1f}",
                    "gwg_rkr_kessel_soll_c": f"{gwg_rkr_soll:.1f}",
                    "raw_a395": rawa395.hex(),
                    "a395_b0": rawa395[0],
                    "a395_b1": rawa395[1],
                    "a395_b2": a395_b2,
                    "a395_b3": rawa395[3],
                    "a395_b2_hex": f"0x{a395_b2:02x}",
                    "raw_a305": rawa305.hex(),
                    "a305_modulation_pct": f"{a305_mod:.1f}",
                    "raw_55d3": raw55d3.hex(),
                    "flame": int(flame),
                    "lockout": int(lockout),
                    "modulation_55dc_pct": modulation_55dc,
                    "status_55dd_hex": f"0x{status_55dd:02x}",
                    "seconds_since_flame_stop": "" if off_age is None else f"{off_age:.1f}",
                    "last_off_interval_s": "" if last_off_interval is None else f"{last_off_interval:.1f}",
                    "raw_2544": raw2544.hex(),
                    "vorlauf_soll_c": f"{vorlauf_soll:.1f}",
                    "raw_0810": raw0810.hex(),
                    "kessel_ist_c": f"{kessel_ist:.1f}",
                    "raw_a307": rawa307.hex(),
                    "blr_soll_c": f"{blr_soll:.1f}",
                }
                writer.writerow(row)

                evt = f"  {event_text}" if event_text else ""
                off_txt = "-" if off_age is None else f"{off_age:5.0f}s"
                print(
                    f"{datetime.now().strftime('%H:%M:%S.%f')[:-3]}  "
                    f"RKR={rkr_enable:02x} {rkr_kessel_soll:4.1f}C P={rkr_leistung_raw:02x}  "
                    f"MIR={int(mirror_match)} GWG={gwg_rkr_soll:4.1f}C  "
                    f"A395.b2={a395_b2:02x}  "
                    f"FL={int(flame)} 55DC={modulation_55dc:3d}% A305={a305_mod:4.1f}%  "
                    f"VS={vorlauf_soll:4.1f}C BLR={blr_soll:4.1f}C IST={kessel_ist:4.1f}C  "
                    f"OFF={off_txt}  "
                    f"cycle={(cycle_end - cycle_start) * 1000.0:.0f}ms"
                    f"{evt}"
                )

                remaining = args.interval - (time.monotonic() - cycle_start)
                if remaining > 0:
                    time.sleep(remaining)

        except KeyboardInterrupt:
            print()
            print(f"Gespeichert: {logfile}")
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
