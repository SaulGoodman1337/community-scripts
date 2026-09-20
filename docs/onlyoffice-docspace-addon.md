# ONLYOFFICE Docs + DocSpace in one LXC

This add-on installs **ONLYOFFICE DocSpace Community** next to an existing native **ONLYOFFICE Docs / Document Server** installation in the same Debian LXC.

It is designed for an existing Proxmox Community Scripts ONLYOFFICE LXC. It does **not** install a new Document Server from scratch.

## Resulting layout

Default listeners:

```text
ONLYOFFICE Docs:     http://LXC-IP:80
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
bash -c "$(curl -fsSL https://raw.githubusercontent.com/SaulGoodman1337/community-scripts/main/install/onlyoffice-docspace-addon.sh)"
```

The installer is install-only. If DocSpace is already fully installed, it refuses to perform an in-place upgrade.

## Installer options

| Variable | Default | Purpose |
| --- | --- | --- |
| `DOCSPACE_PORT` | `8088` | External DocSpace/OpenResty listener |
| `DOCSPACE_SKIP_HARDWARE_CHECK` | `false` | Skip the upstream hardware check |
| `DOCSPACE_INSTALL_FLUENTBIT` | `false` | Enable the optional upstream Fluent Bit/OpenSearch Dashboards path |
| `DOCSPACE_AUTO_ACTIVATE_USERS` | `false` | Install automatic activation for active local accounts |
| `DOCSPACE_OPENSEARCH_HEAP` | `1g` | Fixed OpenSearch JVM heap for the shared LXC |
| `DOCS_PUBLIC_URL` | `http://127.0.0.1` | Advanced/bootstrap value passed to the upstream installer; final same-LXC routing is normalized to loopback and `/ds-vpath/` |

Example:

```bash
DOCSPACE_PORT=8188 \
DOCSPACE_OPENSEARCH_HEAP=1g \
bash -c "$(curl -fsSL https://raw.githubusercontent.com/SaulGoodman1337/community-scripts/main/install/onlyoffice-docspace-addon.sh)"
```

Skipping the upstream hardware check is possible but should not be used as a substitute for sufficient RAM/disk:

```bash
DOCSPACE_SKIP_HARDWARE_CHECK=true \
bash -c "$(curl -fsSL https://raw.githubusercontent.com/SaulGoodman1337/community-scripts/main/install/onlyoffice-docspace-addon.sh)"
```

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
8. restarts the existing `ds-docservice`, `ds-converter` and `ds-metrics` services when present;
9. limits OpenSearch to a `1g` heap by default;
10. restarts the relevant DocSpace services and performs health checks.

### Why the Docs services are explicitly restarted

The upstream DocSpace package configurator stops `ds-*.service` while it configures an external/existing Document Server. In this same-LXC layout those services belong to the existing ONLYOFFICE Docs installation, so the add-on explicitly starts them again.

Without that step, port 80 can return `502` because the nginx frontend is alive while DocService on port 8000 is stopped.

## Health checks

After installation:

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
bash -c "$(curl -fsSL https://raw.githubusercontent.com/SaulGoodman1337/community-scripts/main/install/onlyoffice-docspace-addon.sh)"
```

For small homelab systems, reducing below 1 GiB may work but should be tested carefully.

## Reverse proxy

A typical split behind HAProxy is:

```text
office.example.net -> LXC-IP:8088
docs.example.net   -> LXC-IP:80
```

TLS can terminate on the reverse proxy.

The DocSpace web client uses `/ds-vpath/` to load the editor from the same origin, so the DocSpace hostname remains the important browser-facing editor origin.

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
bash -c "$(curl -fsSL https://raw.githubusercontent.com/SaulGoodman1337/community-scripts/main/tools/docspace-activate-user.sh)" -- user@example.com
```

The helper locates exactly one matching DocSpace user and changes its `activation_status` to `1`.

### Automatically activate active local accounts

Install:

```bash
bash -c "$(curl -fsSL https://raw.githubusercontent.com/SaulGoodman1337/community-scripts/main/tools/docspace-auto-activate-users.sh)" -- install
```

Status:

```bash
bash -c "$(curl -fsSL https://raw.githubusercontent.com/SaulGoodman1337/community-scripts/main/tools/docspace-auto-activate-users.sh)" -- status
```

Remove:

```bash
bash -c "$(curl -fsSL https://raw.githubusercontent.com/SaulGoodman1337/community-scripts/main/tools/docspace-auto-activate-users.sh)" -- remove
```

The automatic helper affects only active local users with an email address. It excludes removed users, LDAP users, SSO users and auto-generated accounts. Pending invitation accounts keep their normal registration/password flow until they become active.

This deliberately bypasses an identity-verification control. Use it only on trusted internal systems where account creation is controlled by an administrator.

To install DocSpace and enable this behavior in one run:

```bash
DOCSPACE_AUTO_ACTIVATE_USERS=true \
bash -c "$(curl -fsSL https://raw.githubusercontent.com/SaulGoodman1337/community-scripts/main/install/onlyoffice-docspace-addon.sh)"
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
