#!/usr/bin/env bash
set -euo pipefail

APP_DIR="/opt/optolink"
ACTION="${1:-on}"

case "$ACTION" in
  on|1|true) VALUE=1 ;;
  off|0|false) VALUE=0 ;;
  *)
    echo "Usage: optolink-party-test [on|off]" >&2
    exit 2
    ;;
esac

if [[ ! -x "$APP_DIR/venv/bin/python" || ! -f "$APP_DIR/settings_ini.py" ]]; then
  echo "Optolink-Splitter installation not found in $APP_DIR" >&2
  exit 1
fi

cd "$APP_DIR"

runuser -u optolink -- ./venv/bin/python - "$VALUE" <<'PY'
import sys
import time

from c_settings_adapter import settings
from homeassistant_publish import connect_mqtt

value = int(sys.argv[1])
responses = []
states = []

client = connect_mqtt(retries=2, delay=1)
if client is None:
    raise SystemExit("MQTT connection failed")

respond_topic = settings.mqtt_respond
state_topic = f"{settings.mqtt_topic}/heizkreis_m1_partybetrieb"

if not settings.mqtt_listen:
    raise SystemExit("mqtt_listen is disabled")
if not respond_topic:
    raise SystemExit("mqtt_respond is disabled")

def on_message(client, userdata, message):
    payload = message.payload.decode(errors="replace")
    if message.topic == respond_topic:
        responses.append(payload)
    elif message.topic == state_topic:
        states.append(payload)

client.on_message = on_message
client.subscribe([(respond_topic, 0), (state_topic, 0)])
time.sleep(0.5)

write_cmd = f"w;0x2303;1;{value}"
print(f"WRITE  -> {settings.mqtt_listen}: {write_cmd}")
client.publish(settings.mqtt_listen, write_cmd).wait_for_publish()

deadline = time.time() + 5
while time.time() < deadline and not responses:
    time.sleep(0.1)

if responses:
    print(f"WRITE RESP <- {respond_topic}: {responses[-1]}")
else:
    print("WRITE RESP <- timeout")

responses.clear()
read_cmd = "r;0x2303;1;1;False"
print(f"READ   -> {settings.mqtt_listen}: {read_cmd}")
client.publish(settings.mqtt_listen, read_cmd).wait_for_publish()

deadline = time.time() + 5
while time.time() < deadline and not responses:
    time.sleep(0.1)

if responses:
    print(f"READ RESP  <- {respond_topic}: {responses[-1]}")
else:
    print("READ RESP  <- timeout")

deadline = time.time() + 3
while time.time() < deadline:
    if states and states[-1] == str(value):
        break
    time.sleep(0.1)

if states:
    print(f"STATE      <- {state_topic}: {states[-1]}")
else:
    print("STATE      <- no MQTT state observed")

client.loop_stop()
client.disconnect()
PY
