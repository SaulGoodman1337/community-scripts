# ONLYOFFICE Docs + DocSpace in one LXC

> **Private repository:** define the authenticated `csrun` helper first; see [Private repository access](private-access.md). The required fine-grained PAT only needs `Contents: Read-only` on this repository.


This add-on installs **ONLYOFFICE DocSpace Community** next to an existing native **ONLYOFFICE Docs / Document Server** installation in the same Debian LXC.

It is designed for an existing Proxmox Community Scripts ONLYOFFICE LXC. It does **not** install a new Document Server from scratch.

## Resulting layout

Default listeners after the add-on has normalized the same-LXC layout:

```text
ONLYOFFICE Docs:     http://127.0.0.1:80   (loopback only)
ONLYOFFICE DocSpace: http://LXC-IP:8088
```

Internal routing after installation:

```text
Browser
  |
  +--> DocSpace / OpenResty :8088
          |
          +--> /ds-vpath/ --> 127.0.0.1:80 --> ONLYOFFICE Docs

DocSpace -> Docs      http://127.0.0.1
Docs -> DocSpace      http://127.0.0.1:8088
```

DocSpace therefore exposes the editor through a same-origin `/ds-vpath/` path while backend callbacks stay on loopback.

## Requirements

- Debian-based LXC
- amd64
- existing `onlyoffice-documentserver` package
- existing `/etc/onlyoffice/documentserver/local.json`
- root access inside the LXC
- port `8088` free by default
- `vm.max_map_count >= 262144`

DocSpace is much heavier than a Docs-only container. The combined LXC runs, among other services:

- ONLYOFFICE DocService and converter
- DocSpace .NET services
- two Java identity services
- MySQL
- RabbitMQ
- Redis
- OpenSearch

For this shared-LXC layout, use **at least 8 GiB RAM plus 4 GiB Proxmox LXC swap**. If the host has enough memory, 10–12 GiB RAM is a better target.

### Proxmox host preparation

OpenSearch needs a sufficiently high map count:

```bash
echo 'vm.max_map_count=262144' >/etc/sysctl.d/99-opensearch.conf
sysctl --system
```

A practical container memory configuration is:

```bash
pct set <CTID> -memory 8192 -swap 4096
```

The add-on deliberately does not create a swap file inside the LXC.

## Install

Run **inside the existing ONLYOFFICE Docs LXC**:

```bash
csrun install/onlyoffice-docspace-addon.sh
```

The installer is install-only. If DocSpace is already fully installed, it refuses to perform an in-place upgrade.

## Installer options

| Variable | Default | Purpose |
| --- | --- | --- |
| `DOCSPACE_PORT` | `8088` | External DocSpace/OpenResty listener |
| `DOCSPACE_SKIP_HARDWARE_CHECK` | `false` | Skip the upstream hardware check |
| `DOCSPACE_INSTALL_FLUENTBIT` | `false` | Enable the optional upstream Fluent Bit/OpenSearch Dashboards path |
| `DOCSPACE_AUTO_ACTIVATE_USERS` | `false` | Install automatic activation for active local accounts |
| `DOCSPACE_OPENSEARCH_HEAP` | `1g` normally, `512m` in lean mode | Fixed OpenSearch JVM heap for the shared LXC |
| `DOCSPACE_LEAN_MODE` | `false` | Enable the conservative low-memory profile |
| `DOCSPACE_LEAN_PERSIST` | `true` | Reapply lean settings automatically after dpkg package-state changes |
| `DOCSPACE_LEAN_SINGLETON_MODE` | `true` | Set `core.hosting.singletonMode=true` in lean mode; disable only for multi-instance DocSpace deployments |
| `DOCSPACE_LEAN_IDENTITY_HEAP` | empty | Optional max heap for each Java identity service, for example `640m` |
| `DOCS_PUBLIC_URL` | `http://127.0.0.1` | Advanced/bootstrap value passed to the upstream installer; final same-LXC routing is normalized to loopback and `/ds-vpath/` |

Example:

```bash
DOCSPACE_PORT=8188 \
DOCSPACE_OPENSEARCH_HEAP=1g \
csrun install/onlyoffice-docspace-addon.sh
```

Skipping the upstream hardware check is possible but should not be used as a substitute for sufficient RAM/disk:

```bash
DOCSPACE_SKIP_HARDWARE_CHECK=true \
csrun install/onlyoffice-docspace-addon.sh
```

## Lean mode for small installations

For a small trusted installation with roughly one or two users:

```bash
DOCSPACE_LEAN_MODE=true \
csrun install/onlyoffice-docspace-addon.sh
```

The default lean profile deliberately stays conservative:

