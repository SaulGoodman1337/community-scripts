#!/usr/bin/env bash
set -euo pipefail

CS_REPO="${COMMUNITY_SCRIPTS_REPO:-SaulGoodman1337/community-scripts}"
CS_REF="${COMMUNITY_SCRIPTS_REF:-main}"
APP_DIR="/opt/optolink"
PROFILE_REL="config/optolink-splitter/vdensho1-20c2-wb2a-homeassistant.py"
PROFILE_NAME="vdensho1-20c2-wb2a-homeassistant.py"

cs_repo_fetch() {
  local rel="${1:?repo-relative path}"
  local dest="${2:?destination}"

  if [[ -n "${COMMUNITY_SCRIPTS_ROOT:-}" && -f "${COMMUNITY_SCRIPTS_ROOT}/$rel" ]]; then
    cp "${COMMUNITY_SCRIPTS_ROOT}/$rel" "$dest"
    return 0
  fi

  local token="${COMMUNITY_SCRIPTS_GITHUB_TOKEN:-}"
  if [[ -n "$token" ]]; then
    curl -fsSL \
      -H "Authorization: Bearer $token" \
      -H "Accept: application/vnd.github.raw+json" \
      -H "X-GitHub-Api-Version: 2022-11-28" \
      "https://api.github.com/repos/$CS_REPO/contents/$rel?ref=$CS_REF" \
      -o "$dest"
    return 0
  fi

  # Public-repository fallback. Do not block non-interactive image updates
  # waiting for a token on /dev/tty.
  curl -fsSL "https://raw.githubusercontent.com/$CS_REPO/$CS_REF/$rel" -o "$dest"
}

if [[ ! -d "$APP_DIR" || ! -f "$APP_DIR/settings_ini.py" ]]; then
  echo "Optolink-Splitter installation not found in $APP_DIR" >&2
  exit 1
fi

STAMP="$(date +%Y%m%d-%H%M%S)"
install -d -m 0755 "$APP_DIR/profiles"

tmp="$(mktemp)"
trap 'rm -f "$tmp"' EXIT

cs_repo_fetch "$PROFILE_REL" "$tmp"
python3 -m py_compile "$tmp"

cp "$tmp" "$APP_DIR/profiles/$PROFILE_NAME"

cp -a "$APP_DIR/settings_ini.py" "$APP_DIR/settings_ini.py.bak-$STAMP"

had_poll=0
had_ha=0
if [[ -f "$APP_DIR/poll_list.py" ]]; then
  had_poll=1
  cp -a "$APP_DIR/poll_list.py" "$APP_DIR/poll_list.py.bak-$STAMP"
fi
if [[ -f "$APP_DIR/homeassistant_poll_list.py" ]]; then
  had_ha=1
  cp -a "$APP_DIR/homeassistant_poll_list.py" "$APP_DIR/homeassistant_poll_list.py.bak-$STAMP"
fi

rollback_profile() {
  echo "Rolling back Optolink profile..." >&2
  if [[ "$had_poll" == "1" ]]; then
    cp -a "$APP_DIR/poll_list.py.bak-$STAMP" "$APP_DIR/poll_list.py"
  else
    rm -f "$APP_DIR/poll_list.py"
  fi
  if [[ "$had_ha" == "1" ]]; then
    cp -a "$APP_DIR/homeassistant_poll_list.py.bak-$STAMP" "$APP_DIR/homeassistant_poll_list.py"
  else
    rm -f "$APP_DIR/homeassistant_poll_list.py"
  fi
  chown optolink:optolink "$APP_DIR/settings_ini.py" 2>/dev/null || true
  [[ ! -f "$APP_DIR/poll_list.py" ]] || chown optolink:optolink "$APP_DIR/poll_list.py"
  [[ ! -f "$APP_DIR/homeassistant_poll_list.py" ]] || chown optolink:optolink "$APP_DIR/homeassistant_poll_list.py"
}

cp "$tmp" "$APP_DIR/homeassistant_poll_list.py"

# c_polllist.py gives poll_list.py precedence. Remove it after creating a
# timestamped backup so the Home Assistant adapter becomes the active source.
rm -f "$APP_DIR/poll_list.py"

chown optolink:optolink   "$APP_DIR/settings_ini.py"   "$APP_DIR/homeassistant_poll_list.py"   "$APP_DIR/profiles/$PROFILE_NAME"
chmod 640   "$APP_DIR/settings_ini.py"   "$APP_DIR/homeassistant_poll_list.py"   "$APP_DIR/profiles/$PROFILE_NAME"

