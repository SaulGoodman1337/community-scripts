# Community Scripts

Personal Proxmox VE helper scripts and add-ons for services that are not covered by my standard setup.

The repository follows the general layout of [community-scripts/ProxmoxVE](https://github.com/community-scripts/ProxmoxVE) and uses the shared [community-scripts/core](https://github.com/community-scripts/core) framework where appropriate. It is an independent repository and is not part of the official community-scripts project.

## Private repository access

Installers are run through an authenticated bootstrap. Create a GitHub fine-grained PAT restricted to this repository with **Contents: Read-only**, then define `csrun` once in the current shell:

```bash
csrun() {
  local target="${1:?repo-relative script path}"
  shift || true
  local token bootstrap

  printf 'GitHub token: ' >/dev/tty
  read -rs token </dev/tty
  printf '\n' >/dev/tty

  bootstrap="$(
    curl -fsSL \
      -H "Authorization: Bearer $token" \
      -H "Accept: application/vnd.github.raw+json" \
      -H "X-GitHub-Api-Version: 2022-11-28" \
      "https://api.github.com/repos/SaulGoodman1337/community-scripts/contents/tools/private-run.sh?ref=main"
  )"

  COMMUNITY_SCRIPTS_GITHUB_TOKEN="$token" bash -c "$bootstrap" -- "$target" "$@"
  unset token bootstrap
}
```

The token is requested per run and is not stored by the bootstrap. Existing LXCs should run their old `update` once **before** the repository is switched from public to private so their update entrypoint is migrated. See [docs/private-access.md](docs/private-access.md).

---

## Included projects

| Project | Purpose | Install location | Default ports |
| --- | --- | --- | --- |
| **Mindwtr** | Creates a dedicated Debian LXC and runs the Mindwtr web app plus its self-hosted sync backend with Docker Compose. | Run on the **Proxmox host** | Web: `5173`, Sync API: `8787` |
| **Heirloom** | Creates a dedicated Debian LXC and runs the Heirloom family-tree app with PostgreSQL using the upstream Docker Compose stack. | Run on the **Proxmox host** | Web: `8081` |
| **SMB-Scan-Proxy** | Creates an isolated legacy scan-to-folder compatibility bridge and forwards completed files to a modern SMB3 backend. | Run on the **Proxmox host** | SMB: `445`, `139` |
| **ONLYOFFICE DocSpace add-on** | Adds DocSpace Community to an **existing native ONLYOFFICE Docs LXC** and reuses the installed Document Server. | Run **inside the existing ONLYOFFICE LXC** | Docs: `80`, DocSpace: `8088` |

---

## Mindwtr

[Mindwtr](https://github.com/dongdongbh/Mindwtr) is a local-first GTD/task-management application. This script creates a dedicated Debian LXC and deploys the official Mindwtr app and cloud/sync containers.

### Install

Run on the **Proxmox VE host**:

```bash
csrun ct/mindwtr.sh
```

Default container resources:

| Resource | Default |
| --- | ---: |
| CPU | 2 cores |
| RAM | 2048 MiB |
| Disk | 8 GiB |
| OS | Debian 13 |
| Container | Unprivileged, nesting enabled |
| Architectures | amd64, arm64 |

After installation:

```text
Web/PWA:        http://LXC-IP:5173
Cloud/Sync API: http://LXC-IP:8787
```

The installer generates a random sync token and stores the connection details inside the LXC at:

```text
/root/mindwtr.creds
```

Update Mindwtr from inside the container with:

```bash
update
```

The update routine upgrades the base system, refreshes Docker, pulls the current Mindwtr images, recreates the Compose stack and verifies the sync service health.

More details: [docs/mindwtr.md](docs/mindwtr.md)

---

## Heirloom

[Heirloom](https://heirloom-app.com/) is an open-source, self-hosted family-tree application. This script creates a dedicated Debian LXC and deploys the upstream production Docker Compose stack with PostgreSQL, the API, and the web frontend.

Run on the **Proxmox VE host**:

```bash
csrun ct/heirloom.sh
```

Defaults: 2 CPU cores, 4096 MiB RAM, 12 GiB disk, Debian 13, unprivileged LXC with nesting enabled. The web interface is exposed at `http://LXC-IP:8081`.

The installer generates random PostgreSQL and JWT secrets, stores configuration in `/opt/heirloom/.env`, and supports updates through the standard `update` command inside the container. Upstream production images are currently published for amd64, so the helper advertises amd64 only.

More details: [docs/heirloom.md](docs/heirloom.md)

---

## SMB-Scan-Proxy

SMB-Scan-Proxy is for legacy printers/scanners with older SMB dialect requirements while the real NAS or Samba server stays on modern SMB3.

Run on the **Proxmox VE host**:

```bash
csrun ct/smb-scan-proxy.sh
```

Defaults: 1 CPU core, 512 MiB RAM, 4 GiB disk, Debian 13, unprivileged LXC. The legacy Samba listener is deliberately disabled after installation until a printer IP and `ENABLED=true` are configured in `/etc/smb-scan-proxy.env`.

The frontend is restricted to the configured printer IP and defaults to SMB2_02 for the HP compatibility case. Completed files are queued locally and forwarded with `smbclient` using SMB3 to the actual backend share. No CIFS kernel mount, Docker or privileged container is required.

Generated frontend credentials are stored in `/root/smb-scan-proxy.creds`.

More details: [docs/smb-scan-proxy.md](docs/smb-scan-proxy.md)

---

## ONLYOFFICE Docs + DocSpace

The ONLYOFFICE script is **not a standalone Document Server installer**. It is an add-on for an existing native ONLYOFFICE Docs installation, such as a Proxmox Community Scripts ONLYOFFICE LXC.

It installs **ONLYOFFICE DocSpace Community** into the same Debian LXC and keeps the existing Document Server on port 80, but binds that port to loopback only.

### Target layout

```text
Browser / Desktop Editors
  |
  +--> DocSpace / OpenResty :8088
         |
         +--> /ds-vpath/ --> 127.0.0.1:80 --> ONLYOFFICE Docs

DocSpace -> Docs      http://127.0.0.1
Docs -> DocSpace      http://127.0.0.1:8088
```

The same-origin `/ds-vpath/` route avoids mixed-content problems when DocSpace is later exposed through HTTPS.

### Requirements

- existing native `onlyoffice-documentserver` installation
- Debian-based amd64 LXC
- root shell inside the LXC
- port `8088` available
- `vm.max_map_count >= 262144` on the Proxmox host
- enough memory for Docs, DocSpace, MySQL, RabbitMQ, OpenSearch and the Java identity services

For the combined same-LXC deployment, **8 GiB RAM plus 4 GiB swap should be treated as a practical minimum**. If the Proxmox host has enough memory, 10–12 GiB RAM is considerably more comfortable. The installer limits OpenSearch to a 1 GiB heap by default.

Configure the kernel setting on the **Proxmox host**:

```bash
echo 'vm.max_map_count=262144' >/etc/sysctl.d/99-opensearch.conf
sysctl --system
```

Configure LXC swap on the **Proxmox host**, for example:

```bash
pct set <CTID> -memory 8192 -swap 4096
```

### Install DocSpace

Run **inside the existing ONLYOFFICE Docs LXC**:

```bash
csrun install/onlyoffice-docspace-addon.sh
```

Optional automatic activation of active local DocSpace users for a trusted internal deployment:

```bash
DOCSPACE_AUTO_ACTIVATE_USERS=true \
csrun install/onlyoffice-docspace-addon.sh
```

For a small installation (for example 1–2 users), enable the conservative RAM-saving profile:

```bash
DOCSPACE_LEAN_MODE=true \
csrun install/onlyoffice-docspace-addon.sh
```

Lean mode uses a 512 MiB OpenSearch heap, enables DocSpace single-instance hosting mode and disables only `docspace-ai-worker`, `docspace-mcp` and `docspace-telegram`. Single-instance mode removes the per-second MySQL worker-registration heartbeat that is unnecessary in a single-LXC deployment. The browser-facing `docspace-ai` service and backup services remain enabled to avoid 502 responses from normal UI/API routes.

Use lean mode only for a single DocSpace instance by default. If multiple DocSpace application instances share the same database, set `DOCSPACE_LEAN_SINGLETON_MODE=false`; the helper then writes `singletonMode=false` and preserves upstream active/passive worker coordination.

The installer:

- reuses the existing Document Server and its JWT secret/header;
- installs DocSpace with native DEB packages;
- keeps Docs on loopback-only port `80` and uses `8088` for DocSpace;
- removes the Debian default nginx site when active and binds ONLYOFFICE Docs to `127.0.0.1:80` / `[::1]:80`;
- fixes the same-LXC DocSpace/Docs routing to loopback;
- permits the Document Server to fetch the private loopback callback/stream URLs generated by DocSpace;
- restores the Docs services that the upstream DocSpace package configuration stops;
- defaults OpenSearch to a `1g` JVM heap, or `512m` with `DOCSPACE_LEAN_MODE=true`;
- can install a persistent lean-mode watcher that restores the single-instance override and re-disables selected optional services after dpkg/package changes;
- creates a pre-install backup under `/root/onlyoffice-docspace-preinstall-*`;
- writes its installation log to `/var/log/onlyoffice-docspace-addon.log`.

### Health checks

Inside the LXC:

```bash
curl -fsS http://127.0.0.1:8000/healthcheck ; echo
curl -fsS http://127.0.0.1/healthcheck ; echo
curl -fsS http://127.0.0.1:8088/ds-vpath/healthcheck ; echo
```

All three should return:

```text
true
```

### Reverse proxy

Expose only DocSpace:

```text
office.example.net -> LXC-IP:8088
```

The Document Server is intentionally not exposed on the LXC network interface. Browser and desktop-editor traffic reaches it through DocSpace's same-origin `/ds-vpath/` proxy. TLS can terminate at HAProxy/reverse proxy.

### ONLYOFFICE Docs 9.4.0 and ad blockers

ONLYOFFICE Docs **9.4.0 Build 129** contains a browser-side dependency named `Analytics.js`. Privacy filters such as Adblock Plus/EasyPrivacy, uBlock Origin and some browser tracking protection can block that filename. The symptom is an editor that shows only its empty/skeleton UI although all server health checks are green.

If that exact version is installed and the browser console reports a failed request similar to:

```text
.../web-apps/apps/common/Analytics.js
```

disable the blocker for the ONLYOFFICE/DocSpace origin or upgrade to a release containing the upstream fix. Do not diagnose this symptom as a backend failure before checking the browser network/console.

Full installation, tuning and account-activation notes: [docs/onlyoffice-docspace-addon.md](docs/onlyoffice-docspace-addon.md)

---

## Repository layout

```text
ct/
  mindwtr.sh                       Proxmox LXC definition and update routine
  heirloom.sh                      Heirloom LXC definition and update routine
  smb-scan-proxy.sh                SMB scan proxy LXC definition and update routine

install/
  mindwtr-install.sh               Mindwtr installation inside the new LXC
  heirloom-install.sh              Heirloom installation inside the new LXC
  smb-scan-proxy-install.sh        SMB scan proxy installation inside the new LXC
  onlyoffice-docspace-addon.sh     DocSpace add-on for an existing Docs LXC

docs/
  mindwtr.md
  heirloom.md
  smb-scan-proxy.md
  onlyoffice-docspace-addon.md

tools/
  smb-scan-proxy-apply.sh          Renders Samba config and applies proxy settings
  docspace-activate-user.sh
  docspace-auto-activate-users.sh
  docspace-lean-mode.sh

json/
  mindwtr.json                     Mindwtr script metadata
  heirloom.json                    Heirloom script metadata
  smb-scan-proxy.json              SMB scan proxy script metadata

apps/smb-scan-proxy/               SMB scan spool/upload worker

  vscotho1-20cb-poll-list.py       VScotHO1/20CB poll profile
  vcontrol-mapping.md              Legacy vcontrold to MQTT mapping
```

## Notes

- Scripts are intended for systems you administer yourself. Review them before running them on production hosts.
- Secrets generated during installation are kept locally and are not committed to this repository.
- The ONLYOFFICE account-activation helpers deliberately bypass email verification for selected local-account workflows. Use them only in trusted internal deployments.
- Upstream projects, package layouts and minimum requirements can change; verify release notes before major upgrades.
