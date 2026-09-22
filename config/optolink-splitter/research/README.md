# WB2A / VDensHO1 research notes

This directory contains hardware-verified and still-open reverse-engineering notes for the Vitodens 200-W WB2A setup used with Optolink-Splitter.

The notes are intentionally split into two layers:

- [device-vdensho1-20c2-wb2a.md](device-vdensho1-20c2-wb2a.md) — controller/device/GFA runtime behavior and live datapoints.
- [coding-plug-7833971-2015-0201.md](coding-plug-7833971-2015-0201.md) — Kesselcodierstecker identity, GWG parameters and burner characteristic.

Related implementation/reference files in the parent directory:

- `vdensho1-20c2-wb2a-service-draft-poll-list.py`
- `vdensho1-20c2-wb2a-homeassistant.py`
- `vcontrol-mapping.md`
- `wb2a-single-session-logger.py`

All current reverse engineering is read-only unless a datapoint is explicitly documented elsewhere as hardware-verified READ/WRITE.


## Logger installation

Existing Optolink-Splitter LXCs install or refresh the single-session WB2A logger through the normal:

```bash
update
```

The helper is installed as:

```text
/usr/local/bin/wb2a-single-session-logger
```

and can be started simply with:

```bash
wb2a-single-session-logger
```