echo "Validating Home Assistant discovery configuration..."
# Validate the generated HA discovery configuration before touching the service.
if ! timeout 30s runuser -u optolink --   "$APP_DIR/venv/bin/python" "$APP_DIR/homeassistant_publish.py" -c   > /root/optolink-ha-discovery-dry-run.txt 2>&1; then
  rc=$?
  if [[ "$rc" == "124" ]]; then
    echo "Home Assistant discovery dry-run timed out after 30s." >&2
  else
    echo "Home Assistant discovery dry-run failed (exit $rc)." >&2
  fi
  cat /root/optolink-ha-discovery-dry-run.txt >&2
  rollback_profile
  exit 1
fi

echo "Discovery dry-run OK."
systemctl daemon-reload

if [[ -c /dev/ttyUSB0 ]]; then
  echo "Restarting Optolink-Splitter with VDensHO1 profile..."
  systemctl restart optolink-splitter.service
  sleep 3

  if ! systemctl is-active --quiet optolink-splitter.service; then
    echo "Optolink-Splitter did not stay active with the new profile." >&2
    journalctl -u optolink-splitter.service -n 30 --no-pager >&2 || true
    rollback_profile
    systemctl restart optolink-splitter.service || true
    exit 1
  fi
else
  systemctl stop optolink-splitter.service 2>/dev/null || true
  echo "No /dev/ttyUSB0 present; profile installed but service left stopped."
fi

mqtt_enabled="$(runuser -u optolink -- "$APP_DIR/venv/bin/python" - <<'PY'
import sys
sys.path.insert(0, "/opt/optolink")
import settings_ini
print("1" if getattr(settings_ini, "mqtt_broker", None) else "0")
PY
)"

if [[ "$mqtt_enabled" == "1" && -c /dev/ttyUSB0 ]]; then
  echo "Publishing Home Assistant MQTT discovery (timeout 45s)..."
  # Discovery publishing is intentionally non-fatal: the Optolink service
  # remains useful even if Home Assistant/MQTT is temporarily unavailable.
  if timeout 45s runuser -u optolink --       "$APP_DIR/venv/bin/python" "$APP_DIR/homeassistant_publish.py"; then
    echo "Home Assistant MQTT discovery published."

    # Discovery is published after the splitter has already started. New HA
    # entities can therefore miss their first non-retained state message.
    # Clear the splitters MQTT publish cache and force one complete poll after
    # HA has subscribed to the newly created discovery entities.
    echo "Refreshing MQTT states after discovery..."
    if (
      cd "$APP_DIR"
      timeout 20s runuser -u optolink -- ./venv/bin/python - <<'PY'
import time
from c_settings_adapter import settings
from homeassistant_publish import connect_mqtt

client = connect_mqtt(retries=2, delay=2)
if client is None:
    raise SystemExit(1)

try:
    if not settings.mqtt_listen:
        raise RuntimeError("mqtt_listen is disabled")
    client.publish(settings.mqtt_listen, "reset").wait_for_publish()
    time.sleep(0.5)
    client.publish(settings.mqtt_listen, "forcepoll").wait_for_publish()
    time.sleep(1.0)
finally:
    client.loop_stop()
    client.disconnect()
PY
    )
    then
      echo "MQTT state refresh triggered."
    else
      echo "WARNING: Could not trigger MQTT state refresh; restart optolink-splitter to republish states." >&2
    fi
  else
    rc=$?
    if [[ "$rc" == "124" ]]; then
      echo "WARNING: HA discovery publish timed out after 45s." >&2
    else
      echo "WARNING: HA discovery publish failed (exit $rc)." >&2
    fi
    echo "Optolink remains active. Retry later with:" >&2
    echo "  cd /opt/optolink && ./venv/bin/python homeassistant_publish.py" >&2
  fi
else
  echo "MQTT is disabled; discovery was validated but not published."
fi

echo "VDensHO1/20C2 Home Assistant profile is active."
echo "Active profile: $APP_DIR/homeassistant_poll_list.py"
echo "Discovery dry-run: /root/optolink-ha-discovery-dry-run.txt"
if [[ -f "$APP_DIR/poll_list.py.bak-$STAMP" ]]; then
  echo "Previous poll list backup: $APP_DIR/poll_list.py.bak-$STAMP"
fi
if [[ -f "$APP_DIR/homeassistant_poll_list.py.bak-$STAMP" ]]; then
  echo "Previous HA profile backup: $APP_DIR/homeassistant_poll_list.py.bak-$STAMP"
fi
