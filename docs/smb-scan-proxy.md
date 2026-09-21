# SMB-Scan-Proxy LXC

SMB-Scan-Proxy is a small compatibility bridge for legacy printers/scanners that can only write to SMB1/NT1 shares while the real file server is kept on SMB2/SMB3.

It is inspired by projects such as [Andreetje/smb1-proxy](https://github.com/Andreetje/smb1-proxy), but this implementation is intentionally native and minimal for Proxmox LXC.

The bridge is **not** a general transparent filesystem proxy. It is a spool-and-forward design:

```text
Legacy printer/scanner
        |
        | SMB1 / NT1
        v
+----------------------------+
| SMB-Scan-Proxy LXC         |
|                            |
| Samba frontend             |
| /srv/smb-scan-proxy/inbox |
|        |                   |
|        v                   |
| local queue                |
|        |                   |
|        v                   |
| smbclient                  |
+--------|-------------------+
         | SMB3
         v
Modern Samba/NAS share
```

This keeps SMB1 isolated to a dedicated container instead of lowering the protocol floor on the real file server.

## Install

Run on the **Proxmox VE host**:

```bash
bash -c "$(curl -fsSL https://raw.githubusercontent.com/SaulGoodman1337/community-scripts/main/ct/smb-scan-proxy.sh)"
```

Defaults:

| Resource | Default |
| --- | ---: |
| CPU | 1 core |
| RAM | 512 MiB |
| Disk | 4 GiB |
| OS | Debian 13 |
| Container | unprivileged |
| Nesting | disabled |
| Frontend SMB ports | TCP 445 and 139 |

The legacy SMB service is deliberately **disabled after installation**. A random frontend Samba password is generated and stored in:

```text
/root/smb-scan-proxy.creds
```

## Configure

Inside the new LXC:

```bash
nano /etc/smb-scan-proxy.env
```

Example:

```text
ENABLED=true

PRINTER_IP=192.168.150.50

FRONTEND_SHARE=scan
FRONTEND_USER=scanner
FRONTEND_PASSWORD=<generated-password>

BACKEND_HOST=192.168.150.20
BACKEND_SHARE=Scans
BACKEND_SUBDIR=HP-M281
BACKEND_DOMAIN=WORKGROUP
BACKEND_USER=scanner
BACKEND_PASSWORD=<backend-password>
BACKEND_PROTOCOL=SMB3
```

Apply it:

```bash
smb-scan-proxy-config
```

or directly:

```bash
smb-scan-proxy-apply
```

The printer should then use the **LXC IP**, not the backend NAS:

```text
\\LXC-IP\scan
```

with:

```text
Username: scanner
Password: <FRONTEND_PASSWORD>
```

Use the proxy by IP address rather than DNS/NetBIOS name for old printer firmware.

## Security model

The frontend Samba server is configured specifically for legacy access:

```text
server min protocol = NT1
server max protocol = NT1
ntlm auth = ntlmv1-permitted
```

The backend client is kept modern:

```text
client min protocol = SMB2_02
client max protocol = SMB3
```

and the worker explicitly defaults to:

```text
BACKEND_PROTOCOL=SMB3
```

Additional safeguards:

- the LXC is unprivileged;
- no CIFS kernel mount is required;
- no Docker or nesting is required;
- Samba accepts connections only from `PRINTER_IP` plus localhost;
- anonymous/guest access is disabled;
- frontend and backend credentials are separate;
- backend credentials are stored root-owned and readable only by the upload worker group;
- received files are queued locally and deleted only after a successful backend upload;
- remote uploads use a temporary `.partial` filename before rename;
- received filenames are normalized and prefixed with a timestamp/nonce to avoid accidental overwrite.

For another isolation layer, also restrict TCP 445/139 to the printer IP with the Proxmox firewall.

## Queue behavior

Scans first land in:

```text
/srv/smb-scan-proxy/inbox
```

The worker waits until the file size/mtime is stable, then moves it into:

```text
/var/lib/smb-scan-proxy/queue
```

The queued file is uploaded with `smbclient` to the configured backend. If the NAS is unavailable, the file remains in the queue and the worker retries later.

This means the printer can finish its SMB1 upload even during a temporary backend outage.

## Status and troubleshooting

Quick status:

```bash
smb-scan-proxy-status
```

Services:

```bash
systemctl status smbd
systemctl status smb-scan-proxy-worker
```

Logs:

```bash
journalctl -u smb-scan-proxy-worker -f
journalctl -u smbd -f
```

Queued scans:

```bash
find /var/lib/smb-scan-proxy/queue -maxdepth 1 -type f -ls
```

Samba configuration:

```bash
testparm -s
```

Test the modern backend from inside the LXC:

```bash
smbclient //BACKEND-IP/SHARE -A /etc/smb-scan-proxy.backend -m SMB3 -c 'ls'
```

If the printer cannot connect at all, verify that its source address exactly matches `PRINTER_IP` and that no Proxmox firewall rule blocks TCP 445/139.

## Update

Inside the LXC:

```bash
update
```

The update routine refreshes the worker and configuration helper and then re-applies the existing `/etc/smb-scan-proxy.env`. Credentials and queued files are preserved.

## Scope

This helper is intended for scan-to-folder and similar **write-only legacy appliance workflows**. It is deliberately not a full bidirectional SMB gateway and should not be used to expose arbitrary modern shares back to SMB1 clients.