```text
OpenSearch heap:     512m
single-instance mode: true
disabled:
  docspace-ai-worker
  docspace-mcp
  docspace-telegram

kept enabled:
  docspace-ai
  docspace-backup
  docspace-backup-worker
```

`core.hosting.singletonMode=true` tells DocSpace that only one application instance is participating in background-worker execution. In a single-LXC deployment this removes the active/passive worker registration heartbeat against MySQL while keeping the background workers themselves active. Do not use this setting for horizontally scaled/multi-instance DocSpace deployments; use `DOCSPACE_LEAN_SINGLETON_MODE=false` there.

`docspace-ai` stays enabled because OpenResty has direct routes such as `/api/2.0/ai` and `/asc.ai` pointing at it. Disabling that service can therefore produce benign-looking but noisy `502 Bad Gateway` responses even when document editing itself still works. The backup API also has direct OpenResty routes and is not disabled by the default lean profile.

If you want to cap the two Java identity services as an additional, more aggressive optimization:

```bash
DOCSPACE_LEAN_MODE=true \
DOCSPACE_LEAN_IDENTITY_HEAP=640m \
csrun install/onlyoffice-docspace-addon.sh
```

The identity heap limit is optional because it is more workload-sensitive than the safe service removals.

### Persistent re-apply after package updates

Lean mode installs:

```text
/usr/local/sbin/docspace-lean-enforce
/etc/default/docspace-lean
/etc/systemd/system/docspace-lean-enforce.service
/etc/systemd/system/docspace-lean-enforce.path
```

The path unit watches `/var/lib/dpkg/status`. When package state changes, it waits for `apt`/`dpkg` to finish and then:

1. restores `core.hosting.singletonMode=true` in `appsettings.community.json` when enabled;
2. restarts only currently running DocSpace services if that override had to be restored, so disabled lean-mode services stay disabled;
3. restores the configured OpenSearch heap if a package update overwrote it;
4. disables/stops `docspace-ai-worker`, `docspace-mcp` and `docspace-telegram` again;
5. restores optional identity JVM drop-ins if configured.

This is necessary because the upstream DocSpace configurator enables and restarts its full service list during reconfiguration.

For an already installed DocSpace instance, install lean mode directly:

```bash
csrun tools/docspace-lean-mode.sh install
```

Optional identity cap on an existing installation:

```bash
DOCSPACE_LEAN_IDENTITY_HEAP=640m \
csrun tools/docspace-lean-mode.sh install
```

Status:

```bash
csrun tools/docspace-lean-mode.sh status
```

Remove the persistent lean-mode machinery:

```bash
csrun tools/docspace-lean-mode.sh remove
```

Removal does not automatically restore prior OpenSearch heap values, re-enable services or remove the `core.hosting.singletonMode` override. Set `DOCSPACE_LEAN_SINGLETON_MODE=false` before removal if you want to return the override to `false`.

## What the installer changes

Before modifying the system, the script validates the existing Docs installation and creates a backup under:

```text
/root/onlyoffice-docspace-preinstall-YYYYMMDD-HHMMSS
```

The installation log is:

```text
/var/log/onlyoffice-docspace-addon.log
```

The add-on then:

1. reads the existing Docs JWT secret and JWT header from `local.json`;
2. installs DocSpace Community through the official native package installer;
3. prevents the OpenResty package from stealing port 80 during package configuration;
4. keeps the external DocSpace listener on `8088` by default;
5. normalizes DocSpace URLs to:
   - public: `/ds-vpath/`
   - internal: `http://127.0.0.1`
   - portal/callback: `http://127.0.0.1:8088`;
6. rewrites the OpenResty `/ds-vpath/` proxy to the local Document Server;
7. enables `services.CoAuthoring.request-filtering-agent.allowPrivateIPAddress` in the existing Document Server because DocSpace generates local stream/callback URLs;
8. removes the active Debian default nginx site if present;
9. rewrites the active ONLYOFFICE nginx config and its package templates so Docs listens on `127.0.0.1:80` / `[::1]:80` instead of wildcard interfaces;
10. restarts nginx plus the existing `ds-docservice`, `ds-converter` and `ds-metrics` services when present;
11. limits OpenSearch to a `1g` heap by default, or `512m` in lean mode;
12. optionally installs persistent lean-mode enforcement for single-instance hosting and selected optional services;
13. restarts the relevant DocSpace services and performs health checks.

### Why the Docs services are explicitly restarted

The upstream DocSpace package configurator stops `ds-*.service` while it configures an external/existing Document Server. In this same-LXC layout those services belong to the existing ONLYOFFICE Docs installation, so the add-on explicitly starts them again.

Without that step, port 80 can return `502` because the nginx frontend is alive while DocService on port 8000 is stopped.

## Listener and health checks

After installation, port 80 should be loopback-only:

```bash
ss -lntp | grep ':80 '
```

Expected listeners:

```text
127.0.0.1:80
[::1]:80
```

There should be no `0.0.0.0:80` or `[::]:80` listener.

Health checks:

```bash
curl -fsS http://127.0.0.1:8000/healthcheck ; echo
curl -fsS http://127.0.0.1/healthcheck ; echo
curl -fsS http://127.0.0.1:8088/ds-vpath/healthcheck ; echo
```

Expected:

```text
true
true
true
```

Useful service checks:

```bash
systemctl --failed --no-pager

systemctl status \
  ds-docservice \
  ds-converter \
  openresty \
  opensearch \
  docspace-files \
  docspace-doceditor \
  docspace-identity-authorization \
  docspace-identity-api \
  --no-pager -l
```

OpenSearch on a single node can report cluster state `yellow` because replica shards have no second node. Primary shards should still be active and the cluster should not be timed out.

## Memory / OOM troubleshooting

If services repeatedly enter `activating`, restart every minute or disappear unexpectedly:

```bash
journalctl -k -b --no-pager | grep -Ei 'oom|out of memory|killed process'
```

Check available memory:

```bash
free -h
swapon --show
```

Typical high-memory processes in this layout are OpenSearch and the two Java identity services. Increasing CPU cores does not fix an OOM condition.

The add-on defaults OpenSearch to:

```text
-Xms1g
-Xmx1g
```

Override when needed:

```bash
DOCSPACE_OPENSEARCH_HEAP=2g \
csrun install/onlyoffice-docspace-addon.sh
```

For small homelab systems, reducing below 1 GiB may work but should be tested carefully.

## Reverse proxy

Expose only DocSpace behind HAProxy/reverse proxy:

```text
office.example.net -> LXC-IP:8088
```

Do **not** expose port 80 separately in this layout. The Document Server is bound to loopback and is reached through:

```text
https://office.example.net/ds-vpath/
        -> DocSpace/OpenResty
        -> http://127.0.0.1:80
        -> ONLYOFFICE Docs
```

This same-origin path is used by both browser sessions and ONLYOFFICE Desktop Editors connected to DocSpace. TLS can terminate on the reverse proxy.

## Browser issue: ONLYOFFICE Docs 9.4.0 Build 129

ONLYOFFICE Docs 9.4.0 Build 129 has a confirmed browser-side issue involving:

```text
web-apps/apps/common/Analytics.js
```

Adblock Plus/EasyPrivacy, uBlock Origin and privacy-focused browser filtering can block this filename. The result looks like a server failure:

- the document is created successfully;
- DocSpace returns a valid editor configuration;
- Docs health checks return `true`;
- the editor page shows only an empty/skeleton UI.

The browser console/network panel then shows a failed request ending in:

```text
/web-apps/apps/common/Analytics.js
```

Workarounds:

1. disable ad/tracking filtering for the DocSpace/ONLYOFFICE origin; or
2. upgrade to a Document Server release containing the upstream fix.

Upstream issue:

```text
https://github.com/ONLYOFFICE/DocumentServer/issues/3686
```

The upstream fix removes the Analytics module entirely.

## Local accounts without SMTP

DocSpace normally expects local users to complete email activation. For a trusted internal deployment without SMTP, this repository contains two optional helpers.

### Activate one account

```bash
csrun tools/docspace-activate-user.sh user@example.com
```

The helper locates exactly one matching DocSpace user and changes its `activation_status` to `1`.

### Automatically activate active local accounts

Install:

```bash
csrun tools/docspace-auto-activate-users.sh install
```

Status:

```bash
csrun tools/docspace-auto-activate-users.sh status
```

Remove:

```bash
csrun tools/docspace-auto-activate-users.sh remove
```

The automatic helper affects only active local users with an email address. It excludes removed users, LDAP users, SSO users and auto-generated accounts. Pending invitation accounts keep their normal registration/password flow until they become active.

This deliberately bypasses an identity-verification control. Use it only on trusted internal systems where account creation is controlled by an administrator.

To install DocSpace and enable this behavior in one run:

```bash
DOCSPACE_AUTO_ACTIVATE_USERS=true \
csrun install/onlyoffice-docspace-addon.sh
```

## Important files

```text
/etc/onlyoffice/documentserver/local.json
/etc/onlyoffice/docspace/appsettings.community.json
/etc/onlyoffice/docspace/systemd.env
/etc/openresty/conf.d/onlyoffice.conf
/etc/opensearch/jvm.options
/var/log/onlyoffice-docspace-addon.log
/var/log/onlyoffice/documentserver/
/var/log/onlyoffice/docspace/
```

Do not print or commit the JWT secret or database password when collecting diagnostics.
