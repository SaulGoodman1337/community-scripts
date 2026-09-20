#!/usr/bin/env bash
set -Eeuo pipefail

EMAIL="${1:-}"

die() {
  printf '[FAIL] %s\n' "$*" >&2
  exit 1
}

[[ $EUID -eq 0 ]] || die "Run as root inside the DocSpace LXC."
[[ -n "$EMAIL" ]] || die "Usage: $0 user@example.com"
command -v python3 >/dev/null 2>&1 || die "python3 is required."
command -v mysql >/dev/null 2>&1 || die "mysql client is required."

ENVIRONMENT="$(awk -F= '/^ENVIRONMENT=/{print $2; exit}' /etc/onlyoffice/docspace/systemd.env 2>/dev/null || true)"
ENVIRONMENT="${ENVIRONMENT:-community}"
CONF="/etc/onlyoffice/docspace/appsettings.${ENVIRONMENT}.json"
[[ -r "$CONF" ]] || die "Cannot read $CONF"

python3 - "$CONF" "$EMAIL" <<'PY'
import json
import os
import subprocess
import sys

conf_path, email = sys.argv[1], sys.argv[2]

with open(conf_path, "r", encoding="utf-8") as fh:
    cfg = json.load(fh)

try:
    conn = cfg["ConnectionStrings"]["default"]["connectionString"]
except Exception as exc:
    raise SystemExit(f"[FAIL] Cannot read MySQL connection string from {conf_path}: {exc}")

parts = {}
for item in conn.split(";"):
    if "=" not in item:
        continue
    key, value = item.split("=", 1)
    parts[key.strip().lower()] = value

host = parts.get("server", "localhost")
port = parts.get("port", "3306")
database = parts.get("database", "onlyoffice")
user = parts.get("user id") or parts.get("uid") or parts.get("user")
password = parts.get("password", "")

if not user:
    raise SystemExit("[FAIL] Could not determine the MySQL user.")

# Escape a literal string for the mysql CLI statement.
safe_email = email.replace("\\", "\\\\").replace("'", "\\'")

env = os.environ.copy()
env["MYSQL_PWD"] = password

mysql = [
    "mysql",
    "--batch",
    "--raw",
    "--skip-column-names",
    "-h", host,
    "-P", port,
    "-u", user,
    database,
]

def query(sql):
    p = subprocess.run(
        mysql + ["-e", sql],
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if p.returncode:
        raise SystemExit(f"[FAIL] MySQL command failed:\n{p.stderr.strip()}")
    return p.stdout.strip()

count = query(f"SELECT COUNT(*) FROM core_user WHERE email='{safe_email}';")
try:
    count_n = int(count)
except ValueError:
    raise SystemExit(f"[FAIL] Unexpected MySQL result while locating {email!r}: {count!r}")

if count_n == 0:
    raise SystemExit(f"[FAIL] No DocSpace user found with email {email!r}.")
if count_n != 1:
    raise SystemExit(f"[FAIL] Refusing to update: {count_n} users match email {email!r}.")

before = query(
    "SELECT id,email,activation_status,status,removed "
    f"FROM core_user WHERE email='{safe_email}';"
)
print("[INFO] Before:")
print(before)

status = query(
    f"SELECT activation_status FROM core_user WHERE email='{safe_email}';"
)

if status == "1":
    print("[ OK ] Account is already activated.")
    raise SystemExit(0)

query(
    "UPDATE core_user "
    "SET activation_status=1, last_modified=UTC_TIMESTAMP() "
    f"WHERE email='{safe_email}';"
)

after = query(
    "SELECT id,email,activation_status,status,removed "
    f"FROM core_user WHERE email='{safe_email}';"
)
print("[INFO] After:")
print(after)
print("[ OK ] Account activation_status is now 1 (Activated).")
print("[INFO] Log out of DocSpace and sign in again. If the old status is still cached, restart docspace-api and docspace-people-server.")
PY
