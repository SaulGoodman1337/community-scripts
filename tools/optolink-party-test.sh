#!/usr/bin/env bash
set -euo pipefail

APP_DIR="/opt/optolink"
ACTION="${1:-on}"

echo "NOTE: diagnostic native-Party probe only. Production HA Party ON uses" >&2
echo "      optolink-party-emulator because remote 0x2303=1 is not reliable." >&2

case "$ACTION" in
  on|1|true)
    VALUE=1
    WRITE_ADDR="0x2303"
    ;;
  off|0|false)
    VALUE=0
    WRITE_ADDR="0x2303"
    ;;
  cmd-on|2330-on)
    VALUE=1
    WRITE_ADDR="0x2330"
    ;;
  cmd-off|2330-off)
    VALUE=0
    WRITE_ADDR="0x2330"
    ;;
  *)
    echo "Usage: optolink-party-test [on|off|cmd-on|cmd-off]" >&2
    exit 2
    ;;
esac

if [[ ! -x "$APP_DIR/venv/bin/python" || ! -f "$APP_DIR/settings_ini.py" ]]; then
  echo "Optolink-Splitter installation not found in $APP_DIR" >&2
  exit 1
fi

cd "$APP_DIR"

runuser -u optolink -- ./venv/bin/python - "$VALUE" "$WRITE_ADDR" <<'PY'
import sys
import time

from c_settings_adapter import settings
from homeassistant_publish import connect_mqtt

value = int(sys.argv[1])
write_addr = sys.argv[2]
responses = []

client = connect_mqtt(retries=2, delay=1)
if client is None:
    raise SystemExit("MQTT connection failed")

respond_topic = settings.mqtt_respond

if not settings.mqtt_listen:
    raise SystemExit("mqtt_listen is disabled")
if not respond_topic:
    raise SystemExit("mqtt_respond is disabled")

def on_message(client, userdata, message):
    if message.topic == respond_topic:
        responses.append(message.payload.decode(errors="replace"))

client.on_message = on_message
client.subscribe(respond_topic)
time.sleep(0.5)

def request(label, command, timeout=4):
    responses.clear()
    print(f"{label:<12} -> {settings.mqtt_listen}: {command}")
    client.publish(settings.mqtt_listen, command).wait_for_publish()
    deadline = time.time() + timeout
    while time.time() < deadline and not responses:
        time.sleep(0.05)
    if responses:
        print(f"{label:<12} <- {respond_topic}: {responses[-1]}")
        return responses[-1]
    print(f"{label:<12} <- timeout")
    return None

print("=== Context before write ===")
request("MODE 2323", "r;0x2323;1;1;False")
request("PROG 2301", "r;0x2301;1;1;False")
request("PARTY 2303", "r;0x2303;1;1;False")
request("SETPT 2308", "r;0x2308;1;1;False")
request("HOLIDAY", "r;0x2535;1;1;False")
request("ALT 2330", "r;0x2330;1;1;False")

print("=== Party write ===")
print(f"Using command address {write_addr}; live party state is always verified at 0x2303.")
request("WRITE", f"w;{write_addr};1;{value}")

for delay in (0.2, 1.0, 3.0, 6.0):
    time.sleep(delay)
    request(f"STATE +{delay:g}s", "r;0x2303;1;1;False")

print("=== Context after write ===")
request("MODE 2323", "r;0x2323;1;1;False")
request("PROG 2301", "r;0x2301;1;1;False")
request("SETPT 2308", "r;0x2308;1;1;False")

client.loop_stop()
client.disconnect()
PY
