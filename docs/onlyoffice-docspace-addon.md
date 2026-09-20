# ONLYOFFICE DocSpace add-on for an existing ONLYOFFICE Docs LXC

This installer adds **ONLYOFFICE DocSpace Community** to an existing native ONLYOFFICE Docs installation created with the Proxmox VE Community Scripts ONLYOFFICE LXC.

The existing Document Server is reused. DocSpace is installed with native DEB packages and listens on a separate port.

## Default layout

```text
ONLYOFFICE Docs:     http://LXC-IP:80
ONLYOFFICE DocSpace: http://LXC-IP:8080
```

For VyOS HAProxy, use two hostnames:

```text
office.example.internal -> LXC-IP:8080
docs.example.internal   -> LXC-IP:80
```

TLS can terminate on VyOS.

## Requirements

- Debian-based LXC
- amd64
- existing `onlyoffice-documentserver` package
- `/etc/onlyoffice/documentserver/local.json`
- root privileges
- TCP port 8080 free by default

DocSpace is much heavier than ONLYOFFICE Docs alone. Current upstream guidance is roughly 4 CPU cores, 8 GB RAM, and 40 GB free disk space for a basic installation.

DocSpace uses OpenSearch. In an unprivileged Proxmox LXC, set this on the **Proxmox host**:

```bash
echo 'vm.max_map_count=262144' > /etc/sysctl.d/99-opensearch.conf
sysctl --system
```

The installer checks this before modifying the container.

## One-command install

Run this **inside the existing ONLYOFFICE LXC**:

```bash
bash -c "$(curl -fsSL https://raw.githubusercontent.com/SaulGoodman1337/community-scripts/main/install/onlyoffice-docspace-addon.sh)"
```

Defaults:

- DocSpace port: `8080`
- existing ONLYOFFICE Docs is reused
- JWT secret/header are read locally from `local.json`
- no JWT secret is stored in GitHub
- upstream hardware checks stay enabled
- swap-file creation is disabled; configure swap in Proxmox instead
- Fluent Bit / OpenSearch Dashboards are disabled by default

## Install with the final Docs URL

```bash
DOCS_PUBLIC_URL="https://docs.example.internal" \
bash -c "$(curl -fsSL https://raw.githubusercontent.com/SaulGoodman1337/community-scripts/main/install/onlyoffice-docspace-addon.sh)"
```

Recommended final routing:

```text
https://office.example.internal -> LXC-IP:8080
https://docs.example.internal   -> LXC-IP:80
```

Use HTTPS for both hostnames to avoid mixed-content problems.

## Options

Different DocSpace port:

```bash
DOCSPACE_PORT=8180 bash -c "$(curl -fsSL https://raw.githubusercontent.com/SaulGoodman1337/community-scripts/main/install/onlyoffice-docspace-addon.sh)"
```

Skip upstream hardware checks (not recommended):

```bash
DOCSPACE_SKIP_HARDWARE_CHECK=true bash -c "$(curl -fsSL https://raw.githubusercontent.com/SaulGoodman1337/community-scripts/main/install/onlyoffice-docspace-addon.sh)"
```

Enable Fluent Bit / OpenSearch Dashboards:

```bash
DOCSPACE_INSTALL_FLUENTBIT=true bash -c "$(curl -fsSL https://raw.githubusercontent.com/SaulGoodman1337/community-scripts/main/install/onlyoffice-docspace-addon.sh)"
```

## Safety behavior

Before installation, the script verifies the existing Docs package, checks the port and `vm.max_map_count`, reads JWT configuration, creates a backup under `/root/onlyoffice-docspace-preinstall-*`, and logs to `/var/log/onlyoffice-docspace-addon.log`.

The installer intentionally refuses to run when DocSpace is already installed.

## After installation

Open:

```text
http://LXC-IP:8080/
```

and finish the DocSpace setup wizard. Once HAProxy is active, ensure DocSpace uses the HTTPS Document Service address, for example `https://docs.example.internal/`.