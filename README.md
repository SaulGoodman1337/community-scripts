# Proxmox VE Helper Scripts

A collection of my own Proxmox VE helper scripts, structured after the general approach used by [community-scripts/ProxmoxVE](https://github.com/community-scripts/ProxmoxVE).

This repository is independent from the official community-scripts project.

## Scripts

| Application | Type | Install |
| --- | --- | --- |
| Mindwtr | LXC | `bash -c "$(curl -fsSL https://raw.githubusercontent.com/SaulGoodman1337/community-scripts/main/ct/mindwtr.sh)"` |

More scripts may be added over time.

## Structure

Each LXC application consists of two files:

```text
ct/<app>.sh
install/<app>-install.sh
```

- `ct/<app>.sh` defines the Proxmox container, resource defaults and update logic.
- `install/<app>-install.sh` contains the installation steps executed inside the container.

The scripts use the shared [community-scripts/core](https://github.com/community-scripts/core) framework for the Proxmox setup flow.

## Updates

Applications that provide an update routine can be updated from inside their LXC with:

```bash
update
```

The command uses the matching `update_script()` from the application's `ct/` script.
