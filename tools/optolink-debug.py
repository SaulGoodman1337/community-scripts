#!/opt/optolink/venv/bin/python
import argparse
import sys
import time

APP_DIR = "/opt/optolink"
if APP_DIR not in sys.path:
    sys.path.insert(0, APP_DIR)

from c_settings_adapter import settings  # type: ignore
from homeassistant_publish import connect_mqtt  # type: ignore


def connect():
    if not getattr(settings, "mqtt_listen", None):
        raise SystemExit("mqtt_listen is disabled")
    if not getattr(settings, "mqtt_respond", None):
        raise SystemExit("mqtt_respond is disabled")

    client = connect_mqtt(retries=2, delay=1)
    if client is None:
        raise SystemExit("MQTT connection failed")

    responses = []

    def on_message(client, userdata, message):
        if message.topic == settings.mqtt_respond:
            responses.append(message.payload.decode(errors="replace"))

    client.on_message = on_message
    client.subscribe(settings.mqtt_respond)
    time.sleep(0.4)
    return client, responses


def _command_addr(command):
    parts = command.split(";")
    if len(parts) < 2:
        return None
    try:
        return int(parts[1], 0)
    except ValueError:
        return None


def _response_addr(response):
    parts = response.split(";")
    if len(parts) < 2:
        return None
    try:
        return int(parts[1], 0)
    except ValueError:
        return None


def request(client, responses, command, label=None, timeout=4.0):
    responses.clear()
    prefix = label or command
    expected_addr = _command_addr(command)
    print(f"{prefix:<14} -> {settings.mqtt_listen}: {command}")
    client.publish(settings.mqtt_listen, command).wait_for_publish()

    deadline = time.time() + timeout
    response = None
    while time.time() < deadline and response is None:
        while responses:
            candidate = responses.pop(0)
            if expected_addr is None or _response_addr(candidate) == expected_addr:
                response = candidate
                break
        if response is None:
            time.sleep(0.05)

    if response is None:
        print(f"{prefix:<14} <- timeout")
        return None

    print(f"{prefix:<14} <- {settings.mqtt_respond}: {response}")
    return response


def party_snapshot(client, responses):
    commands = [
        ("MODE 2323", "r;0x2323;1;1;False"),
        ("PROG 2301", "r;0x2301;1;1;False"),
        ("PARTY 2303", "r;0x2303;1;1;False"),
        ("SETPT 2308", "r;0x2308;1;1;False"),
        ("F2 27F2", "r;0x27F2;1;1;False"),
        ("STATE 2500", "r;0x2500;22;raw;False"),
    ]
    for label, command in commands:
        request(client, responses, command, label)


def main():
    parser = argparse.ArgumentParser(
        description="Generic Optolink-Splitter debug client via MQTT"
    )
    sub = parser.add_subparsers(dest="mode", required=True)

    req = sub.add_parser("request", help="Send one raw Optolink-Splitter request")
    req.add_argument("command", help="e.g. r;0x2303;1;1;False")
    req.add_argument("--timeout", type=float, default=4.0)

    sub.add_parser("party-snapshot", help="Read all relevant party-mode datapoints")

    party = sub.add_parser("party-write", help="Write party state at 0x2303 and verify")
    party.add_argument("state", choices=["on", "off"])
    party.add_argument("--settle", type=float, default=2.0)

    args = parser.parse_args()

    client, responses = connect()
    try:
        if args.mode == "request":
            request(client, responses, args.command, timeout=args.timeout)
        elif args.mode == "party-snapshot":
            party_snapshot(client, responses)
        elif args.mode == "party-write":
            value = 1 if args.state == "on" else 0
            party_snapshot(client, responses)
            print("=== WRITE ===")
            request(client, responses, f"w;0x2303;1;{value}", "WRITE 2303")
            time.sleep(args.settle)
            request(client, responses, "r;0x2303;1;1;False", "READBACK")
            print("=== AFTER ===")
            party_snapshot(client, responses)
    finally:
        client.loop_stop()
        client.disconnect()


if __name__ == "__main__":
    main()
