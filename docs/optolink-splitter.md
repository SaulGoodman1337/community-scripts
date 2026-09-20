# Optolink-Splitter LXC

[Optolink-Splitter](https://github.com/philippoo66/optolink-splitter) makes a Viessmann heating system available locally over MQTT and TCP/IP while optionally retaining Vitoconnect / ViCare connectivity.

This helper creates a dedicated Debian LXC, installs the Python application in `/opt/optolink`, creates an isolated virtual environment and runs the splitter as a systemd service.

## Important: privileged LXC

The container is **privileged by default**. This is intentional: the shared community-scripts core automatically adds common USB serial passthrough entries for privileged containers, including:

```text
/dev/serial/by-id
/dev/ttyUSB0
/dev/ttyUSB1
/dev/ttyACM0
/dev/ttyACM1
```

This avoids UID/GID mapping problems that commonly occur with USB serial devices in unprivileged LXCs.

A privileged container has a weaker isolation boundary than an unprivileged container. Use this helper only on a Proxmox host and network you administer.

## Install

Connect the Optolink USB adapter to the Proxmox host, then run on the **Proxmox VE host**:

```bash
bash -c "$(curl -fsSL https://raw.githubusercontent.com/SaulGoodman1337/community-scripts/main/ct/optolink-splitter.sh)"
```

Default resources:

| Resource | Default |
| --- | ---: |
| CPU | 1 core |
| RAM | 512 MiB |
| Disk | 4 GiB |
| OS | Debian 13 |
| Container | Privileged, nesting enabled |
| Architectures | amd64, arm64 |

There is no web interface. The default TCP listener is:

```text
LXC-IP:65234
```

## Serial device

Inside the LXC, list serial devices with:

```bash
optolink-ports
```

The default configuration uses:

```python
port_optolink = '/dev/ttyUSB0'
port_vitoconnect = None
```

If possible, use a stable `/dev/serial/by-id/...` path instead of `/dev/ttyUSB0`, for example:

```python
port_optolink = '/dev/serial/by-id/usb-Silicon_Labs_CP2102_USB_to_UART_Bridge_Controller_...'
```

If a second USB-to-TTL adapter is used for Vitoconnect, it will commonly appear as `/dev/ttyUSB1`. Configure it explicitly:

```python
port_vitoconnect = '/dev/ttyUSB1'
```

After changing serial settings:

```bash
systemctl restart optolink-splitter
```

If an adapter is unplugged and reconnected while the LXC is running, restarting the container may be necessary for the bind-mounted device node to become usable again.

## Configuration

Main configuration:

```text
/opt/optolink/settings_ini.py
```

Polling list:

```text
/opt/optolink/poll_list.py
```

Both files are copied from the upstream examples during the first installation and are not tracked by the upstream Git repository. They therefore remain intact during updates.

The installer changes two upstream example defaults for a safer first start:

- `port_vitoconnect = None`
- `mqtt_broker = None`

This means the splitter can be configured first without repeatedly trying to reach a non-existent second serial port or example MQTT broker.

## MQTT

Edit `/opt/optolink/settings_ini.py`, for example:

```python
mqtt_broker = "192.168.1.10:1883"
mqtt_user = "username:password"
mqtt_topic = "Vito"
mqtt_listen = "Vito/cmnd"
mqtt_respond = "Vito/resp"
```

Then restart:

```bash
systemctl restart optolink-splitter
```

Home Assistant users should also review the upstream Home Assistant integration and `homeassistant_poll_list.py.example`.

## Poll list

The installer creates `/opt/optolink/poll_list.py` from the upstream sample. Adapt this file to the datapoints supported by your Viessmann controller.

Useful upstream references:

- Optolink-Splitter Wiki: parameter addresses
- ViessData21 datapoint lists
- upstream poll-list samples

After changes:

```bash
systemctl restart optolink-splitter
```

## Service management

```bash
systemctl status optolink-splitter
systemctl restart optolink-splitter
systemctl stop optolink-splitter
journalctl -u optolink-splitter -f
```

The service runs as the dedicated `optolink` system user with membership in the `dialout` group.

If `/dev/ttyUSB0` is not present during installation, the service is enabled but intentionally left stopped. Once the serial adapter is visible, start it with:

```bash
systemctl start optolink-splitter
```

## Update

Inside the LXC:

```bash
update
```

The update routine:

1. updates Debian packages;
2. fetches the current upstream `main` branch;
3. resets tracked application files to upstream `main` while preserving the untracked local `settings_ini.py` and `poll_list.py` files;
4. updates the Python virtual-environment dependencies;
5. restarts the service when `/dev/ttyUSB0` is available.

The installation intentionally follows the upstream `main` branch rather than pinning a specific release, matching the upstream project's documented update model.

## Troubleshooting USB passthrough

First verify the adapter on the Proxmox host:

```bash
ls -l /dev/serial/by-id/
ls -l /dev/ttyUSB* /dev/ttyACM* 2>/dev/null
```

Then check inside the LXC:

```bash
optolink-ports
```

If the device exists on the host but not inside the LXC, stop and start the container and inspect its Proxmox config:

```bash
pct config <CTID>
```

The community-scripts core should have added USB serial device permissions and bind mounts because this helper creates a privileged container.

## Upstream warning

Optolink-Splitter is an independent project and is not affiliated with Viessmann. Communication with heating controls can include write commands; verify datapoint addresses and values before enabling writes or automations.
