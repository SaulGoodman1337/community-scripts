# Heirloom LXC

> **Private repository:** define the authenticated `csrun` helper first; see [Private repository access](private-access.md). The required fine-grained PAT only needs `Contents: Read-only` on this repository.


[Heirloom](https://heirloom-app.com/) is an open-source, self-hosted family tree application. The product consists of a React frontend, a NestJS API and PostgreSQL. This helper creates a dedicated Debian LXC and runs the official production images with Docker Compose.

## Install

Run on the **Proxmox VE host**:

```bash
csrun ct/heirloom.sh
```

Default resources:

| Resource | Default |
| --- | ---: |
| CPU | 2 cores |
| RAM | 4096 MiB |
| Disk | 12 GiB |
| OS | Debian 13 |
| Container | Unprivileged, nesting enabled |
| Architecture | amd64 |

After installation, open:

```text
http://LXC-IP:8081
```

The deployment files are stored in:

```text
/opt/heirloom/docker-compose.yml
/opt/heirloom/.env
```

Generated PostgreSQL connection details are also written root-only to:

```text
/root/heirloom.creds
```

On first use, Heirloom's setup flow creates the initial administrator account.

## Deployment layout

The helper follows Heirloom's upstream production Compose deployment:

```text
Browser
  |
  +--> LXC-IP:8081 --> heirloom-app (nginx)
                         |-- /          static React frontend
                         |-- /api/*     heirloom-api
                         `-- /graphql   heirloom-api

heirloom-api --> PostgreSQL
             --> persistent media volume
```

The upstream Compose file binds the app to `127.0.0.1:8081`. The helper changes only that host binding to `8081:80` so the application is reachable directly through the LXC IP. The API and PostgreSQL services stay on the internal Docker network.

## Update

Inside the LXC, run:

```bash
update
```

The update routine:

1. upgrades Debian packages and Docker;
2. downloads the current upstream production Compose file and reapplies the LXC port binding;
3. pulls the `db`, `migrate`, `api` and `app` images;
4. applies pending Prisma migrations;
5. recreates the Heirloom services and verifies that the frontend responds;
6. removes unused Docker images.

The previous Compose file is retained as `/opt/heirloom/docker-compose.yml.bak` during updates.

## Reverse proxy / HTTPS

Point a reverse proxy at:

```text
http://LXC-IP:8081
```

For public share links, set `FRONTEND_URL` in `/opt/heirloom/.env` to the externally reachable URL and restart the stack:

```bash
cd /opt/heirloom
docker compose up -d api app
```

`PUBLIC_URL` is baked into the prebuilt frontend image by upstream CI, so changing it in the local `.env` does not rebuild canonical/SEO metadata. It does not prevent normal self-hosted use.

## Optional AI assistant

The installer leaves `AI_API_KEY` empty, so no hosted AI provider is configured by default. To enable the assistant, edit `/opt/heirloom/.env` according to the upstream configuration documentation, then restart `api`.

## Backups

Back up both persistent Docker volumes together:

- PostgreSQL data (`db_data`)
- uploaded media (`media`)

A consistent database dump plus media backup is preferable for application-level recovery. A Proxmox LXC backup/snapshot also captures the Docker volume data stored inside the container.

## Demo data

The public Heirloom demo is a seeded read-only tree. The LXC installer intentionally starts with a normal empty self-hosted instance and does not insert demo records automatically.

## Architecture note

Heirloom's Dockerfiles are multi-architecture capable, but the current upstream Jenkins pipeline builds and publishes the production application images natively as `linux/amd64`. The helper therefore advertises amd64 only to avoid ARM64 installation failures.
