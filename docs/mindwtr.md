# Mindwtr LXC

This repository provides a Proxmox VE LXC wrapper for [Mindwtr](https://github.com/dongdongbh/Mindwtr).

The LXC runs Docker Compose with two upstream containers:

```text
mindwtr-app    -> TCP 5173
mindwtr-cloud  -> TCP 8787
```

## Install

Run on the Proxmox VE host:

```bash
bash -c "$(curl -fsSL https://raw.githubusercontent.com/SaulGoodman1337/community-scripts/main/ct/mindwtr.sh)"
```

Default resources:

```text
CPU:          2 cores
RAM:          2048 MiB
Disk:         8 GiB
OS:           Debian 13
Unprivileged: yes
Nesting:      enabled
Architectures: amd64, arm64
```

## What the installer creates

Application directory:

```text
/opt/mindwtr/
├── .env
├── compose.yaml
└── data/
```

The Compose stack uses:

- `ghcr.io/dongdongbh/mindwtr-app:latest`
- `ghcr.io/dongdongbh/mindwtr-cloud:latest`

A random 32-byte hexadecimal sync token is generated during installation.

Connection details are written to:

```text
/root/mindwtr.creds
```

The credential file is mode `0600`.

## Access

```text
Web/PWA:        http://LXC-IP:5173
Cloud/Sync API: http://LXC-IP:8787
```

The web application is configured to use the local sync API automatically.

## Update

Run inside the Mindwtr LXC:

```bash
update
```

The update routine:

1. updates Debian packages;
2. refreshes the Docker installation;
3. runs `docker compose pull`;
4. recreates the stack with `docker compose up -d --remove-orphans`;
5. waits for the Mindwtr Cloud health endpoint;
6. removes unused Docker images.

## Health and troubleshooting

Check the sync API:

```bash
curl -fsS http://127.0.0.1:8787/health
```

Check containers:

```bash
cd /opt/mindwtr
docker compose ps
```

Logs:

```bash
cd /opt/mindwtr
docker compose logs --tail=200
```

Restart the stack:

```bash
cd /opt/mindwtr
docker compose up -d
```

## Reverse proxy

If you expose Mindwtr through a reverse proxy, remember that the web application and sync API are separate endpoints. Update the values in `/opt/mindwtr/.env` if the externally visible URLs change:

```text
MINDWTR_CLOUD_CORS_ORIGIN=...
MINDWTR_DEFAULT_CLOUD_URL=...
```

Then recreate the stack:

```bash
cd /opt/mindwtr
docker compose up -d
```

Keep the sync token private.
