#!/usr/bin/env bash
set -euo pipefail

CS_REPO="${COMMUNITY_SCRIPTS_REPO:-SaulGoodman1337/community-scripts}"
CS_REF="${COMMUNITY_SCRIPTS_REF:-main}"
APP_DIR="/opt/optolink"

cs_repo_fetch() {
  local rel="${1:?repo-relative path}"
  local dest="${2:?destination}"

  if [[ -n "${COMMUNITY_SCRIPTS_ROOT:-}" && -f "${COMMUNITY_SCRIPTS_ROOT}/$rel" ]]; then
    cp "${COMMUNITY_SCRIPTS_ROOT}/$rel" "$dest"
    return 0
  fi

  local token="${COMMUNITY_SCRIPTS_GITHUB_TOKEN:-}"
  if [[ -z "$token" ]]; then
    printf 'GitHub token: ' >/dev/tty
    read -rs token </dev/tty
    printf '\n' >/dev/tty
  fi
  [[ -n "$token" ]] || { echo "A GitHub token is required." >&2; return 1; }

  curl -fsSL \
    -H "Authorization: Bearer $token" \
    -H "Accept: application/vnd.github.raw+json" \
    -H "X-GitHub-Api-Version: 2022-11-28" \
    "https://api.github.com/repos/$CS_REPO/contents/$rel?ref=$CS_REF" \
    -o "$dest"
}
STAMP="$(date +%Y%m%d-%H%M%S)"

if [[ ! -d "$APP_DIR" || ! -f "$APP_DIR/settings_ini.py" ]]; then
  echo "Optolink-Splitter installation not found in $APP_DIR" >&2
  exit 1
fi

install -d -m 0755 "$APP_DIR/profiles"

for f in vscotho1-20cb-poll-list.py vcontrol-mapping.md; do
  cs_repo_fetch "config/optolink-splitter/$f" "$APP_DIR/profiles/$f"
done

cp -a "$APP_DIR/settings_ini.py" "$APP_DIR/settings_ini.py.bak-$STAMP"
cp -a "$APP_DIR/poll_list.py" "$APP_DIR/poll_list.py.bak-$STAMP" 2>/dev/null || true
cp "$APP_DIR/profiles/vscotho1-20cb-poll-list.py" "$APP_DIR/poll_list.py"

python3 - "$APP_DIR/settings_ini.py" <<'PY'
from pathlib import Path
import re, sys
p=Path(sys.argv[1])
s=p.read_text()
updates={
    'mqtt_topic': '"openv"',
    'mqtt_listen': '"openv/cmnd"',
    'mqtt_respond': '"openv/resp"',
    'mqtt_fstr': '"{dpname}"',
}
for key,value in updates.items():
    pat=rf'(?m)^{re.escape(key)}\s*=.*$'
    repl=f'{key} = {value}'
    if re.search(pat,s):
        s=re.sub(pat,repl,s)
    else:
        s += '\n'+repl+'\n'
p.write_text(s)
PY

cp "$APP_DIR/profiles/vcontrol-mapping.md" /root/optolink-vcontrol-mapping.md
chown optolink:optolink "$APP_DIR/poll_list.py" "$APP_DIR/settings_ini.py"
chmod 640 "$APP_DIR/poll_list.py" "$APP_DIR/settings_ini.py"

systemctl daemon-reload
if [[ -c /dev/ttyUSB0 ]]; then
  systemctl restart optolink-splitter.service || true
fi

echo "VScotHO1/20CB profile applied."
echo "Backups: $APP_DIR/settings_ini.py.bak-$STAMP and $APP_DIR/poll_list.py.bak-$STAMP"
echo "MQTT broker credentials were NOT changed. Configure mqtt_broker/mqtt_user in $APP_DIR/settings_ini.py."
echo "Mapping/audit: /root/optolink-vcontrol-mapping.md"
