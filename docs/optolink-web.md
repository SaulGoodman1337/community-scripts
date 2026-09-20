# Optolink-Web LXC

Optolink-Web is a lightweight browser UI for an existing [Optolink-Splitter](https://github.com/philippoo66/optolink-splitter) installation. It does **not** access the Viessmann USB/Optolink adapter directly. The splitter remains the single owner of the physical adapter and exposes the heating control over TCP and, optionally, MQTT.

The first MVP provides:

- status and device identification via Optolink-Splitter TCP;
- live values from the existing MQTT \`openv/#\` namespace;
- a searchable datapoint browser;
- single datapoint reads over TCP;
- a read-only raw diagnostic form;
- tightly gated MQTT \`/set\` writes for explicitly whitelisted datapoints;
- no frontend build chain and no external web assets.

## Architecture

\`\`\`text
Home Assistant ---- MQTT ----+
                             |
Browser -> Optolink-Web -----+---- Optolink-Splitter ---- Optolink/USB ---- Viessmann
              |              |
              +---- TCP -----+
\`\`\`

Optolink-Web belongs in a **separate unprivileged LXC**. It does not need USB passthrough, nesting or privileged mode.

## Install

Run on the Proxmox VE host:

\`\`\`bash
bash -c "$(curl -fsSL https://raw.githubusercontent.com/SaulGoodman1337/community-scripts/main/ct/optolink-web.sh)"
\`\`\`

Default resources:

| Resource | Default |
| --- | ---: |
| CPU | 1 core |
| RAM | 512 MiB |
| Disk | 4 GiB |
| OS | Debian 13 |
| Container | unprivileged |
| Web UI | \`http://LXC-IP:8080\` |

## Initial configuration

Inside the new LXC edit:

\`\`\`bash
nano /etc/optolink-web.env
\`\`\`

At minimum set the existing splitter address:

\`\`\`text
OPTOLINK_HOST=192.168.150.71
OPTOLINK_PORT=65234
\`\`\`

For live MQTT values also configure the broker used by Optolink-Splitter:

\`\`\`text
MQTT_HOST=192.168.150.12
MQTT_PORT=1883
MQTT_USER=mqtt
MQTT_PASSWORD=change-me
MQTT_TOPIC=openv
\`\`\`

Then restart:

\`\`\`bash
systemctl restart optolink-web
\`\`\`

The helper command below opens the same file and restarts the service afterwards:

\`\`\`bash
optolink-web-config
\`\`\`

## Write safety

Writes are disabled by default:

\`\`\`text
ALLOW_WRITES=false
\`\`\`

The web backend additionally requires the datapoint to be explicitly marked writable and checks its configured minimum/maximum range before publishing to:

\`\`\`text
openv/<datapoint>/set
\`\`\`

For the initial deployment only datapoints that were already used as setpoints in the migrated installation are whitelisted. Warm-water setpoint remains read-only because the legacy configuration used a special two-byte setter and should not be generalized silently.

Before enabling writes:

1. verify TCP device identification;
2. verify live MQTT values;
3. manually read the relevant datapoints;
4. set \`ALLOW_WRITES=true\`;
5. test a non-critical setpoint with a small change and verify readback.

## TCP compatibility

The web client accepts Optolink-Splitter responses both **with and without a trailing LF**. This matters for deployments where the splitter TCP sender was patched for compatibility with ViessData 2.4.1.x / OptoLinkCommAsyncLib 1.1.1.0.

Optolink-Splitter currently accepts one TCP client session at a time. Optolink-Web therefore opens short request/response connections for manual reads and status checks instead of holding the TCP connection open permanently. If ViessData keeps a TCP session open, manual TCP reads from the web app may temporarily fail until ViessData disconnects.

MQTT live values continue to work independently.

## Service management

\`\`\`bash
systemctl status optolink-web
systemctl restart optolink-web
journalctl -u optolink-web -f
\`\`\`

## Update

Inside the LXC:

\`\`\`bash
update
\`\`\`

The update routine refreshes the application files and Python dependencies while preserving \`/etc/optolink-web.env\`.

## Current scope

This is an MVP, not yet a complete ViessData replacement. The current datapoint catalog is intentionally small and based on datapoints already exercised by this deployment. Planned follow-ups include ViessData \`vito_DP.xml\` import, heating schedules, error-history decoding, chart/history storage, operating-mode controls and a richer per-device datapoint catalog.
