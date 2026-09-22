# Optolink-Splitter LXC

> **Private repository:** define the authenticated `csrun` helper first; see [Private repository access](private-access.md). The required fine-grained PAT only needs `Contents: Read-only` on this repository.


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
csrun ct/optolink-splitter.sh
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

The installation now uses the repository's **VScotHO1 / device 20CB profile**, derived from the existing vcontrold/vito configuration used for this deployment. The active Home Assistant datapoints are mapped to clearer Optolink-Splitter MQTT names while the source addresses and scaling remain traceable in:

```text
/root/optolink-vcontrol-mapping.md
```

The installer keeps these safe first-start defaults:

- `port_vitoconnect = None`
- `mqtt_broker = None`
- `mqtt_topic = "openv"`
- `mqtt_listen = "openv/cmnd"`
- `mqtt_respond = "openv/resp"`

The MQTT broker address and credentials are intentionally not guessed.

For an LXC that was installed before this profile existed, run:

```bash
optolink-apply-vscotho1-profile
```

The helper creates timestamped backups of `settings_ini.py` and `poll_list.py`, downloads the current 20CB profile, switches the MQTT namespace to `openv`, and restarts the service when `/dev/ttyUSB0` is present.

Two conflicts in the supplied legacy source are intentionally exposed as `legacy_*` MQTT topics instead of silently reinterpreted:

- `getTempRL17A` resolves to `0x0808` for device 20CB, which is also the supplied address for exhaust temperature.
- `getTempMaxVorlauf` resolves to `0x2306`, also used by the normal M1 room setpoint with a different scale.

## MQTT

Edit `/opt/optolink/settings_ini.py`, for example:

```python
mqtt_broker = "192.168.1.10:1883"
mqtt_user = "username:password"
mqtt_topic = "openv"
mqtt_listen = "openv/cmnd"
mqtt_respond = "openv/resp"
```

Then restart:

```bash
systemctl restart optolink-splitter
```

Home Assistant users should also review the upstream Home Assistant integration and `homeassistant_poll_list.py.example`.

## Poll list

The installer creates `/opt/optolink/poll_list.py` from the custom VScotHO1 / 20CB profile. The profile currently covers the datapoints used by the migrated Home Assistant MQTT configuration.

The current profile uses a 2-second base polling interval for `FAST` runtime values, while preserving the previous effective cadence for slower groups: `NORMAL` about 30 seconds, `SLOW` about 5 minutes and `RARE` about 30 minutes. Adjacent byte-filter datapoints at `0x7660` are derived from one shared 2-byte Optolink read to avoid a redundant request.

Useful upstream references:

- Optolink-Splitter Wiki: parameter addresses
- ViessData21 datapoint lists
- upstream poll-list samples

Project-specific WB2A reverse-engineering notes:

- [Vitodens 200-W WB2A / VDensHO1 Optolink reverse engineering](vitodens-wb2a-optolink-research.md)

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


## Home Assistant migration

The matching Home Assistant MQTT migration keeps the existing `unique_id` values from the previous vcontrold entities. This is deliberate: Home Assistant can keep the existing entity-registry identities while only the MQTT topics and friendly names change.

The old template sensors can therefore keep references such as `number.core_mosquitto_neigung` and `number.core_mosquitto_raumsolltemperatur_normal_m1` as long as those entity IDs already exist in the registry.

The migrated MQTT block also corrects several legacy semantics:

- the 20CB `getBrennerStatus` value is treated as burner modulation and a binary running sensor is derived from values greater than zero;
- the 20CB M1 pump value is treated as pump speed and can also drive the existing binary pump-running entity;
- the valve state is decoded as Undefined / Heating / Middle / Hot Water;
- error-history entries decode their first error byte using the supplied vcontrold error table;
- the warm-water setpoint uses the explicit two-byte write defined by the supplied `setTempWWsoll` command.

The Home Assistant MQTT migration file generated from the current installation is instance-specific and is therefore supplied separately rather than being treated as a generic upstream profile.
